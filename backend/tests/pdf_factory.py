"""Synthetic PDF fixtures built with pypdf (no external services)."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(text: str) -> bytes:
    lines = text.split("\n") if text else []
    parts = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            parts.append("0 -16 Td")
        parts.append(f"({_escape_pdf_text(line)}) Tj")
    parts.append("ET")
    return " ".join(parts).encode("latin-1")


def make_pdf(pages: list[str], password: str | None = None) -> bytes:
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

    if password:
        writer.encrypt(password)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
