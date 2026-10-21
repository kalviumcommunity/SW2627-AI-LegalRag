"""Phase 4 retrieval metric and evaluation-dataset tests."""

from __future__ import annotations

import pytest

from app.services.retrieval_evaluation import (
    QueryEvaluation,
    evaluate_ranking,
    summarize,
)
from evaluation.dataset import (
    document_bytes,
    document_text,
    load_dataset,
    validate_dataset,
)


# --- Metric formulas ---------------------------------------------------------


def test_hit_recall_precision_and_mrr_for_a_mixed_ranking():
    metrics = evaluate_ranking(
        ["chk_a", "chk_b", "chk_c"],
        {"chk_b", "chk_d"},
        k=3,
    )

    assert metrics.hit_at_k == 1.0
    assert metrics.recall_at_k == pytest.approx(0.5)
    assert metrics.precision_at_k == pytest.approx(1 / 3)
    assert metrics.reciprocal_rank == pytest.approx(0.5)
    assert metrics.retrieved_count == 3
    assert metrics.relevant_count == 2


def test_metrics_respect_the_cutoff():
    metrics = evaluate_ranking(
        ["chk_a", "chk_b", "chk_c"],
        {"chk_b"},
        k=1,
    )

    assert metrics.hit_at_k == 0.0
    assert metrics.recall_at_k == 0.0
    assert metrics.precision_at_k == 0.0
    assert metrics.reciprocal_rank == 0.0


def test_duplicate_retrieved_ids_are_counted_once():
    metrics = evaluate_ranking(
        ["chk_a", "chk_a", "chk_b"],
        {"chk_b"},
        k=3,
    )

    assert metrics.hit_at_k == 1.0
    assert metrics.recall_at_k == 1.0
    assert metrics.precision_at_k == pytest.approx(0.5)
    assert metrics.reciprocal_rank == pytest.approx(0.5)


def test_empty_results_score_zero():
    metrics = evaluate_ranking([], {"chk_a"}, k=5)
    assert metrics.hit_at_k == 0.0
    assert metrics.recall_at_k == 0.0
    assert metrics.precision_at_k == 0.0
    assert metrics.reciprocal_rank == 0.0


def test_query_with_no_relevant_evidence_scores_zero():
    metrics = evaluate_ranking(
        ["chk_a", "chk_b"], set(), k=5
    )
    assert metrics.hit_at_k == 0.0
    assert metrics.recall_at_k == 0.0
    assert metrics.precision_at_k == 0.0
    assert metrics.reciprocal_rank == 0.0
    assert metrics.retrieved_count == 2
    assert metrics.relevant_count == 0


def test_precision_uses_actual_returned_count_when_fewer_than_k():
    metrics = evaluate_ranking(["chk_a"], {"chk_a", "chk_b"}, k=5)
    assert metrics.recall_at_k == pytest.approx(0.5)
    assert metrics.precision_at_k == 1.0


def test_invalid_cutoff_is_rejected():
    with pytest.raises(ValueError):
        evaluate_ranking(["chk_a"], {"chk_a"}, k=0)


def test_summary_macro_averages_and_includes_no_evidence_queries():
    perfect = QueryEvaluation(
        query_id="q1",
        query="one",
        retrieved_ids=["chk_a"],
        relevant_ids=["chk_a"],
        metrics=evaluate_ranking(["chk_a"], {"chk_a"}, k=5),
    )
    no_evidence = QueryEvaluation(
        query_id="q2",
        query="two",
        retrieved_ids=["chk_b"],
        relevant_ids=[],
        metrics=evaluate_ranking(["chk_b"], set(), k=5),
    )

    summary = summarize("test", 5, [perfect, no_evidence])

    assert summary.query_count == 2
    assert summary.hit_at_k == pytest.approx(0.5)
    assert summary.recall_at_k == pytest.approx(0.5)
    assert summary.precision_at_k == pytest.approx(0.5)
    assert summary.mrr == pytest.approx(0.5)


# --- Evaluation dataset ------------------------------------------------------


def test_evaluation_dataset_is_valid_and_grounded():
    dataset = load_dataset()
    assert validate_dataset(dataset) == []
    assert len(dataset["documents"]) >= 5
    assert len(dataset["queries"]) >= 8
    assert any(
        not query["relevant_markers"] for query in dataset["queries"]
    )


def test_every_relevant_marker_appears_in_the_corpus():
    dataset = load_dataset()
    corpus = "\n\n".join(
        document_text(document) for document in dataset["documents"]
    ).lower()
    for query in dataset["queries"]:
        for marker in query["relevant_markers"]:
            assert marker.lower() in corpus


def test_evaluation_documents_materialize_to_upload_bytes():
    dataset = load_dataset()
    for document in dataset["documents"]:
        data, content_type = document_bytes(document)
        assert data
        if document["format"] == "pdf":
            assert data.startswith(b"%PDF")
            assert content_type == "application/pdf"
        else:
            assert content_type in {"text/plain", "text/markdown"}


def test_evaluation_covers_cross_document_and_page_queries():
    dataset = load_dataset()
    cross_document = next(
        query
        for query in dataset["queries"]
        if query["id"] == "title_and_loans_cross_document"
    )
    page_query = next(
        query
        for query in dataset["queries"]
        if query["id"] == "title_chain_page_two"
    )
    assert len(cross_document["relevant_markers"]) == 2
    assert page_query["filters"]["page_number"] == 2
    assert page_query["filters"]["source_filename"] == "title_chain.pdf"
