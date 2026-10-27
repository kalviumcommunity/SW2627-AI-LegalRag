"""Pydantic schemas for grounded retrieval-augmented generation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.documents import SourceType
from app.schemas.retrieval import RetrievalFilters, RetrievalMode

EvidenceStatus = Literal[
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "no_relevant_sources",
]


class RAGQuestionRequest(BaseModel):
    """A single property-intelligence question over stored documents."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description=(
            "Natural-language question. The service applies the lower "
            "RAG_MAX_QUESTION_CHARS limit at request time."
        ),
        examples=["What does the sale deed say about the property boundaries?"],
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum retrieval candidates. Capped by RAG_MAX_EVIDENCE_CHUNKS "
            "before the LLM call."
        ),
    )
    mode: RetrievalMode = Field(
        default="semantic",
        description=(
            "'semantic' uses cosine similarity; 'hybrid' fuses semantic and "
            "full-text ranks with reciprocal rank fusion."
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
            "Optional semantic similarity threshold applied by retrieval. "
            "Hybrid keyword-only matches are not thresholded."
        ),
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("question must not be empty or whitespace-only")
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


class RAGCitation(BaseModel):
    """A citation that is guaranteed to map to retrieved evidence."""

    citation_id: str = Field(
        pattern=r"^S[1-9][0-9]*$",
        description="Stable evidence label used in the answer, for example 'S1'.",
    )
    chunk_id: str
    document_id: str
    filename: str
    source: str | None = Field(
        default=None,
        description="Source filename or title, for convenient display.",
    )
    source_type: SourceType
    page_number: int | None = Field(
        default=None,
        description="Present only when the chunk lies on exactly one page.",
    )
    page_numbers: list[int] = Field(
        default_factory=list,
        description="All pages touched by a multi-page chunk.",
    )
    chunk_index: int = Field(ge=0)
    excerpt: str = Field(
        description=(
            "Short extract from the cited chunk, not a generated summary."
        )
    )
    document_created_at: datetime | None = Field(
        default=None,
        description=(
            "When the source document was ingested. This is not necessarily "
            "the date the legal document was signed."
        ),
    )


class RAGResponse(BaseModel):
    """A grounded answer plus the evidence contract for that answer."""

    question: str
    answer: str
    evidence_status: EvidenceStatus
    citations: list[RAGCitation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    retrieved_count: int = Field(ge=0)
    used_chunk_count: int = Field(ge=0)
    mode: RetrievalMode
    citation_guarantee: Literal["retrieved_source_integrity"] = Field(
        default="retrieved_source_integrity",
        description=(
            "Every citation maps to a retrieved chunk and source document. "
            "This does not establish claim-level entailment."
        ),
    )
    claim_support_verified: Literal[False] = Field(
        default=False,
        description=(
            "Always false: citations are validated structurally, not by a "
            "claim-level entailment model."
        ),
    )
