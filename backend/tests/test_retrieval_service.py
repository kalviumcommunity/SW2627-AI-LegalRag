"""Phase 4 retrieval service tests. No network, database, or paid API calls."""

from __future__ import annotations

import logging
import math

import pytest

from app.core.config import Settings
from app.schemas.retrieval import RetrievalFilters
from app.services.embedding_service import (
    EmbeddingProviderError,
    EmbeddingService,
    EmbeddingTimeoutError,
)
from app.services.retrieval_errors import (
    RetrievalConfigurationError,
    RetrievalDatabaseError,
    RetrievalExecutionError,
    RetrievalQueryError,
)
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_store import SearchFilters
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeRetrievalStore,
    keyword_match,
    semantic_match,
)


def _settings(**overrides) -> Settings:
    values = {
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 4,
        "embedding_batch_size": 10,
        "retrieval_default_top_k": 3,
        "retrieval_max_top_k": 5,
        "retrieval_hybrid_candidate_limit": 10,
        "retrieval_rrf_k": 60,
    }
    values.update(overrides)
    return Settings(**values)


def _service(
    store: FakeRetrievalStore,
    *,
    provider=None,
    **overrides,
) -> tuple[RetrievalService, FakeEmbeddingProvider]:
    settings = _settings(**overrides)
    embedding_provider = provider or FakeEmbeddingProvider(dimensions=4)
    service = RetrievalService(
        settings,
        embedding_service=EmbeddingService(
            settings, provider=embedding_provider
        ),
        store=store,
    )
    return service, embedding_provider


# --- Query embedding and response mapping -----------------------------------


def test_query_is_normalized_embedded_and_returned():
    store = FakeRetrievalStore([semantic_match("chk_1")])
    service, provider = _service(store)

    outcome = service.search("  Who\towns   the property?  ")

    assert provider.calls == [["Who owns the property?"]]
    assert outcome.response.query == "Who owns the property?"
    assert len(outcome.response.results) == 1
    assert len(store.semantic_calls) == 1
    vector = store.semantic_calls[0]["query_vector"]
    assert len(vector) == 4
    assert math.isclose(sum(value * value for value in vector), 1.0)
    assert outcome.embedding_duration_ms >= 0
    assert outcome.database_duration_ms >= 0
    assert outcome.total_duration_ms >= 0


def test_cosine_similarity_score_and_distance_are_reported():
    store = FakeRetrievalStore([semantic_match("chk_1", distance=0.25)])
    service, _ = _service(store)

    result = service.search("title deed").response.results[0]

    assert result.score_type == "cosine_similarity"
    assert result.score == pytest.approx(0.75)
    assert result.semantic_score == pytest.approx(0.75)
    assert result.distance == pytest.approx(0.25)
    assert result.metadata.filename == "deed.pdf"
    assert result.metadata.page_number == 1
    assert result.metadata.page_numbers == [1]


def test_semantic_results_preserve_database_ordering():
    store = FakeRetrievalStore(
        [
            semantic_match("chk_best", distance=0.1),
            semantic_match("chk_mid", distance=0.4),
            semantic_match("chk_worst", distance=0.9),
        ]
    )
    service, _ = _service(store)

    results = service.search("anything").response.results

    assert [result.chunk_id for result in results] == [
        "chk_best",
        "chk_mid",
        "chk_worst",
    ]
    assert [result.score for result in results] == pytest.approx(
        [0.9, 0.6, 0.1]
    )


def test_results_beyond_top_k_are_not_returned():
    store = FakeRetrievalStore(
        [semantic_match(f"chk_{index}", distance=index / 10) for index in range(5)]
    )
    service, _ = _service(store)

    outcome = service.search("anything", top_k=2)

    assert len(outcome.response.results) == 2
    assert store.semantic_calls[0]["limit"] == 2


def test_default_top_k_is_used_when_not_supplied():
    store = FakeRetrievalStore(
        [semantic_match(f"chk_{index}") for index in range(5)]
    )
    service, _ = _service(store)

    assert len(service.search("anything").response.results) == 3
    assert store.semantic_calls[0]["limit"] == 3


def test_empty_database_returns_an_empty_result_set():
    store = FakeRetrievalStore([])
    service, _ = _service(store)

    outcome = service.search("no matching chunk")

    assert outcome.response.results == []
    assert outcome.response.result_count == 0


