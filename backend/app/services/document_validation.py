"""Upload validation: filename, size, extension, MIME type, and signature.

Client-provided metadata is never trusted on its own. Filenames are reduced to
a safe display basename, and file contents are checked for the expected format
before any extraction happens.
"""

from __future__ import annotations

import codecs
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.config import Settings
from app.services.ingestion_errors import (
    DocumentTooLargeError,
    DocumentValidationError,
    UnsupportedDocumentTypeError,
)
from app.services.text_extraction import get_extractor, supported_extensions

_ALLOWED_MIME_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf", "application/x-pdf"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/x-markdown", "text/plain"}),
}
_GENERIC_MIME_TYPES = frozenset(
    {"", "application/octet-stream", "binary/octet-stream"}
)
_CONTROL_AND_PATH_CHARS_RE = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')
_WHITESPACE_RE = re.compile(r"\s+")
_BINARY_CONTROL_BYTES = frozenset(
    {*range(0, 9), 11, 12, *range(14, 32), 127}
)


@dataclass(frozen=True)
class ValidatedUpload:
    """A validated upload with a safe filename and detected source type."""

    filename: str
    extension: str
    source_type: str
    content_type: str | None
    data: bytes


def sanitize_filename(raw_filename: str | None) -> str:
    """Return a safe display basename, never a path.

    Both POSIX and Windows separators are treated as path components, control
    characters and Windows-reserved punctuation are replaced, and length is
    bounded while preserving the extension.
    """
    if not raw_filename or not raw_filename.strip():
        return "upload"

    # Reduce to the final component regardless of separator style.
    candidate = raw_filename.replace("\\", "/").split("/")[-1]
    candidate = unicodedata.normalize("NFKC", candidate)
    candidate = _CONTROL_AND_PATH_CHARS_RE.sub("_", candidate)
    candidate = _WHITESPACE_RE.sub(" ", candidate).strip(" .")

    if not candidate or candidate in {".", ".."}:
        return "upload"

    if len(candidate) > 255:
        stem, dot, extension = candidate.rpartition(".")
        if dot and len(extension) <= 20:
            keep = max(1, 255 - len(extension) - 1)
            candidate = f"{stem[:keep]}.{extension}"
        else:
            candidate = candidate[:255]
    return candidate


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _validate_content_type(extension: str, content_type: str | None) -> None:
    normalized = _normalize_content_type(content_type)
    if normalized in _GENERIC_MIME_TYPES:
        return
    allowed = _ALLOWED_MIME_TYPES.get(extension, frozenset())
    if normalized not in allowed:
        raise UnsupportedDocumentTypeError(
            f"Content type '{normalized}' is not valid for '{extension}' files."
        )


def _validate_signature(extension: str, data: bytes) -> None:
    if extension == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise DocumentValidationError(
                "The uploaded file is not a valid PDF (missing PDF signature)."
            )
        return

    # TXT/Markdown: reject binary-looking payloads, while allowing BOM-marked
    # UTF-16/UTF-32 where NUL bytes are part of the encoding.
    if data.startswith(
        (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)
    ):
        return

    sample = data[:4096]
    if b"\x00" in sample:
        raise DocumentValidationError(
            "The uploaded file contains binary data and is not a text document."
        )
    if sample:
        control_bytes = sum(1 for byte in sample if byte in _BINARY_CONTROL_BYTES)
        if control_bytes / len(sample) > 0.05:
            raise DocumentValidationError(
                "The uploaded file does not look like a text document."
            )


def validate_upload(
    data: bytes,
    filename: str | None,
    content_type: str | None,
    settings: Settings,
) -> ValidatedUpload:
    """Validate size, name, extension, MIME type, and magic signature."""
    if not data:
        raise DocumentValidationError("The uploaded file is empty.")

    if len(data) > settings.document_max_upload_bytes:
        raise DocumentTooLargeError(
            f"The upload exceeds the {settings.document_max_upload_bytes} byte limit."
        )

    safe_filename = sanitize_filename(filename)
    extension = PurePosixPath(safe_filename).suffix.lower()
    if not extension:
        raise UnsupportedDocumentTypeError(
            "The file has no extension. Supported formats: PDF, TXT, Markdown."
        )

    configured = settings.allowed_document_extensions
    if extension.lstrip(".") not in configured or extension not in supported_extensions():
        allowed = ", ".join(sorted(f".{item}" for item in configured)) or "none"
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type '{extension}'. Allowed types: {allowed}."
        )

    _validate_content_type(extension, content_type)
    _validate_signature(extension, data)

    extractor = get_extractor(extension)
    return ValidatedUpload(
        filename=safe_filename,
        extension=extension,
        source_type=extractor.source_type,
        content_type=content_type,
        data=data,
    )
