"""Pydantic schemas for grounded retrieval-augmented generation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    verify_claims: bool = Field(
        default=True,
        description="Whether to perform claim-level evidence verification (Phase 9).",
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


ClaimVerificationStatus = Literal["supported", "contradicted", "unsupported"]


class ClaimVerification(BaseModel):
    """Result of verifying an individual factual claim against cited evidence."""

    claim: str = Field(default="", description="The factual claim statement.")
    claim_text: str = Field(default="", description="Alias for claim.")
    status: ClaimVerificationStatus = Field(
        ..., description="Verification outcome for this claim."
    )
    cited_sources: list[str] = Field(
        default_factory=list, description="Source IDs cited (e.g. ['S1'])."
    )
    cited_source_ids: list[str] = Field(
        default_factory=list, description="Alias for cited_sources."
    )
    evidence_excerpts: list[str] = Field(
        default_factory=list,
        description="Verbatim evidence text from cited passages.",
    )
    source_quotes: list[str] = Field(
        default_factory=list, description="Alias for evidence_excerpts."
    )
    reasoning: str | None = Field(
        default=None, description="Detailed reasoning or contradiction/insufficiency note."
    )
    entailment_explanation: str = Field(
        default="", description="Alias for reasoning."
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.claim_text and self.claim:
            object.__setattr__(self, "claim_text", self.claim)
        elif not self.claim and self.claim_text:
            object.__setattr__(self, "claim", self.claim_text)

        if not self.cited_source_ids and self.cited_sources:
            object.__setattr__(self, "cited_source_ids", list(self.cited_sources))
        elif not self.cited_sources and self.cited_source_ids:
            object.__setattr__(self, "cited_sources", list(self.cited_source_ids))

        if not self.source_quotes and self.evidence_excerpts:
            object.__setattr__(self, "source_quotes", list(self.evidence_excerpts))
        elif not self.evidence_excerpts and self.source_quotes:
            object.__setattr__(self, "evidence_excerpts", list(self.source_quotes))

        reasoning_text = self.reasoning or ""
        if not self.entailment_explanation and reasoning_text:
            object.__setattr__(self, "entailment_explanation", reasoning_text)
        elif not self.reasoning and self.entailment_explanation:
            object.__setattr__(self, "reasoning", self.entailment_explanation)


class ConflictSource(BaseModel):
    """Specific citation and quote contributing to a cross-document conflict."""

    document_id: str = Field(..., description="Unique document ID.")
    filename: str = Field(..., description="Source document filename.")
    citation_id: str = Field(..., description="Citation marker, e.g. 'S1'.")
    quote: str = Field(..., description="Verbatim statement from the source document.")
    page_number: int | None = Field(default=None, description="Page number if applicable.")
    page_numbers: list[int] = Field(default_factory=list, description="Page numbers if multi-page.")


class CrossDocumentConflict(BaseModel):
    """A verified material disagreement between two distinct documents."""

    topic: str = Field(
        default="general",
        description="Subject matter of conflict (e.g. 'consideration', 'area', 'encumbrance').",
    )
    description: str = Field(
        ..., description="Concise explanation of the material disagreement."
    )
    contradiction_reason: str = Field(
        default="", description="Alias for description."
    )
    source_a: ConflictSource = Field(..., description="First conflicting source document.")
    source_b: ConflictSource = Field(..., description="Second conflicting source document.")
    resolution_note: str = Field(
        default=(
            "Conflicting records across distinct documents; neither document "
            "is assumed legally authoritative without judicial or title determination."
        ),
        description="Neutral note regarding legal authoritativeness.",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.contradiction_reason and self.description:
            object.__setattr__(self, "contradiction_reason", self.description)
        elif not self.description and self.contradiction_reason:
            object.__setattr__(self, "description", self.contradiction_reason)


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
    claim_support_verified: bool = Field(
        default=False,
        description=(
            "Indicates whether claim-level evidence verification was performed."
        ),
    )
    claim_verifications: list[ClaimVerification] = Field(
        default_factory=list,
        description="Claim-level evidence verification results.",
    )
    conflicts: list[CrossDocumentConflict] = Field(
        default_factory=list,
        description="Material contradictions across distinct documents.",
    )
    insufficient_reasons: list[str] = Field(
        default_factory=list,
        description="Specific reasons why available evidence cannot establish the answer.",
    )
    legal_disclaimer: str = Field(
        default=(
            "Automated verification is provided for informational and due diligence assistance only. "
            "It does not constitute legal advice, a title guarantee, or confirmation of clear property title."
        ),
        description="Mandatory legal advice and title guarantee disclaimer.",
    )
