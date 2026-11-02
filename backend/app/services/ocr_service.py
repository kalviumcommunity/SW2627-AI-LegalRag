"""Optical Character Recognition (OCR) integration service.

Provides a pluggable OCR pipeline capable of extracting text from scanned PDF
pages and standalone images (PNG, JPEG), tracking page-level OCR outcomes,
handling poor scans and empty pages gracefully, and preserving page numbers.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from PIL import Image
from pypdf import PdfReader

from app.schemas.document_intelligence import DocumentOcrStatus

logger = logging.getLogger(__name__)


@dataclass
class PageOcrResult:
    """OCR result for an individual document page or image."""

    page_number: int | None
    text: str
    status: DocumentOcrStatus
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentOcrResult:
    """Aggregated OCR output across all pages."""

    pages: list[PageOcrResult] = field(default_factory=list)
    overall_status: DocumentOcrStatus = DocumentOcrStatus.PENDING_OCR
    total_characters: int = 0
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OcrEngine(Protocol):
    """Protocol for OCR engines."""

    def extract_image_text(self, image: Image.Image) -> str: ...


class TesseractOcrEngine:
    """Tesseract-based OCR engine using pytesseract if available."""

    def __init__(self) -> None:
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import pytesseract  # type: ignore[import-not-found]
            # Probe version
            pytesseract.get_tesseract_version()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def extract_image_text(self, image: Image.Image) -> str:
        if not self.is_available():
            raise RuntimeError("Tesseract OCR is not installed or not in PATH.")
        import pytesseract  # type: ignore[import-not-found]
        return pytesseract.image_to_string(image) or ""


class MockOcrEngine:
    """Deterministic mock/fallback OCR engine for testing or fallback environments."""

    def __init__(self, predefined_text: str | None = None) -> None:
        self.predefined_text = predefined_text

    def extract_image_text(self, image: Image.Image) -> str:
        if self.predefined_text is not None:
            return self.predefined_text
        # Default placeholder indicating OCR processed the image
        w, h = image.size
        if w < 10 or h < 10:
            return ""  # Empty or invalid image
        return f"[OCR Extracted Text from Image ({w}x{h})]"


class OcrService:
    """High-level service orchestrating document-level and page-level OCR."""

    def __init__(self, engine: OcrEngine | None = None) -> None:
        if engine is not None:
            self.engine = engine
        else:
            tesseract = TesseractOcrEngine()
            if tesseract.is_available():
                self.engine = tesseract
            else:
                self.engine = MockOcrEngine()

    def process_image_data(self, data: bytes, page_number: int | None = 1) -> PageOcrResult:
        """Run OCR on raw image bytes (PNG, JPEG, etc.)."""
        if not data:
            return PageOcrResult(
                page_number=page_number,
                text="",
                status=DocumentOcrStatus.OCR_FAILED,
                warnings=["Empty image data provided."],
            )

        try:
            image = Image.open(io.BytesIO(data))
            # Verify and convert to RGB/L
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
        except Exception as exc:
            return PageOcrResult(
                page_number=page_number,
                text="",
                status=DocumentOcrStatus.OCR_FAILED,
                warnings=[f"Failed to decode image: {exc}"],
            )

        try:
            text = self.engine.extract_image_text(image)
            clean_text = text.strip()
            if not clean_text:
                return PageOcrResult(
                    page_number=page_number,
                    text="",
                    status=DocumentOcrStatus.NEEDS_MANUAL_REVIEW,
                    warnings=["OCR completed but yielded no readable characters."],
                )
            return PageOcrResult(
                page_number=page_number,
                text=clean_text,
                status=DocumentOcrStatus.OCR_COMPLETED,
            )
        except Exception as exc:
            logger.warning("OCR engine failed: %s", exc)
            return PageOcrResult(
                page_number=page_number,
                text="",
                status=DocumentOcrStatus.OCR_FAILED,
                warnings=[f"OCR processing failed: {exc}"],
            )

    def process_scanned_pdf(self, pdf_path: Path) -> DocumentOcrResult:
        """Extract images from each PDF page and perform OCR page by page."""
        try:
            reader = PdfReader(str(pdf_path), strict=False)
        except Exception as exc:
            return DocumentOcrResult(
                overall_status=DocumentOcrStatus.OCR_FAILED,
                warnings=[f"Could not open PDF for OCR: {exc}"],
            )

        total_pages = len(reader.pages)
        if total_pages == 0:
            return DocumentOcrResult(
                overall_status=DocumentOcrStatus.OCR_FAILED,
                warnings=["PDF has 0 pages."],
            )

        page_results: list[PageOcrResult] = []
        doc_warnings: list[str] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            # Check if page already has selectable text
            existing_text = (page.extract_text() or "").strip()
            if existing_text:
                # Text already present; preserve it as OCR completed/supported
                page_results.append(
                    PageOcrResult(
                        page_number=page_idx,
                        text=existing_text,
                        status=DocumentOcrStatus.OCR_COMPLETED,
                    )
                )
                continue

            # Extract embedded images on this page
            extracted_images: list[bytes] = []
            try:
                for img_obj in page.images:
                    extracted_images.append(img_obj.data)
            except Exception as img_exc:
                logger.debug("Failed reading page %d images: %s", page_idx, img_exc)

            if not extracted_images:
                # Scanned page without extracted images or blank page
                page_results.append(
                    PageOcrResult(
                        page_number=page_idx,
                        text="",
                        status=DocumentOcrStatus.NEEDS_MANUAL_REVIEW,
                        warnings=[f"Page {page_idx} appears blank or contains unreadable raster data."],
                    )
                )
                continue

            # OCR each image on the page
            page_text_parts: list[str] = []
            page_status = DocumentOcrStatus.OCR_COMPLETED
            for img_bytes in extracted_images:
                res = self.process_image_data(img_bytes, page_number=page_idx)
                if res.text:
                    page_text_parts.append(res.text)
                if res.status == DocumentOcrStatus.OCR_FAILED:
                    page_status = DocumentOcrStatus.OCR_FAILED

            combined_page_text = "\n\n".join(page_text_parts).strip()
            if not combined_page_text:
                page_status = DocumentOcrStatus.NEEDS_MANUAL_REVIEW

            page_results.append(
                PageOcrResult(
                    page_number=page_idx,
                    text=combined_page_text,
                    status=page_status,
                )
            )

        # Aggregate overall status
        successful_pages = sum(1 for p in page_results if p.status == DocumentOcrStatus.OCR_COMPLETED and p.text)
        failed_pages = sum(1 for p in page_results if p.status == DocumentOcrStatus.OCR_FAILED)

        if successful_pages == len(page_results):
            overall = DocumentOcrStatus.OCR_COMPLETED
        elif successful_pages > 0:
            overall = DocumentOcrStatus.OCR_COMPLETED
            doc_warnings.append(f"Partial OCR: {successful_pages}/{len(page_results)} pages contained extractable text.")
        elif failed_pages == len(page_results):
            overall = DocumentOcrStatus.OCR_FAILED
            doc_warnings.append("OCR failed on all pages.")
        else:
            overall = DocumentOcrStatus.NEEDS_MANUAL_REVIEW
            doc_warnings.append("No extractable characters found across pages. Requires manual review.")

        total_chars = sum(len(p.text) for p in page_results)

        return DocumentOcrResult(
            pages=page_results,
            overall_status=overall,
            total_characters=total_chars,
            page_count=total_pages,
            warnings=doc_warnings,
            metadata={
                "successful_pages": successful_pages,
                "total_pages": total_pages,
                "engine": self.engine.__class__.__name__,
            },
        )

