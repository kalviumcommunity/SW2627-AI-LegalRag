"""Pydantic schemas for document ingestion and chunk responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["pdf", "txt", "markdown"]
IngestionStatus = Literal["processed", "ocr_required", "failed"]


class DocumentChunk(BaseModel):
    """A traceable, JSON-serializable chunk ready for later embedding."""

    chunk_id: str = Field(..., description="Generated chunk identifier.")
    document_id: str = Field(..., description="Identifier of the source document.")
    chunk_index: int = Field(..., ge=0, description="Zero-based position in the document.")
    text: str = Field(..., description="Cleaned chunk text.")
    source_filename: str = Field(..., description="Sanitized upload filename.")
    source_type: SourceType = Field(..., description="Normalized source format.")
    page_number: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Original PDF page number when the chunk lies on exactly one page. "
            "Null for multi-page chunks and non-paginated formats; use "
            "metadata.page_numbers for the full set."
        ),
    )
    start_offset: int | None = Field(
        default=None,
        ge=0,
        description="Inclusive character offset in the cleaned extracted text.",
    )
    end_offset: int | None = Field(
        default=None,
        ge=0,
        description="Exclusive character offset in the cleaned extracted text.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional JSON-serializable traceability metadata.",
    )


class IngestResponse(BaseModel):
    """Structured result returned by the ingestion endpoint."""

    document_id: str
    filename: str
    status: IngestionStatus
    extracted_characters: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    chunks: list[DocumentChunk] = Field(default_factory=list)
    page_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of PDF pages; null for TXT/Markdown.",
    )
    warnings: list[str] = Field(default_factory=list)
    detail: str | None = Field(
        default=None,
        description="Safe explanation for ocr_required or failed results.",
    )
