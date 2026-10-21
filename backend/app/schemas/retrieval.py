"""Pydantic schemas for semantic and hybrid retrieval."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.documents import SourceType

RetrievalMode = Literal["semantic", "hybrid"]
ScoreType = Literal["cosine_similarity", "reciprocal_rank_fusion"]


class RetrievalFilters(BaseModel):
    """Optional metadata filters applied inside the database query.

    Property-level associations are not part of the Phase 2/3 schema, so filters
    are document/chunk-level only. Unknown fields are rejected rather than
    silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    source_filename: str | None = Field(
        default=None,
        max_length=255,
        description="Exact sanitized source filename, for example 'sale_deed.pdf'.",
    )
    source_type: SourceType | None = Field(
        default=None,
        description="Normalized source format: pdf, txt, or markdown.",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Match chunks associated with this PDF page. Chunks spanning "
            "multiple pages have a null page_number but are matched through "
            "their metadata.page_numbers list."
        ),
    )

    @field_validator("source_filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source_filename must not be blank")
        return cleaned


class RetrievalSearchRequest(BaseModel):
    """A natural-language retrieval query."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Natural-language property-intelligence question.",
        examples=["What legal documents are available for this property?"],
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of chunks to return. When omitted, "
            "RETRIEVAL_DEFAULT_TOP_K (default 5) is used. Values above "
            "RETRIEVAL_MAX_TOP_K (default 50) are rejected."
        ),
    )
    mode: RetrievalMode = Field(
        default="semantic",
        description=(
            "'semantic' uses pgvector cosine similarity. 'hybrid' fuses "
            "semantic and PostgreSQL full-text rankings with reciprocal rank "
            "fusion (RRF)."
        ),
    )
    document_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional exact document ID filter.",
    )
    filters: RetrievalFilters = Field(
        default_factory=RetrievalFilters,
        description="Optional document/chunk metadata filters.",
    )
    min_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description=(
            "Optional minimum cosine similarity in [-1, 1]. Higher is better. "
            "In hybrid mode this threshold is applied to the semantic "
            "candidate list before fusion; keyword-only matches are not "
            "thresholded because their scores are on a different scale."
        ),
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("query must not be empty or whitespace-only")
        return cleaned

    @field_validator("document_id")
    @classmethod
    def document_id_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("document_id must not be blank")
        return cleaned


class RetrievalResultMetadata(BaseModel):
    """Source information retained for later citation/grounded generation."""

    filename: str
    source_type: SourceType
    page_number: int | None = Field(
        default=None,
        description=(
            "Set only when the chunk lies on exactly one page, matching "
            "Phase 2 semantics."
        ),
    )
    page_numbers: list[int] = Field(
        default_factory=list,
        description="All pages touched by the chunk (from Phase 2 metadata).",
    )
    chunk_index: int = Field(ge=0)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Full Phase 2 chunk metadata for traceability.",
    )


class RetrievalResult(BaseModel):
    """One retrieved chunk and its ranking information."""

    chunk_id: str
    document_id: str
    text: str = Field(description="Cleaned chunk text from PostgreSQL.")
    score: float = Field(
        description=(
            "Ranking score. For semantic mode this is cosine similarity "
            "(higher is better). For hybrid mode this is an RRF score "
            "(higher is better); values from different modes are not "
            "comparable."
        )
    )
    score_type: ScoreType
    distance: float | None = Field(
        default=None,
        description=(
            "Raw pgvector cosine distance for semantic candidates "
            "(lower is better; similarity = 1 - distance). Null for "
            "keyword-only hybrid results."
        ),
    )
    semantic_score: float | None = Field(
        default=None,
        description="Cosine similarity component in hybrid results.",
    )
    keyword_rank: int | None = Field(
        default=None,
        description="One-based PostgreSQL full-text rank position in hybrid mode.",
    )
    metadata: RetrievalResultMetadata


class RetrievalSearchResponse(BaseModel):
    """Ordered retrieval result set."""

    query: str
    mode: RetrievalMode
    results: list[RetrievalResult] = Field(default_factory=list)
    result_count: int = Field(ge=0)