def test_min_score_is_passed_to_the_semantic_query():
    store = FakeRetrievalStore([semantic_match("chk_1")])
    service, _ = _service(store)

    service.search("title", min_score=0.4)

    assert store.semantic_calls[0]["min_score"] == pytest.approx(0.4)


# --- Validation --------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", "\n\t "])
def test_empty_queries_are_rejected_before_embedding(query):
    store = FakeRetrievalStore()
    service, provider = _service(store)

    with pytest.raises(RetrievalQueryError):
        service.search(query)
    assert provider.calls == []
    assert store.semantic_calls == []


def test_non_string_query_is_rejected():
    service, provider = _service(FakeRetrievalStore())
    with pytest.raises(RetrievalQueryError):
        service.search(123)  # type: ignore[arg-type]
    assert provider.calls == []


def test_overlong_query_is_rejected():
    service, provider = _service(
        FakeRetrievalStore(), retrieval_max_query_chars=5
    )
    with pytest.raises(RetrievalQueryError):
        service.search("too long")
    assert provider.calls == []


@pytest.mark.parametrize("top_k", [0, -1, 6, True, 1.5])
def test_invalid_top_k_values_are_rejected(top_k):
    service, provider = _service(FakeRetrievalStore())
    with pytest.raises(RetrievalQueryError):
        service.search("title", top_k=top_k)  # type: ignore[arg-type]
    assert provider.calls == []


def test_invalid_mode_is_rejected():
    service, _ = _service(FakeRetrievalStore())
    with pytest.raises(RetrievalQueryError):
        service.search("title", mode="keyword")  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [-1.1, 1.1, float("nan"), True, "high"])
def test_invalid_min_score_is_rejected(score):
    service, _ = _service(FakeRetrievalStore())
    with pytest.raises(RetrievalQueryError):
        service.search("title", min_score=score)  # type: ignore[arg-type]


# --- Failure handling --------------------------------------------------------


def test_embedding_provider_errors_propagate_safely():
    provider = FakeEmbeddingProvider(
        dimensions=4, error=EmbeddingProviderError("provider unavailable")
    )
    store = FakeRetrievalStore([semantic_match("chk_1")])
    service, _ = _service(store, provider=provider)

    with pytest.raises(EmbeddingProviderError):
        service.search("title")
    assert store.semantic_calls == []


def test_database_errors_propagate_safely():
    store = FakeRetrievalStore(error=RetrievalDatabaseError("database down"))
    service, _ = _service(store)

    with pytest.raises(RetrievalDatabaseError):
        service.search("title")


def test_invalid_query_embedding_dimensions_are_a_configuration_error():
    class _WrongDimensionEmbeddingService:
        def embed_texts(self, texts):
            return [[1.0, 0.0]]

    settings = _settings()
    service = RetrievalService(
        settings,
        embedding_service=_WrongDimensionEmbeddingService(),  # type: ignore[arg-type]
        store=FakeRetrievalStore(),
    )

    with pytest.raises(RetrievalConfigurationError):
        service.search("title")


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_non_finite_query_embedding_is_rejected(bad_value):
    class _BadEmbeddingService:
        def embed_texts(self, texts):
            return [[bad_value, 0.0, 0.0, 1.0]]

    service = RetrievalService(
        _settings(),
        embedding_service=_BadEmbeddingService(),  # type: ignore[arg-type]
        store=FakeRetrievalStore(),
    )

    with pytest.raises(RetrievalExecutionError):
        service.search("title")


def test_unexpected_embedding_failure_is_wrapped_without_internals():
    class _BrokenEmbeddingService:
        def embed_texts(self, texts):
            raise RuntimeError("secret-internal-detail")

    service = RetrievalService(
        _settings(),
        embedding_service=_BrokenEmbeddingService(),  # type: ignore[arg-type]
        store=FakeRetrievalStore(),
    )

    with pytest.raises(Exception) as raised:
        service.search("title")
    assert "secret-internal-detail" not in str(raised.value)


# --- Filters -----------------------------------------------------------------


