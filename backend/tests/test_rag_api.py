"""Phase 5 RAG API tests. The orchestrator and providers are mocked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import rag
from app.core.config import Settings
from app.main import create_app
from app.schemas.rag import RAGCitation, RAGResponse
from app.services.rag_errors import (
    RAGConfigurationError,
    RAGExecutionError,
    RAGGenerationError,
    RAGQueryError,
)
from app.services.retrieval_errors import RetrievalDatabaseError


def _settings() -> Settings:
    return Settings(
        groq_api_key="test-key-not-a-secret",
        embedding_provider="fastembed",
        embedding_model="fake-model",
        embedding_dimensions=4,
    )


def _response(**overrides) -> RAGResponse:
    values = {
        "question": "What is the western boundary?",
        "answer": "The western boundary follows the river [S1].",
        "evidence_status": "supported",
        "citations": [
            RAGCitation(
                citation_id="S1",
                chunk_id="chk_1",
                document_id="doc_1",
                filename="sale-deed.pdf",
                source_type="pdf",
                page_number=2,
                page_numbers=[2],
                chunk_index=0,
                excerpt="The western boundary follows the river.",
            )
        ],
        "limitations": ["Only one excerpt was retrieved."],
        "retrieved_count": 1,
        "used_chunk_count": 1,
        "mode": "semantic",
    }
    values.update(overrides)
    return RAGResponse(**values)


class _FakeRAGService:
    def __init__(self, response=None, error=None):
        self.response = response or _response()
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    async def ask(self, question: str, **kwargs) -> RAGResponse:
        self.calls.append((question, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def _client(service) -> TestClient:
    app = create_app()
    app.dependency_overrides[rag.get_rag_service] = lambda: service
    return TestClient(app)


def _ask(client: TestClient, settings: Settings, payload: dict):
    return client.post(f"{settings.api_prefix}/rag/ask", json=payload)


def test_valid_request_returns_grounded_response():
    settings = _settings()
    service = _FakeRAGService()
    client = _client(service)

    response = _ask(
        client,
        settings,
        {
            "question": "  What is the western boundary?  ",
            "top_k": 2,
            "mode": "hybrid",
            "document_id": "doc_1",
            "filters": {"source_filename": "sale-deed.pdf"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == "supported"
    assert body["answer"].endswith("[S1].")
    assert body["citations"][0]["chunk_id"] == "chk_1"
    assert body["citations"][0]["page_numbers"] == [2]
    assert body["retrieved_count"] == 1
    assert body["used_chunk_count"] == 1
    assert body["citation_guarantee"] == "retrieved_source_integrity"
    assert body["claim_support_verified"] is False
    assert service.calls[0][0] == "What is the western boundary?"
    assert service.calls[0][1]["top_k"] == 2
    assert service.calls[0][1]["mode"] == "hybrid"
    assert service.calls[0][1]["filters"].source_filename == "sale-deed.pdf"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "Boundary?", "mode": "keyword"},
        {"question": "Boundary?", "top_k": 0},
        {"question": "Boundary?", "filters": {"unknown": "x"}},
        {"question": "x" * 8001},
    ],
)
def test_invalid_requests_are_rejected_before_orchestration(payload):
    settings = _settings()
    service = _FakeRAGService()
    client = _client(service)

    response = _ask(client, settings, payload)

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RAGQueryError("bad query"), 422),
        (RAGConfigurationError("not configured"), 503),
        (RAGGenerationError("invalid generation"), 502),
        (RAGExecutionError("failed safely"), 500),
        (RetrievalDatabaseError("database down"), 503),
    ],
)
def test_errors_map_to_safe_status_codes(error, expected_status):
    settings = _settings()
    client = _client(_FakeRAGService(error=error))
    response = _ask(client, settings, {"question": "Boundary?"})

    assert response.status_code == expected_status
    assert "traceback" not in response.text.lower()
    assert error.message in response.json()["detail"]


def test_missing_llm_configuration_returns_safe_503():
    settings = Settings(groq_api_key=None)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        f"{settings.api_prefix}/rag/ask",
        json={"question": "What is the western boundary?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"].lower()
    assert "not configured" in detail
    assert "traceback" not in response.text.lower()


def test_openapi_documents_the_rag_endpoint():
    settings = _settings()
    client = _client(_FakeRAGService())
    schema = client.get("/openapi.json").json()

    assert f"{settings.api_prefix}/rag/ask" in schema["paths"]
    operation = schema["paths"][f"{settings.api_prefix}/rag/ask"]["post"]
    assert "grounded" in operation["summary"].lower()
    # Also verify Phase 6 document management routes are documented in OpenAPI
    assert f"{settings.api_prefix}/documents" in schema["paths"]
    assert f"{settings.api_prefix}/documents/{{document_id}}" in schema["paths"]
    assert f"{settings.api_prefix}/documents/{{document_id}}/chunks" in schema["paths"]


def test_rag_ask_with_document_id_filter():
    settings = _settings()
    service = _FakeRAGService()
    client = _client(service)

    response = _ask(
        client,
        settings,
        {
            "question": "What is the mortgage status?",
            "document_id": "doc_mortgage_42",
        },
    )

    assert response.status_code == 200
    assert service.calls[0][1]["document_id"] == "doc_mortgage_42"


def test_rag_ask_returns_no_relevant_sources():
    settings = _settings()
    no_source_response = _response(
        answer="I could not find relevant information in the provided property documents.",
        evidence_status="no_relevant_sources",
        citations=[],
        retrieved_count=0,
        used_chunk_count=0,
    )
    service = _FakeRAGService(response=no_source_response)
    client = _client(service)

    response = _ask(
        client,
        settings,
        {
            "question": "What is the zoning law?",
            "document_id": "doc_nonexistent",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == "no_relevant_sources"
    assert body["citations"] == []
    assert body["retrieved_count"] == 0

