"""Modular text extraction for the supported document formats.

Each extractor returns pages (PDF) or one page-less unit (TXT/Markdown) and
keeps failures explicit. Adding DOCX later only requires a new extractor and a
registry entry; the rest of the ingestion pipeline stays unchanged.
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

    def extract(self, path: Path) -> ExtractionResult:
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


_EXTRACTORS: tuple[DocumentExtractor, ...] = (
    PdfExtractor(),
    PlainTextExtractor(),
    MarkdownExtractor(),
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
