"""Evaluation metrics and validators for grounded RAG responses.

Separates automated quantitative metrics from qualitative review criteria.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.rag import RAGCitation, RAGResponse
from app.services.rag_context import EvidenceSource

_CITATION_LABEL_RE = re.compile(r"^S[1-9][0-9]*$")


@dataclass(frozen=True)
class CitationAudit:
    """Detailed audit for a single citation returned in a RAG response."""

    citation_id: str
    is_valid_format: bool
    is_in_retrieved_evidence: bool
    metadata_matches_source: bool
    excerpt_in_chunk: bool

    @property
    def is_valid(self) -> bool:
        return (
            self.is_valid_format
            and self.is_in_retrieved_evidence
            and self.metadata_matches_source
            and self.excerpt_in_chunk
        )


@dataclass(frozen=True)
class QueryRAGEvaluation:
    """Evaluation result for a single test query."""

    query_id: str
    question: str
    expected_status: str
    actual_status: str
    status_match: bool
    retrieval_success: bool
    total_citations: int
    valid_citations: int
    citation_validity_rate: float
    citation_audits: list[CitationAudit]
    citation_integrity_verified: bool
    claim_support_assessed: bool
    claim_support_verified: bool
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RAGEvaluationSummary:
    """Aggregated quantitative metrics across an evaluation dataset."""

    total_queries: int
    status_match_count: int
    status_accuracy: float
    retrieval_success_count: int
    retrieval_success_rate: float
    total_citations_returned: int
    valid_citations_returned: int
    overall_citation_validity_rate: float
    citation_integrity_verified_count: int
    citation_integrity_rate: float
    claim_support_assessed: bool
    claim_support_verified_count: int
    per_status_breakdown: dict[str, dict[str, int]]
    query_evaluations: list[QueryRAGEvaluation]


def audit_citation(
    citation: RAGCitation,
    evidence_sources: list[EvidenceSource],
) -> CitationAudit:
    """Audit one citation against the evidence presented to the LLM."""
    format_valid = bool(_CITATION_LABEL_RE.match(citation.citation_id))

    matching_sources = [
        src for src in evidence_sources if src.source_id == citation.citation_id
    ]
    if not matching_sources:
        return CitationAudit(
            citation_id=citation.citation_id,
            is_valid_format=format_valid,
            is_in_retrieved_evidence=False,
            metadata_matches_source=False,
            excerpt_in_chunk=False,
        )

    matched = matching_sources[0]
    meta = matched.result.metadata
    metadata_match = (
        citation.chunk_id == matched.result.chunk_id
        and citation.document_id == matched.result.document_id
        and citation.filename == meta.filename
        and citation.source_type == meta.source_type
        and citation.chunk_index == meta.chunk_index
        and citation.page_number == meta.page_number
        and citation.page_numbers == list(meta.page_numbers)
    )

    clean_excerpt = " ".join(citation.excerpt.rstrip(".").split()).lower()
    clean_chunk = " ".join(matched.result.text.split()).lower()
    excerpt_in_chunk = clean_excerpt in clean_chunk if clean_excerpt else True

    return CitationAudit(
        citation_id=citation.citation_id,
        is_valid_format=format_valid,
        is_in_retrieved_evidence=True,
        metadata_matches_source=metadata_match,
        excerpt_in_chunk=excerpt_in_chunk,
    )


def evaluate_rag_response(
    query_item: dict[str, Any],
    response: RAGResponse,
    evidence_sources: list[EvidenceSource],
) -> QueryRAGEvaluation:
    """Evaluate one RAG execution against dataset expectations."""
    query_id = query_item.get("id", "unknown")
    question = query_item.get("query", response.question)
    expected_status = query_item.get("expected_status", "supported")
    actual_status = response.evidence_status

    status_match = actual_status == expected_status

    expected_markers = query_item.get("expected_markers", [])
    if expected_markers:
        combined_evidence = " ".join(
            src.result.text for src in evidence_sources
        ).lower()
        retrieval_success = any(
            marker.lower() in combined_evidence for marker in expected_markers
        )
    elif expected_status == "no_relevant_sources":
        retrieval_success = not evidence_sources
    else:
        retrieval_success = True

    audits = [
        audit_citation(cit, evidence_sources) for cit in response.citations
    ]
    total_cit = len(audits)
    valid_cit = sum(1 for a in audits if a.is_valid)
    validity_rate = (valid_cit / total_cit) if total_cit > 0 else 1.0

    notes: list[str] = []
    if not status_match:
        notes.append(
            f"Status mismatch: expected '{expected_status}', got '{actual_status}'"
        )
    if total_cit != valid_cit:
        notes.append(f"{total_cit - valid_cit} invalid citations detected")

    citation_integrity = True
    if actual_status == "supported" and total_cit == 0:
        citation_integrity = False
        notes.append("Supported status returned without any citations")
    if not all(a.is_valid for a in audits):
        citation_integrity = False
        notes.append("Answer contains at least one invalid citation")
    for cit in response.citations:
        marker = f"[{cit.citation_id}]"
        if marker not in response.answer:
            citation_integrity = False
            notes.append(f"Citation marker {marker} missing from answer text")
    notes.append("Claim-level support was not assessed.")

    return QueryRAGEvaluation(
        query_id=query_id,
        question=question,
        expected_status=expected_status,
        actual_status=actual_status,
        status_match=status_match,
        retrieval_success=retrieval_success,
        total_citations=total_cit,
        valid_citations=valid_cit,
        citation_validity_rate=validity_rate,
        citation_audits=audits,
        citation_integrity_verified=citation_integrity,
        claim_support_assessed=False,
        claim_support_verified=False,
        notes=notes,
    )


def summarize_rag_evaluations(
    evaluations: list[QueryRAGEvaluation],
) -> RAGEvaluationSummary:
    """Aggregate individual query evaluations into summary statistics."""
    total = len(evaluations)
    if total == 0:
        return RAGEvaluationSummary(
            total_queries=0,
            status_match_count=0,
            status_accuracy=0.0,
            retrieval_success_count=0,
            retrieval_success_rate=0.0,
            total_citations_returned=0,
            valid_citations_returned=0,
            overall_citation_validity_rate=0.0,
            citation_integrity_verified_count=0,
            citation_integrity_rate=0.0,
            claim_support_assessed=False,
            claim_support_verified_count=0,
            per_status_breakdown={},
            query_evaluations=[],
        )

    status_match_count = sum(1 for e in evaluations if e.status_match)
    retrieval_success_count = sum(1 for e in evaluations if e.retrieval_success)
    total_citations = sum(e.total_citations for e in evaluations)
    valid_citations = sum(e.valid_citations for e in evaluations)
    citation_integrity_count = sum(
        1 for e in evaluations if e.citation_integrity_verified
    )

    breakdown: dict[str, dict[str, int]] = {}
    for ev in evaluations:
        exp = ev.expected_status
        if exp not in breakdown:
            breakdown[exp] = {"total": 0, "correct": 0}
        breakdown[exp]["total"] += 1
        if ev.status_match:
            breakdown[exp]["correct"] += 1

    overall_validity = (
        (valid_citations / total_citations) if total_citations > 0 else 1.0
    )

    return RAGEvaluationSummary(
        total_queries=total,
        status_match_count=status_match_count,
        status_accuracy=status_match_count / total,
        retrieval_success_count=retrieval_success_count,
        retrieval_success_rate=retrieval_success_count / total,
        total_citations_returned=total_citations,
        valid_citations_returned=valid_citations,
        overall_citation_validity_rate=overall_validity,
        citation_integrity_verified_count=citation_integrity_count,
        citation_integrity_rate=citation_integrity_count / total,
        claim_support_assessed=False,
        claim_support_verified_count=0,
        per_status_breakdown=breakdown,
        query_evaluations=evaluations,
    )
