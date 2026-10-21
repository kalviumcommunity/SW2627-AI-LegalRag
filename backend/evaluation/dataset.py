"""Load, validate, and materialize the Phase 4 retrieval evaluation corpus.

The corpus is synthetic and original. It is intentionally small so evaluation
runs are fast and every expected relevant chunk can be traced to a phrase in a
source document.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

DATASET_PATH = Path(__file__).with_name("retrieval_dataset.json")
ALLOWED_FILTER_FIELDS = {
    "source_filename",
    "source_type",
    "page_number",
}
ALLOWED_SOURCE_TYPES = {"pdf", "txt", "markdown"}


def load_dataset(path: Path | None = None) -> dict[str, Any]:
    with (path or DATASET_PATH).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def document_text(document: dict[str, Any]) -> str:
    if "content" in document:
        return document["content"]
    return "\n\n".join(document.get("pages") or [])


def document_bytes(document: dict[str, Any]) -> tuple[bytes, str]:
    """Return upload bytes and a matching content type."""
    document_format = document["format"]
    if document_format == "pdf":
        return make_pdf(document["pages"]), "application/pdf"
    text = document["content"]
    if document_format == "md":
        return text.encode("utf-8"), "text/markdown"
    return text.encode("utf-8"), "text/plain"


def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    """Return human-readable problems; an empty list means the corpus is usable."""
    errors: list[str] = []
    documents = dataset.get("documents")
    queries = dataset.get("queries")
    if not isinstance(documents, list) or not documents:
        return ["documents must be a non-empty list"]
    if not isinstance(queries, list) or not queries:
        return ["queries must be a non-empty list"]

    document_keys: set[str] = set()
    filenames: set[str] = set()
    for index, document in enumerate(documents):
        label = f"documents[{index}]"
        key = document.get("key")
        filename = document.get("filename")
        if not isinstance(key, str) or not key:
            errors.append(f"{label}.key must be a non-empty string")
        elif key in document_keys:
            errors.append(f"duplicate document key: {key}")
        else:
            document_keys.add(key)
        if not isinstance(filename, str) or not filename:
            errors.append(f"{label}.filename must be a non-empty string")
        elif filename in filenames:
            errors.append(f"duplicate document filename: {filename}")
        else:
            filenames.add(filename)
        document_format = document.get("format")
        if document_format not in {"pdf", "txt", "md"}:
            errors.append(f"{label}.format must be pdf, txt, or md")
        elif document_format == "pdf":
            pages = document.get("pages")
            if (
                not isinstance(pages, list)
                or not pages
                or not all(isinstance(page, str) and page.strip() for page in pages)
            ):
                errors.append(f"{label}.pages must be a non-empty string list")
        else:
            content = document.get("content")
            if not isinstance(content, str) or not content.strip():
                errors.append(f"{label}.content must be non-empty text")

    combined_text = "\n\n".join(
        document_text(document) for document in documents
    ).lower()
    query_ids: set[str] = set()
    for index, query in enumerate(queries):
        label = f"queries[{index}]"
        query_id = query.get("id")
        if not isinstance(query_id, str) or not query_id:
            errors.append(f"{label}.id must be a non-empty string")
        elif query_id in query_ids:
            errors.append(f"duplicate query id: {query_id}")
        else:
            query_ids.add(query_id)
        text = query.get("query")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{label}.query must be non-empty text")
        markers = query.get("relevant_markers")
        if not isinstance(markers, list) or not all(
            isinstance(marker, str) and marker.strip() for marker in markers
        ):
            errors.append(f"{label}.relevant_markers must be a string list")
            markers = []
        for marker in markers:
            if marker.lower() not in combined_text:
                errors.append(
                    f"{label} marker is not grounded in the corpus: {marker!r}"
                )
        filters = query.get("filters", {})
        if not isinstance(filters, dict):
            errors.append(f"{label}.filters must be an object")
            continue
        unknown = set(filters) - ALLOWED_FILTER_FIELDS
        if unknown:
            errors.append(
                f"{label}.filters has unsupported fields: {sorted(unknown)}"
            )
        if "source_filename" in filters and filters["source_filename"] not in filenames:
            errors.append(
                f"{label}.filters.source_filename is not in the corpus"
            )
        if (
            "source_type" in filters
            and filters["source_type"] not in ALLOWED_SOURCE_TYPES
        ):
            errors.append(f"{label}.filters.source_type is invalid")
        page_number = filters.get("page_number")
        if page_number is not None and (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
        ):
            errors.append(f"{label}.filters.page_number must be >= 1")
    return errors


def make_pdf(pages: list[str]) -> bytes:
    """Create a text-based PDF with one content stream per page."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_ref}
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(_content_stream(text))
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _content_stream(text: str) -> bytes:
    lines = text.split("\n") if text else []
    parts = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            parts.append("0 -16 Td")
        parts.append(f"({_escape_pdf_text(line)}) Tj")
    parts.append("ET")
    return " ".join(parts).encode("latin-1")


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
