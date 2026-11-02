"""Modular text extraction for the supported document formats.

Each extractor returns pages (PDF, Image) or one page-less unit (TXT/Markdown) and
keeps failures explicit.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from app.services.ingestion_errors import (
    DocumentExtractionError,
    DocumentValidationError,
    EncryptedDocumentError,
)
from app.services.ocr_service import OcrService


@dataclass(frozen=True)
class ExtractedPage:
    """Text extracted from one source page, or one whole non-PDF document."""

    page_number: int | None
    text: str


@dataclass
class ExtractionResult:
    """Source-aware extraction output consumed by cleaning and chunking."""

    pages: list[ExtractedPage] = field(default_factory=list)
    source_type: str = ""
    warnings: list[str] = field(default_factory=list)
    requires_ocr: bool = False
    page_count: int | None = None


class DocumentExtractor(Protocol):
    """Minimal interface implemented by every document format."""

    source_type: str
    extensions: tuple[str, ...]

    def extract(self, path: Path) -> ExtractionResult: ...


def _decode_text(data: bytes) -> str:
    """Decode UTF-8 or BOM-marked UTF-16/UTF-32; reject everything else.

    Rejecting an unknown encoding is safer than silently guessing and
    corrupting legal text, names, or numeric values.
    """
    if data.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
    elif data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        encoding = "utf-32"
    else:
        encoding = "utf-8"

    try:
        text = data.decode(encoding, errors="strict")
    except (UnicodeDecodeError, LookupError) as exc:
        raise DocumentValidationError(
            "The text file is not valid UTF-8/UTF-16/UTF-32 text. "
            "Re-save it with a supported encoding."
        ) from exc

    if "\x00" in text:
        raise DocumentValidationError(
            "The text file contains binary data and cannot be processed as text."
        )
    return text


class PlainTextExtractor:
    """Safe whole-file decoding for ``.txt`` documents."""

    source_type = "txt"
    extensions = (".txt",)

    def extract(self, path: Path) -> ExtractionResult:
        text = _decode_text(path.read_bytes())
        return ExtractionResult(
            pages=[ExtractedPage(page_number=None, text=text)],
            source_type=self.source_type,
        )


class MarkdownExtractor:
    """Decodes Markdown while preserving headings and paragraph boundaries."""

    source_type = "markdown"
    extensions = (".md",)

    def extract(self, path: Path) -> ExtractionResult:
        text = _decode_text(path.read_bytes())
        return ExtractionResult(
            pages=[ExtractedPage(page_number=None, text=text)],
            source_type=self.source_type,
        )


class PdfExtractor:
    """Page-by-page PDF text extraction using the maintained ``pypdf`` library."""

    source_type = "pdf"
    extensions = (".pdf",)

    def __init__(self, ocr_service: OcrService | None = None) -> None:
        self.ocr_service = ocr_service or OcrService()

    def extract(self, path: Path, perform_ocr_if_needed: bool = False) -> ExtractionResult:
        try:
            reader = PdfReader(str(path), strict=False)
        except Exception as exc:
            raise DocumentExtractionError(
                "The PDF could not be read. It may be malformed or damaged."
            ) from exc

        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise EncryptedDocumentError(
                        "The PDF is password protected and cannot be processed."
                    )
            except EncryptedDocumentError:
                raise
            except Exception as exc:
                raise EncryptedDocumentError(
                    "The PDF is password protected and cannot be processed."
                ) from exc

        try:
            total_pages = len(reader.pages)
        except Exception as exc:
            raise DocumentExtractionError(
                "The PDF could not be read. It may be malformed or damaged."
            ) from exc

        if total_pages == 0:
            raise DocumentExtractionError("The PDF does not contain any pages.")

        pages: list[ExtractedPage] = []
        warnings: list[str] = []
        failed_pages = 0
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                failed_pages += 1
                warnings.append(f"Text extraction failed on page {page_number}.")
                text = ""
            pages.append(ExtractedPage(page_number=page_number, text=text))

        if failed_pages == total_pages:
            raise DocumentExtractionError(
                "Text could not be extracted from any page of the PDF."
            )

        requires_ocr = not any(page.text.strip() for page in pages)

        # If OCR is explicitly requested or enabled for scanned PDFs
        if requires_ocr and perform_ocr_if_needed:
            try:
                ocr_result = self.ocr_service.process_scanned_pdf(path)
                if ocr_result.total_characters > 0:
                    pages = [
                        ExtractedPage(page_number=p.page_number, text=p.text)
                        for p in ocr_result.pages
                    ]
                    requires_ocr = False
                    warnings.extend(ocr_result.warnings)
            except Exception as ocr_exc:
                warnings.append(f"Automatic OCR attempt failed: {ocr_exc}")

        if requires_ocr:
            warnings.append(
                "No extractable text was found. The PDF may be scanned and "
                "require OCR before it can be used."
            )

        return ExtractionResult(
            pages=pages,
            source_type=self.source_type,
            warnings=warnings,
            requires_ocr=requires_ocr,
            page_count=total_pages,
        )


class ImageExtractor:
    """Extracts text from standalone image documents (PNG, JPEG) via OCR."""

    source_type = "image"
    extensions = (".png", ".jpg", ".jpeg")

    def __init__(self, ocr_service: OcrService | None = None) -> None:
        self.ocr_service = ocr_service or OcrService()

    def extract(self, path: Path) -> ExtractionResult:
        data = path.read_bytes()
        res = self.ocr_service.process_image_data(data, page_number=1)
        text = res.text
        requires_ocr = not bool(text.strip())
        warnings = list(res.warnings)
        if requires_ocr and "No extractable text was found in image." not in warnings:
            warnings.append("No extractable text was found in image.")

        return ExtractionResult(
            pages=[ExtractedPage(page_number=1, text=text)],
            source_type=self.source_type,
            warnings=warnings,
            requires_ocr=requires_ocr,
            page_count=1,
        )


_EXTRACTORS: tuple[DocumentExtractor, ...] = (
    PdfExtractor(),
    PlainTextExtractor(),
    MarkdownExtractor(),
    ImageExtractor(),
)

_EXTRACTOR_BY_EXTENSION: dict[str, DocumentExtractor] = {
    extension: extractor
    for extractor in _EXTRACTORS
    for extension in extractor.extensions
}


def get_extractor(extension: str) -> DocumentExtractor:
    """Return the extractor registered for a normalized extension."""
    try:
        return _EXTRACTOR_BY_EXTENSION[extension.lower()]
    except KeyError as exc:
        raise DocumentExtractionError(
            f"No extractor is available for '{extension}'."
        ) from exc


def supported_extensions() -> frozenset[str]:
    return frozenset(_EXTRACTOR_BY_EXTENSION)
