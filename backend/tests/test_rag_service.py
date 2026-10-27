"""Phase 5 RAG orchestration tests. LLM and retrieval are always mocked."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.schemas.retrieval import RetrievalFilters
from app.services.llm_service import LLMRateLimitError
from app.services.rag_errors import RAGQueryError
from app.services.rag_service import RAGService
from app.services.retrieval_errors import RetrievalDatabaseError
from tests.fakes import (
    FakeLLMService,
    FakeRetrievalService,
    retrieval_result,
)

CREATED_AT = datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)


def _settings(**overrides) -> Settings:
    values = {
        "groq_api_key": "test-key-not-a-secret",
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 4,
        "retrieval_default_top_k": 3,
        "retrieval_max_top_k": 5,
        "rag_max_evidence_chunks": 3,
    }
    values.update(overrides)
    return Settings(**values)


def _service(
    *,
    results=None,
    generation: str | None = None,
    llm_error: Exception | None = None,
    retrieval_error: Exception | None = None,
    **overrides,
):
    settings = _settings(**overrides)
    retrieval = FakeRetrievalService(
        results=results,
        error=retrieval_error,
    )
    llm = FakeLLMService(
        response=generation or json.dumps(
            {
                "answer": "The deed states the boundary follows the river [S1].",
                "evidence_status": "supported",
                "used_source_ids": [1],
                "limitations": ["Only the retrieved deed excerpt was reviewed."],
            }
        ),
        error=llm_error,
    )
    service = RAGService(
        settings,
        retrieval_service=retrieval,
        llm_service=llm,
    )
    return service, retrieval, llm


def _result(chunk_id: str = "chk_1", **overrides):
    values = {
        "text": "The western boundary follows the river.",
        "filename": "sale-deed.pdf",
        "page_number": 2,
        "page_numbers": [2],
        "document_created_at": CREATED_AT,
    }
    values.update(overrides)
    return retrieval_result(chunk_id, **values)


# --- Supported answers and citations ---------------------------------------


async def test_supported_answer_maps_citations_to_retrieved_chunks():
    service, retrieval, llm = _service(
        results=[_result(page_number=None, page_numbers=[2, 3])],
    )

    response = await service.ask(
        "  What is the western boundary?  ",
        top_k=2,
        mode="hybrid",
        document_id="doc_1",
        filters=RetrievalFilters(source_filename="sale-deed.pdf"),
    )

    assert response.question == "What is the western boundary?"
    assert response.evidence_status == "supported"
    assert response.retrieved_count == 1
    assert response.used_chunk_count == 1
    assert response.mode == "hybrid"
    assert response.citation_guarantee == "retrieved_source_integrity"
    assert response.claim_support_verified is False
    assert any("claim-level entailment" in item for item in response.limitations)
    assert response.citations[0].citation_id == "S1"
    assert response.citations[0].chunk_id == "chk_1"
    assert response.citations[0].document_id == "doc_1"
    assert response.citations[0].filename == "sale-deed.pdf"
    assert response.citations[0].page_number is None
    assert response.citations[0].page_numbers == [2, 3]
    assert response.citations[0].document_created_at == CREATED_AT
    assert "western boundary" in response.citations[0].excerpt
    assert any("Only the retrieved" in item for item in response.limitations)
    assert any("not legal advice" in item for item in response.limitations)

    query, retrieval_kwargs = retrieval.calls[0]
    assert query == "What is the western boundary?"
    assert retrieval_kwargs["top_k"] == 2
    assert retrieval_kwargs["mode"] == "hybrid"
    assert retrieval_kwargs["document_id"] == "doc_1"
    assert retrieval_kwargs["filters"].source_filename == "sale-deed.pdf"
    assert llm.calls[0]["json_mode"] is True
    assert llm.calls[0]["max_tokens"] == service.settings.rag_max_output_tokens
    assert "untrusted" in llm.calls[0]["system_prompt"]
    assert "pages: 2, 3" in llm.calls[0]["user_prompt"]
    assert "ingested_at: 2025-01-02T03:04:00+00:00" in llm.calls[0]["user_prompt"]


async def test_top_k_is_capped_by_the_rag_evidence_limit():
    service, retrieval, _ = _service(results=[_result()])
    await service.ask("Boundary?", top_k=5)
    assert retrieval.calls[0][1]["top_k"] == 3


async def test_only_markers_referenced_in_a_supported_answer_are_cited():
    generation = json.dumps(
        {
            "answer": "Only the second excerpt addresses this [S2].",
            "evidence_status": "supported",
            "used_source_ids": [1, 2],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result("chk_1", text="The western boundary follows the river."),
            _result("chk_2", text="The eastern boundary follows the road."),
        ],
        generation=generation,
    )

    response = await service.ask("Question")

    assert response.evidence_status == "supported"
    assert [citation.citation_id for citation in response.citations] == ["S2"]
    assert [citation.chunk_id for citation in response.citations] == ["chk_2"]


# --- No evidence and context limits ---------------------------------------


async def test_no_retrieval_results_skip_the_llm():
    service, _, llm = _service(results=[], generation="should not be used")
    response = await service.ask("Question with no results")

    assert response.evidence_status == "no_relevant_sources"
    assert response.answer.startswith("No relevant document excerpts")
    assert response.retrieved_count == 0
    assert response.used_chunk_count == 0
    assert response.citations == []
    assert llm.calls == []


async def test_context_omissions_are_reported_and_deduplicated():
    service, _, llm = _service(
        results=[
            _result("chk_1", text="A duplicated boundary clause."),
            _result("chk_2", text="A duplicated boundary clause."),
        ],
    )
    response = await service.ask("Boundary?")

    assert response.used_chunk_count == 1
    assert any("omitted" in item for item in response.limitations)
    prompt = llm.calls[0]["user_prompt"]
    assert prompt.count("<<<EVIDENCE S1 ") == 1
    assert "<<<EVIDENCE S2 " not in prompt


# --- Citation and grounding validation ------------------------------------


async def test_supported_answer_without_a_citation_is_downgraded():
    generation = json.dumps(
        {
            "answer": "The boundary follows the river.",
            "evidence_status": "supported",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    service, _, _ = _service(results=[_result()], generation=generation)

    response = await service.ask("Boundary?")

    assert response.evidence_status == "insufficient_evidence"
    assert response.citations == []
    assert any("did not provide a citation" in item for item in response.limitations)


async def test_unknown_citation_and_source_ids_are_removed():
    generation = json.dumps(
        {
            "answer": "The river is the boundary [S99], according to the deed [S1].",
            "evidence_status": "supported",
            "used_source_ids": [1, 99],
            "limitations": [],
        }
    )
    service, _, _ = _service(results=[_result()], generation=generation)

    response = await service.ask("Boundary?")

    assert response.evidence_status == "supported"
    assert "S99" not in response.answer
    assert [citation.citation_id for citation in response.citations] == ["S1"]
    assert any("citation labels" in item for item in response.limitations)
    assert any("source IDs" in item for item in response.limitations)


async def test_conflicting_evidence_requires_two_valid_sources():
    generation = json.dumps(
        {
            "answer": "One excerpt says the property has 3 floors [S1], while "
            "another says it has 4 floors [S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": ["S1", "S2"],
            "conflict_claims": [
                {"source_id": "S1", "claim": "The property has 3 floors."},
                {"source_id": "S2", "claim": "The property has 4 floors."},
            ],
            "limitations": ["The documents disagree."],
        }
    )
    service, _, _ = _service(
        results=[
            _result(
                "chk_1",
                document_id="doc_1",
                text="The property has 3 floors.",
            ),
            _result(
                "chk_2",
                document_id="doc_2",
                text="The property has 4 floors.",
            ),
        ],
        generation=generation,
    )
    response = await service.ask("How many floors?")

    assert response.evidence_status == "conflicting_evidence"
    assert [citation.citation_id for citation in response.citations] == ["S1", "S2"]


async def test_single_source_conflict_is_downgraded():
    generation = json.dumps(
        {
            "answer": "This evidence appears inconsistent [S1].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    service, _, _ = _service(results=[_result()], generation=generation)
    response = await service.ask("Boundary?")

    assert response.evidence_status == "insufficient_evidence"
    assert any("at least two" in item for item in response.limitations)


async def test_conflict_from_the_same_document_is_downgraded():
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [S1], but also 4 floors [S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [
                {"source_id": "S1", "claim": "The property has 3 floors."},
                {"source_id": "S2", "claim": "The property has 4 floors."},
            ],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result(
                "chk_1",
                document_id="doc_1",
                text="The property has 3 floors.",
                start_offset=0,
                end_offset=25,
            ),
            _result(
                "chk_2",
                document_id="doc_1",
                text="The property has 4 floors.",
                start_offset=100,
                end_offset=125,
            ),
        ],
        generation=generation,
    )

    response = await service.ask("How many floors?")

    assert response.evidence_status == "insufficient_evidence"
    assert any(
        "distinct documents" in item for item in response.limitations
    )


async def test_conflict_claim_must_be_verbatim_from_the_cited_source():
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [S1], but 4 floors [S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [
                {"source_id": "S1", "claim": "The property has 5 floors."},
                {"source_id": "S2", "claim": "The property has 4 floors."},
            ],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result(
                "chk_1",
                document_id="doc_1",
                text="The property has 3 floors.",
            ),
            _result(
                "chk_2",
                document_id="doc_2",
                text="The property has 4 floors.",
                start_offset=100,
                end_offset=125,
            ),
        ],
        generation=generation,
    )

    response = await service.ask("How many floors?")

    assert response.evidence_status == "insufficient_evidence"
    assert any("verbatim" in item for item in response.limitations)


async def test_non_material_document_differences_do_not_count_as_conflict():
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [S1][S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [
                {
                    "source_id": "S1",
                    "claim": "The property has 3 floors and a garden.",
                },
                {
                    "source_id": "S2",
                    "claim": "The property has 3 floors and a pool.",
                },
            ],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result(
                "chk_1",
                document_id="doc_1",
                text="The property has 3 floors and a garden.",
            ),
            _result(
                "chk_2",
                document_id="doc_2",
                text="The property has 3 floors and a pool.",
                start_offset=100,
                end_offset=140,
            ),
        ],
        generation=generation,
    )

    response = await service.ask("What does the property have?")

    assert response.evidence_status == "insufficient_evidence"
    assert any(
        "material disagreement" in item for item in response.limitations
    )


async def test_supported_answer_with_an_uncited_sentence_is_downgraded():
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [S1]. It also has a garden.",
            "evidence_status": "supported",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[_result(text="The property has 3 floors.")],
        generation=generation,
    )

    response = await service.ask("What does the property have?")

    assert response.evidence_status == "insufficient_evidence"
    assert response.citations == []
    assert any("lacked a citation" in item for item in response.limitations)


async def test_citation_labels_are_normalized_and_malformed_labels_removed():
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [s01] and 4 rooms "
            "[S1, S2], per the deed [S1a] [S99].",
            "evidence_status": "supported",
            "used_source_ids": [1, 2, 99],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result(
                "chk_1",
                document_id="doc_1",
                text="The property has 3 floors and 4 rooms.",
            ),
            _result(
                "chk_2",
                document_id="doc_2",
                text="The deed records four rooms.",
                start_offset=100,
                end_offset=130,
            ),
        ],
        generation=generation,
    )

    response = await service.ask("What does the property have?")

    assert response.evidence_status == "supported"
    assert "[s01]" not in response.answer
    assert "[S1, S2]" not in response.answer
    assert "[S1a]" not in response.answer
    assert "[S99]" not in response.answer
    assert "[S1]" in response.answer
    assert "[S2]" in response.answer
    assert [citation.citation_id for citation in response.citations] == [
        "S1",
        "S2",
    ]
    assert any("malformed citation" in item for item in response.limitations)
    assert any("citation labels" in item for item in response.limitations)


async def test_weak_retrieval_results_do_not_reach_the_model():
    service, _, llm = _service(
        results=[
            _result(
                "chk_1",
                text="Unrelated content.",
                score=0.1,
            )
        ],
    )

    response = await service.ask("Question")

    assert response.evidence_status == "no_relevant_sources"
    assert response.retrieved_count == 1
    assert response.used_chunk_count == 0
    assert response.citations == []
    assert llm.calls == []
    assert any("relevance policy" in item for item in response.limitations)


async def test_hybrid_keyword_rank_can_pass_the_relevance_policy():
    service, _, llm = _service(
        results=[
            _result(
                "chk_1",
                text="The boundary follows the river.",
                score=0.01,
                score_type="reciprocal_rank_fusion",
                semantic_score=0.1,
                keyword_rank=1,
            )
        ],
    )

    response = await service.ask("Boundary?", mode="hybrid")

    assert response.evidence_status == "supported"
    assert response.used_chunk_count == 1
    assert llm.calls


async def test_insufficient_evidence_with_citations_stays_insufficient():
    generation = json.dumps(
        {
            "answer": "The excerpt does not identify the eastern boundary [S1].",
            "evidence_status": "insufficient_evidence",
            "used_source_ids": [1],
            "limitations": ["Only the western boundary is described."],
        }
    )
    service, _, _ = _service(results=[_result()], generation=generation)
    response = await service.ask("What is the eastern boundary?")

    assert response.evidence_status == "insufficient_evidence"
    assert [citation.citation_id for citation in response.citations] == ["S1"]
    assert response.answer.endswith("[S1].")


# --- Safe fallbacks and failures ------------------------------------------


async def test_malformed_model_output_returns_a_safe_insufficient_answer():
    service, _, _ = _service(
        results=[_result()],
        generation="This is not JSON and contains private model output.",
    )
    response = await service.ask("Boundary?")

    assert response.evidence_status == "insufficient_evidence"
    assert response.citations == []
    assert "private model output" not in response.answer
    assert "private model output" not in " ".join(response.limitations)
    assert response.retrieved_count == 1
    assert response.used_chunk_count == 1


async def test_unsupported_model_status_returns_a_safe_fallback():
    generation = json.dumps(
        {
            "answer": "Answer text",
            "evidence_status": "verified_by_the_internet",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    service, _, _ = _service(results=[_result()], generation=generation)
    response = await service.ask("Boundary?")

    assert response.evidence_status == "insufficient_evidence"
    assert response.citations == []


async def test_retrieval_errors_propagate_without_calling_the_llm():
    service, _, llm = _service(
        retrieval_error=RetrievalDatabaseError("database down")
    )
    with pytest.raises(RetrievalDatabaseError):
        await service.ask("Boundary?")
    assert llm.calls == []


async def test_llm_errors_propagate_safely():
    service, _, _ = _service(
        results=[_result()],
        llm_error=LLMRateLimitError("rate limited"),
    )
    with pytest.raises(LLMRateLimitError):
        await service.ask("Boundary?")


@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
async def test_blank_questions_are_rejected(question):
    service, retrieval, llm = _service(results=[_result()])
    with pytest.raises(RAGQueryError):
        await service.ask(question)
    assert retrieval.calls == []
    assert llm.calls == []


async def test_overlong_questions_are_rejected():
    service, retrieval, llm = _service(results=[_result()])
    with pytest.raises(RAGQueryError):
        await service.ask("x" * (service.settings.rag_max_question_chars + 1))
    assert retrieval.calls == []
    assert llm.calls == []


async def test_logging_does_not_include_question_answer_or_evidence(caplog):
    caplog.set_level(logging.INFO)
    generation = json.dumps(
        {
            "answer": "Private answer text [S1].",
            "evidence_status": "supported",
            "used_source_ids": [1],
            "limitations": ["Private limitation text."],
        }
    )
    service, _, _ = _service(
        results=[_result(text="Private evidence text.")],
        generation=generation,
    )
    await service.ask("Private question text?")

    logged = caplog.text
    assert "Private question text" not in logged
    assert "Private answer text" not in logged
    assert "Private evidence text" not in logged
    assert "rag_completed" in logged


# --- Audit remediation regression tests -----------------------------------


async def test_conflict_downgraded_for_corroborating_documents():
    """Two documents with corroborating information cannot trigger conflict."""
    generation = json.dumps(
        {
            "answer": "Both documents state the property has 3 floors [S1][S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [
                {"source_id": "S1", "claim": "The property has 3 floors."},
                {"source_id": "S2", "claim": "The property has 3 floors."},
            ],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result("chk_1", document_id="doc_1", text="The property has 3 floors."),
            _result("chk_2", document_id="doc_2", text="The property has 3 floors."),
        ],
        generation=generation,
    )
    response = await service.ask("How many floors?")

    assert response.evidence_status == "insufficient_evidence"
    assert any("material disagreement" in item for item in response.limitations)


async def test_conflict_downgraded_for_missing_or_ambiguous_source_metadata():
    """Ambiguous or missing source metadata prevents asserting a conflict."""
    generation = json.dumps(
        {
            "answer": "One document says 3 floors [S1], another says 4 floors [S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [
                {"source_id": "S1", "claim": "The property has 3 floors."},
                {"source_id": "S2", "claim": "The property has 4 floors."},
            ],
            "limitations": [],
        }
    )
    # doc_1 has missing/empty document_id
    res1 = _result("chk_1", document_id="", text="The property has 3 floors.")
    res2 = _result("chk_2", document_id="doc_2", text="The property has 4 floors.")
    service, _, _ = _service(results=[res1, res2], generation=generation)
    response = await service.ask("How many floors?")

    assert response.evidence_status == "insufficient_evidence"
    assert any("missing or ambiguous" in item for item in response.limitations)


async def test_conflict_cannot_be_triggered_merely_by_citing_two_chunks():
    """Merely citing two chunks without verbatim conflicting claims downgrades to insufficient."""
    generation = json.dumps(
        {
            "answer": "The property has 3 floors [S1] and was completed in 2021 [S2].",
            "evidence_status": "conflicting_evidence",
            "used_source_ids": [1, 2],
            "conflict_claims": [],  # No conflict claims provided
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result("chk_1", document_id="doc_1", text="The property has 3 floors."),
            _result("chk_2", document_id="doc_2", text="Completed in 2021."),
        ],
        generation=generation,
    )
    response = await service.ask("What are the property details?")

    assert response.evidence_status == "insufficient_evidence"
    assert any("fewer than two" in item for item in response.limitations)


async def test_citation_integrity_does_not_guarantee_factual_entailment():
    """Citations guarantee source integrity, not verified factual entailment."""
    generation = json.dumps(
        {
            "answer": "The property features a rooftop helipad and olympic pool [S1].",
            "evidence_status": "supported",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    # chk_1 does NOT mention helipad or pool, but the citation is structurally valid
    service, _, _ = _service(
        results=[_result("chk_1", text="The property has 3 bedrooms.")],
        generation=generation,
    )
    response = await service.ask("What amenities exist?")

    assert response.evidence_status == "supported"
    assert response.citation_guarantee == "retrieved_source_integrity"
    assert response.claim_support_verified is False
    assert any("claim-level entailment" in item for item in response.limitations)
    assert response.citations[0].chunk_id == "chk_1"


async def test_supported_answer_with_multiple_cited_claims():
    """An answer with multiple factual sentences where all are cited stays supported."""
    generation = json.dumps(
        {
            "answer": (
                "The owner is Ananya Rao [S1]. "
                "The sale consideration is INR 8500000 [S1]. "
                "The apartment has three bedrooms [S2]."
            ),
            "evidence_status": "supported",
            "used_source_ids": [1, 2],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result("chk_1", document_id="doc_1", text="Ananya Rao owner. INR 8500000."),
            _result("chk_2", document_id="doc_2", text="Three bedrooms."),
        ],
        generation=generation,
    )
    response = await service.ask("Owner, price, and bedrooms?")

    assert response.evidence_status == "supported"
    assert [c.citation_id for c in response.citations] == ["S1", "S2"]


async def test_citation_labels_normalization_for_source_and_citation_variants():
    """Various citation notations like [Source 1], [citation 2], [S-1] are normalized."""
    generation = json.dumps(
        {
            "answer": (
                "The property has 3 floors [Source 1]. "
                "It is in Whitefield [citation: 1]. "
                "The metro is nearby [Source S2] [S-2]."
            ),
            "evidence_status": "supported",
            "used_source_ids": [1, 2],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[
            _result("chk_1", document_id="doc_1", text="3 floors in Whitefield."),
            _result("chk_2", document_id="doc_2", text="Metro is nearby."),
        ],
        generation=generation,
    )
    response = await service.ask("Tell me about the property.")

    assert response.evidence_status == "supported"
    assert "[Source 1]" not in response.answer
    assert "[citation: 1]" not in response.answer
    assert "[Source S2]" not in response.answer
    assert "[S-2]" not in response.answer
    assert "[S1]" in response.answer
    assert "[S2]" in response.answer
    assert [c.citation_id for c in response.citations] == ["S1", "S2"]


async def test_malformed_citation_looking_references_are_removed():
    """Malformed references like [Source X] and [citation needed] are stripped."""
    generation = json.dumps(
        {
            "answer": (
                "The property has 3 floors [S1], but roof access is uncertain [citation needed] "
                "and basement storage is unverified [Source X] [S1a]."
            ),
            "evidence_status": "supported",
            "used_source_ids": [1],
            "limitations": [],
        }
    )
    service, _, _ = _service(
        results=[_result("chk_1", text="The property has 3 floors.")],
        generation=generation,
    )
    response = await service.ask("Tell me about the property.")

    assert "[citation needed]" not in response.answer
    assert "[Source X]" not in response.answer
    assert "[S1a]" not in response.answer
    assert "[S1]" in response.answer
    assert any("malformed citation" in item for item in response.limitations)


async def test_high_similarity_score_alone_does_not_force_supported_status():
    """A high retrieval score does not override an insufficient or ungrounded evidence evaluation."""
    generation = json.dumps(
        {
            "answer": "The excerpt mentions the property but does not state the warranty terms [S1].",
            "evidence_status": "insufficient_evidence",
            "used_source_ids": [1],
            "limitations": ["Warranty terms were not found in the retrieved document."],
        }
    )
    # High score (0.95), but document does not answer the question
    service, _, _ = _service(
        results=[_result("chk_1", score=0.95, semantic_score=0.95, text="General property info.")],
        generation=generation,
    )
    response = await service.ask("What are the warranty terms?")

    assert response.evidence_status == "insufficient_evidence"
    assert response.used_chunk_count == 1
