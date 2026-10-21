"""Phase 4 retrieval API tests using mock embedding and in-memory stores."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import retrieval
from app.core.config import Settings
from app.main import create_app
from app.services.embedding_service import (
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingService,
    EmbeddingTimeoutError,
)
from app.services.retrieval_errors import (
    RetrievalConfigurationError,
    RetrievalDatabaseError,
    RetrievalExecutionError,
)
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeRetrievalStore,
    keyword_match,
    semantic_match,
)


def _settings(**overrides) -> Settings:
    values = {
        "groq_api_key": None,
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 4,
        "retrieval_default_top_k": 3,
        "retrieval_max_top_k": 5,
    }
    values.update(overrides)
    return Settings(**values)


def _client(
    store: FakeRetrievalStore,
    *,
    settings: Settings | None = None,
    provider=None,
) -> tuple[TestClient, Settings]:
    settings = settings or _settings()
    app = create_app()
    embedding_service = EmbeddingService(
        settings,
        provider=provider or FakeEmbeddingProvider(dimensions=4),
    )
    app.dependency_overrides[retrieval.get_settings_dep] = lambda: settings
    app.dependency_overrides[retrieval.get_embedding_service] = (
        lambda: embedding_service
    )
    app.dependency_overrides[retrieval.get_retrieval_store] = lambda: store
    return TestClient(app), settings


def _search(client: TestClient, settings: Settings, payload: dict):
    return client.post(
        f"{settings.api_prefix}/retrieval/search", json=payload
    )


# --- Successful requests -----------------------------------------------------


def test_valid_semantic_search_returns_expected_structure():
    store = FakeRetrievalStore(
        [
            semantic_match(
                "chk_1",
                distance=0.13,
                filename="property-document.pdf",
                page_number=2,
            )
        ]
    )
    client, settings = _client(store)

    response = _search(
        client,
        settings,
        {
            "query": "What legal documents are available for this property?",
            "top_k": 5,
            "document_id": None,
            "filters": {},
            "mode": "semantic",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"query", "mode", "results", "result_count"}
    assert body["query"] == "What legal documents are available for this property?"
    assert body["mode"] == "semantic"
    assert body["result_count"] == 1
    result = body["results"][0]
    assert result["chunk_id"] == "chk_1"
    assert result["document_id"] == "doc_1"
    assert result["score"] == pytest.approx(0.87)
    assert result["score_type"] == "cosine_similarity"
    assert result["distance"] == pytest.approx(0.13)
    assert result["metadata"]["filename"] == "property-document.pdf"
    assert result["metadata"]["page_number"] == 2
    assert result["metadata"]["page_numbers"] == [2]
    assert "traceback" not in response.text.lower()


def test_omitted_top_k_uses_the_configured_default():
    store = FakeRetrievalStore(
        [semantic_match(f"chk_{index}") for index in range(5)]
    )
    client, settings = _client(store)

    response = _search(client, settings, {"query": "title"})

    assert response.status_code == 200
    assert response.json()["result_count"] == settings.retrieval_default_top_k
    assert store.semantic_calls[0]["limit"] == settings.retrieval_default_top_k


def test_filters_and_document_id_are_forwarded():
    store = FakeRetrievalStore([semantic_match("chk_1")])
    client, settings = _client(store)

    response = _search(
        client,
        settings,
        {
            "query": "encumbrance certificate",
            "document_id": "doc_42",
            "filters": {
                "source_filename": "ec.pdf",
                "source_type": "pdf",
                "page_number": 3,
            },
        },
    )

    assert response.status_code == 200
    passed = store.semantic_calls[0]["filters"]
    assert passed.document_id == "doc_42"
    assert passed.source_filename == "ec.pdf"
    assert passed.source_type == "pdf"
    assert passed.page_number == 3


def test_hybrid_search_returns_fused_results():
    store = FakeRetrievalStore(
        semantic_results=[semantic_match("chk_a", distance=0.1)],
        keyword_results=[keyword_match("chk_b", rank=1)],
    )
    client, settings = _client(store)

    response = _search(
        client,
        settings,
        {"query": "sale deed", "mode": "hybrid", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hybrid"
    assert [item["chunk_id"] for item in body["results"]] == [
        "chk_a",
        "chk_b",
    ]
    assert all(
        item["score_type"] == "reciprocal_rank_fusion"
        for item in body["results"]
    )


def test_empty_database_returns_an_empty_200_response():
    client, settings = _client(FakeRetrievalStore())
    response = _search(client, settings, {"query": "title"})
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["result_count"] == 0


# --- Request validation ------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "title", "top_k": 0},
        {"query": "title", "top_k": 999},
        {"query": "title", "mode": "keyword"},
        {"query": "title", "min_score": 2},
        {"query": "title", "document_id": "   "},
        {"query": "title", "filters": {"page_number": 0}},
        {"query": "title", "filters": {"property_id": "prop_1"}},
        {"query": "title", "filters": {"source_type": "docx"}},
        {"query": "title", "unknown_field": True},
    ],
)
def test_invalid_requests_return_422(payload):
    client, settings = _client(FakeRetrievalStore())
    response = _search(client, settings, payload)
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_overlong_query_is_rejected_by_the_service():
    client, settings = _client(
        FakeRetrievalStore(), settings=_settings(retrieval_max_query_chars=5)
    )
    response = _search(client, settings, {"query": "too many words"})
    assert response.status_code == 422
    assert "character limit" in response.json()["detail"]


# --- Error mapping and safety ------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RetrievalConfigurationError("safe configuration error"), 503),
        (RetrievalDatabaseError("safe database error"), 503),
        (RetrievalExecutionError("safe execution error"), 500),
    ],
)
def test_retrieval_errors_map_to_safe_status_codes(error, expected_status):
    client, settings = _client(FakeRetrievalStore(error=error))
    response = _search(client, settings, {"query": "title"})

    assert response.status_code == expected_status
    assert response.json()["detail"] == error.message
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (EmbeddingProviderError("safe provider error"), 502),
        (EmbeddingRateLimitError("safe rate limit"), 429),
        (EmbeddingTimeoutError("safe timeout"), 504),
    ],
)
def test_embedding_errors_map_to_safe_status_codes(error, expected_status):
    client, settings = _client(
        FakeRetrievalStore(),
        provider=FakeEmbeddingProvider(dimensions=4, error=error),
    )
    response = _search(client, settings, {"query": "title"})

    assert response.status_code == expected_status
    assert response.json()["detail"] == error.message


def test_exception_details_are_not_leaked():
    client, settings = _client(
        FakeRetrievalStore(),
        provider=FakeEmbeddingProvider(
            dimensions=4,
            error=RuntimeError("secret-provider-payload"),
        ),
    )
    response = _search(client, settings, {"query": "title"})

    assert response.status_code == 502
    assert "secret-provider-payload" not in response.text
    assert "traceback" not in response.text.lower()


def test_openapi_documents_the_retrieval_endpoint():
    client, settings = _client(FakeRetrievalStore())
    schema = client.get("/openapi.json").json()
    path = f"{settings.api_prefix}/retrieval/search"
    assert path in schema["paths"]
    assert "post" in schema["paths"][path]
    operation = schema["paths"][path]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]
    assert operation["responses"]["200"]