def test_filters_are_mapped_and_passed_to_the_store():
    store = FakeRetrievalStore([semantic_match("chk_1")])
    service, _ = _service(store)
    filters = RetrievalFilters(
        source_filename="deed.pdf",
        source_type="pdf",
        page_number=2,
    )

    service.search("title", document_id="doc_9", filters=filters)

    passed = store.semantic_calls[0]["filters"]
    assert passed == SearchFilters(
        document_id="doc_9",
        source_filename="deed.pdf",
        source_type="pdf",
        page_number=2,
    )


# --- Hybrid retrieval --------------------------------------------------------


def test_hybrid_rrf_fuses_deduplicates_and_preserves_metadata():
    store = FakeRetrievalStore(
        semantic_results=[
            semantic_match("chk_a", distance=0.1),
            semantic_match("chk_b", distance=0.2),
        ],
        keyword_results=[
            keyword_match("chk_b", rank=1),
            keyword_match("chk_c", rank=2),
        ],
    )
    service, _ = _service(store)

    outcome = service.search("legal title", mode="hybrid", top_k=3)
    results = outcome.response.results

    assert [result.chunk_id for result in results] == [
        "chk_b",
        "chk_a",
        "chk_c",
    ]
    assert len({result.chunk_id for result in results}) == 3
    by_id = {result.chunk_id: result for result in results}
    assert by_id["chk_b"].keyword_rank == 1
    assert by_id["chk_b"].semantic_score == pytest.approx(0.8)
    assert by_id["chk_b"].score_type == "reciprocal_rank_fusion"
    assert by_id["chk_c"].keyword_rank == 2
    assert by_id["chk_c"].distance is None
    assert by_id["chk_c"].semantic_score is None
    assert all(
        result.metadata.filename == "deed.pdf" for result in results
    )


def test_hybrid_uses_candidate_pool_and_returns_only_top_k():
    store = FakeRetrievalStore(
        semantic_results=[
            semantic_match(f"chk_{index}", distance=index / 10)
            for index in range(5)
        ],
        keyword_results=[keyword_match("chk_4", rank=1)],
    )
    service, _ = _service(store)

    outcome = service.search("anything", mode="hybrid", top_k=2)

    assert len(outcome.response.results) == 2
    assert store.semantic_calls[0]["limit"] == 10
    assert store.keyword_calls[0]["limit"] == 10


def test_hybrid_applies_min_score_only_to_semantic_candidates():
    store = FakeRetrievalStore(
        semantic_results=[semantic_match("chk_a")],
        keyword_results=[keyword_match("chk_b", rank=1)],
    )
    service, _ = _service(store)

    service.search("anything", mode="hybrid", min_score=0.3)

    assert store.semantic_calls[0]["min_score"] == pytest.approx(0.3)
    assert "min_score" not in store.keyword_calls[0]


def test_hybrid_ties_are_broken_deterministically_by_semantic_rank_then_id():
    store = FakeRetrievalStore(
        semantic_results=[semantic_match("chk_a", distance=0.1)],
        keyword_results=[keyword_match("chk_b", rank=1)],
    )
    service, _ = _service(store)

    results = service.search("anything", mode="hybrid").response.results

    # Both have RRF 1/(60+1); the semantic-only candidate comes first.
    assert [result.chunk_id for result in results] == ["chk_a", "chk_b"]


def test_hybrid_with_no_matches_is_empty():
    service, _ = _service(FakeRetrievalStore())
    outcome = service.search("nothing", mode="hybrid")
    assert outcome.response.results == []
    assert outcome.response.result_count == 0


# --- Logging -----------------------------------------------------------------


def test_logging_does_not_include_query_or_chunk_text(caplog):
    store = FakeRetrievalStore(
        [semantic_match("chk_1", text="private legal chunk contents")]
    )
    service, _ = _service(store)

    with caplog.at_level(
        logging.INFO, logger="app.services.retrieval_service"
    ):
        service.search("confidential query words")

    assert "retrieval_completed" in caplog.text
    assert "confidential query words" not in caplog.text
    assert "private legal chunk contents" not in caplog.text


def test_timeout_error_status_is_preserved():
    provider = FakeEmbeddingProvider(
        dimensions=4, error=EmbeddingTimeoutError("timed out")
    )
    service, _ = _service(FakeRetrievalStore(), provider=provider)
    with pytest.raises(EmbeddingTimeoutError) as raised:
        service.search("title")
    assert raised.value.status_code == 504
