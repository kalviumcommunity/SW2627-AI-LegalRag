"""Tests for Phase 5 RAG evaluation tools and dataset."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.rag import RAGCitation, RAGResponse
from app.services.rag_context import EvidenceSource
from app.services.rag_evaluation import (
    audit_citation,
    evaluate_rag_response,
    summarize_rag_evaluations,
)
from evaluation.rag_harness import run_evaluation
from tests.fakes import retrieval_result

DATASET_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "rag_dataset.json"
HARNESS_PATH = (
    Path(__file__).resolve().parents[1] / "evaluation" / "rag_harness.py"
)


def test_rag_dataset_schema_and_integrity():
    assert DATASET_PATH.exists()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "documents" in data and len(data["documents"]) >= 5
    assert "queries" in data and len(data["queries"]) >= 8

    statuses = {q["expected_status"] for q in data["queries"]}
    assert "supported" in statuses
    assert "conflicting_evidence" in statuses
    assert "insufficient_evidence" in statuses
    assert "no_relevant_sources" in statuses


def test_audit_citation_valid():
    res = retrieval_result("chk_1", text="The western boundary follows the river.")
    source = EvidenceSource(source_id="S1", result=res, text=res.text)

    cit = RAGCitation(
        citation_id="S1",
        chunk_id="chk_1",
        document_id=res.document_id,
        filename=res.metadata.filename,
        source_type=res.metadata.source_type,
        page_number=res.metadata.page_number,
        page_numbers=list(res.metadata.page_numbers),
        chunk_index=res.metadata.chunk_index,
        excerpt="The western boundary follows the river",
    )

    audit = audit_citation(cit, [source])
    assert audit.is_valid is True
    assert audit.is_valid_format is True
    assert audit.is_in_retrieved_evidence is True
    assert audit.metadata_matches_source is True
    assert audit.excerpt_in_chunk is True


def test_audit_citation_detects_unretrieved_source_or_metadata_mismatch():
    res = retrieval_result("chk_1", text="The boundary follows the river.")
    source = EvidenceSource(source_id="S1", result=res, text=res.text)

    # Citation referring to unretrieved S2
    cit_missing = RAGCitation(
        citation_id="S2",
        chunk_id="chk_2",
        document_id="doc_2",
        filename="other.pdf",
        source_type="pdf",
        chunk_index=0,
        excerpt="other text",
    )
    audit1 = audit_citation(cit_missing, [source])
    assert audit1.is_valid is False
    assert audit1.is_in_retrieved_evidence is False

    # Citation with fabricated chunk_id on S1
    cit_mismatched = RAGCitation(
        citation_id="S1",
        chunk_id="fabricated_chunk_id",
        document_id=res.document_id,
        filename=res.metadata.filename,
        source_type=res.metadata.source_type,
        chunk_index=0,
        excerpt="The boundary follows the river",
    )
    audit2 = audit_citation(cit_mismatched, [source])
    assert audit2.is_valid is False
    assert audit2.metadata_matches_source is False


def test_evaluate_rag_response_and_summary():
    res = retrieval_result("chk_1", text="The registered owner is Ananya Rao.")
    source = EvidenceSource(source_id="S1", result=res, text=res.text)

    query_item = {
        "id": "q1",
        "query": "Who is the owner?",
        "expected_status": "supported",
        "expected_markers": ["Ananya Rao"],
    }

    response = RAGResponse(
        question="Who is the owner?",
        answer="The registered owner is Ananya Rao [S1].",
        evidence_status="supported",
        citations=[
            RAGCitation(
                citation_id="S1",
                chunk_id="chk_1",
                document_id=res.document_id,
                filename=res.metadata.filename,
                source_type=res.metadata.source_type,
                page_number=res.metadata.page_number,
                page_numbers=list(res.metadata.page_numbers),
                chunk_index=res.metadata.chunk_index,
                excerpt="registered owner is Ananya Rao",
            )
        ],
        limitations=[],
        retrieved_count=1,
        used_chunk_count=1,
        mode="semantic",
    )

    eval_result = evaluate_rag_response(query_item, response, [source])
    assert eval_result.status_match is True
    assert eval_result.retrieval_success is True
    assert eval_result.citation_validity_rate == 1.0
    assert eval_result.citation_integrity_verified is True
    assert eval_result.claim_support_assessed is False
    assert eval_result.claim_support_verified is False

    summary = summarize_rag_evaluations([eval_result])
    assert summary.total_queries == 1
    assert summary.status_accuracy == 1.0
    assert summary.overall_citation_validity_rate == 1.0
    assert summary.citation_integrity_rate == 1.0
    assert summary.claim_support_assessed is False
    assert summary.claim_support_verified_count == 0


def test_harness_does_not_import_application_test_doubles():
    source = HARNESS_PATH.read_text(encoding="utf-8")

    assert "tests.fakes" not in source
    assert 'item.get("expected_status"' not in source
    assert 'item.get("expected_documents"' not in source
    assert 'item.get("expected_markers"' not in source


async def test_offline_harness_exercises_real_services_without_claim_support_claims():
    summary = await run_evaluation()

    assert summary.total_queries == len(
        json.loads(DATASET_PATH.read_text(encoding="utf-8"))["queries"]
    )
    assert 0.0 <= summary.status_accuracy <= 1.0
    assert summary.citation_integrity_rate == 1.0
    assert summary.claim_support_assessed is False
    assert summary.claim_support_verified_count == 0
    assert all(
        evaluation.claim_support_verified is False
        for evaluation in summary.query_evaluations
    )
