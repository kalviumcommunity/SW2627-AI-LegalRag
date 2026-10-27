"""Pydantic schemas for document ingestion and chunk responses."""

from datetime import datetime
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


class DocumentSummary(BaseModel):
    """Summary metadata for an ingested document in paginated listings."""

    document_id: str = Field(..., description="Stable document identifier.")
    filename: str = Field(..., description="Sanitized upload filename.")
    source_type: SourceType = Field(..., description="Normalized source format.")
    status: IngestionStatus = Field(..., description="Processing status.")
    extracted_characters: int = Field(..., ge=0, description="Total characters extracted.")
    chunk_count: int = Field(..., ge=0, description="Total chunks stored.")
    page_count: int | None = Field(default=None, ge=0, description="Total pages if paginated.")
    warnings: list[str] = Field(default_factory=list, description="Warnings recorded during processing.")
    detail: str | None = Field(default=None, description="Detailed processing status or explanation.")
    created_at: datetime | None = Field(default=None, description="When the document record was created.")
    updated_at: datetime | None = Field(default=None, description="When the document record was last updated.")


class DocumentDetailResponse(BaseModel):
    """Full document metadata and processing status without chunk contents."""

    document_id: str = Field(..., description="Stable document identifier.")
    filename: str = Field(..., description="Sanitized upload filename.")
    source_type: SourceType = Field(..., description="Normalized source format.")
    status: IngestionStatus = Field(..., description="Processing status.")
    content_sha256: str = Field(..., description="SHA-256 hash of the upload contents.")
    extracted_characters: int = Field(..., ge=0, description="Total characters extracted.")
    chunk_count: int = Field(..., ge=0, description="Total chunks stored.")
    page_count: int | None = Field(default=None, ge=0, description="Total pages if paginated.")
    warnings: list[str] = Field(default_factory=list, description="Warnings recorded during processing.")
    detail: str | None = Field(default=None, description="Detailed processing status or explanation.")
    created_at: datetime | None = Field(default=None, description="When the document record was created.")
    updated_at: datetime | None = Field(default=None, description="When the document record was last updated.")


class DocumentListResponse(BaseModel):
    """Paginated list of document summaries."""

    items: list[DocumentSummary] = Field(default_factory=list, description="Matching document summaries.")
    total: int = Field(..., ge=0, description="Total matching documents.")
    page: int = Field(..., ge=1, description="Current page number.")
    page_size: int = Field(..., ge=1, description="Maximum items per page.")
    total_pages: int = Field(..., ge=0, description="Total number of pages.")


class DocumentChunkSummary(BaseModel):
    """Traceable chunk metadata for inspection."""

    chunk_id: str = Field(..., description="Generated chunk identifier.")
    document_id: str = Field(..., description="Source document identifier.")
    chunk_index: int = Field(..., ge=0, description="Zero-based chunk position.")
    source_filename: str = Field(..., description="Sanitized upload filename.")
    source_type: SourceType = Field(..., description="Normalized source format.")
    page_number: int | None = Field(default=None, ge=1, description="Page number if single page.")
    start_offset: int | None = Field(default=None, ge=0, description="Start offset in cleaned text.")
    end_offset: int | None = Field(default=None, ge=0, description="End offset in cleaned text.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata.")
    text: str | None = Field(
        default=None,
        description="Chunk text, included only when requested (include_text=true).",
    )


class DocumentChunkListResponse(BaseModel):
    """Paginated chunk metadata for a document."""

    document_id: str = Field(..., description="Source document identifier.")
    items: list[DocumentChunkSummary] = Field(default_factory=list, description="Matching chunk metadata.")
    total: int = Field(..., ge=0, description="Total chunks for this document.")
    page: int = Field(..., ge=1, description="Current page number.")
    page_size: int = Field(..., ge=1, description="Maximum items per page.")
    total_pages: int = Field(..., ge=0, description="Total number of pages.")


class DocumentDeleteResponse(BaseModel):
    """Confirmation of document deletion and cascading cleanup."""

    document_id: str = Field(..., description="Identifier of the deleted document.")
    deleted: bool = Field(default=True, description="True if deletion succeeded.")
    message: str = Field(
        default="Document and associated chunks deleted successfully.",
        description="Human-readable status message.",
    )
