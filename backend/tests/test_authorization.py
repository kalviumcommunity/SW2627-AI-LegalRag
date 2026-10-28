"""Tests for document-level authorization and multi-tenant isolation."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.deps import (
    get_auth_service,
    get_current_user,
    get_document_ingestion_service,
    get_document_management_service,
    get_llm_service,
    get_rag_service,
    get_retrieval_service,
)
from app.core.config import Settings, get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_management import DocumentManagementService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from tests.fakes import (
    FakeDocumentStore,
    FakeEmbeddingProvider,
    FakeLLMService,
    FakeRetrievalStore,
    chunk_record,
    retrieval_result,
)


@pytest.fixture
def auth_sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    yield engine
    engine.dispose()


@pytest.fixture
def auth_service(auth_sqlite_engine):
    settings = Settings(
        jwt_secret_key="secret-key-32-characters-minimum-authz-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        rate_limit_upload_per_minute=5,
        rate_limit_rag_per_minute=5,
    )
    return AuthService(settings=settings, engine=auth_sqlite_engine)


@pytest.fixture
def shared_stores():
    doc_store = FakeDocumentStore()
    embedding_provider = FakeEmbeddingProvider(dimensions=8)
    retrieval_store = FakeRetrievalStore()
    llm_service = FakeLLMService(response='{"answer": "Grounded answer.", "evidence_status": "fully_supported", "citations": []}')
    return {
        "doc_store": doc_store,
        "embedding_provider": embedding_provider,
        "retrieval_store": retrieval_store,
        "llm_service": llm_service,
    }


@pytest.fixture
def client(auth_service, shared_stores):
    app = create_app()
    # Remove default test user override
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: auth_service.settings

    doc_ingestion = DocumentIngestionService(
        store=shared_stores["doc_store"],
        embedding_service=shared_stores["embedding_provider"],
    )
    doc_management = DocumentManagementService(store=shared_stores["doc_store"])
    retrieval_srv = RetrievalService(
        settings=auth_service.settings,
        embedding_service=shared_stores["embedding_provider"],
        store=shared_stores["retrieval_store"],
        document_store=shared_stores["doc_store"],
    )
    rag_srv = RAGService(
        retrieval_service=retrieval_srv,
        llm_service=shared_stores["llm_service"],
    )

    app.dependency_overrides[get_document_ingestion_service] = lambda: doc_ingestion
    app.dependency_overrides[get_document_management_service] = lambda: doc_management
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_srv
    app.dependency_overrides[get_rag_service] = lambda: rag_srv
    app.dependency_overrides[get_llm_service] = lambda: shared_stores["llm_service"]

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register_user(client: TestClient, email: str, password: str = "Password123!") -> str:
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201
    return res.json()["access_token"]


def test_unauthenticated_requests_are_rejected(client):
    endpoints = [
        ("GET", "/documents"),
        ("POST", "/documents/ingest"),
        ("GET", "/documents/doc_123"),
        ("GET", "/documents/doc_123/chunks"),
        ("DELETE", "/documents/doc_123"),
        ("POST", "/retrieval/search"),
        ("POST", "/rag/ask"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path)
        elif method == "DELETE":
            resp = client.delete(path)
        else:
            resp = client.post(path, json={})
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, expected 401"
        assert "WWW-Authenticate" in resp.headers


def test_document_isolation_between_users(client):
    token_a = _register_user(client, "alice@propertyintel.com")
    token_b = _register_user(client, "bob@propertyintel.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads a document
    file_bytes = b"Lease agreement for Unit 402 with tenant Jane Doe."
    upload_res = client.post(
        "/documents/ingest",
        headers=headers_a,
        files={"file": ("lease_unit_402.txt", io.BytesIO(file_bytes), "text/plain")},
    )
    assert upload_res.status_code == 200
    doc_a_id = upload_res.json()["document_id"]

    # User A can view the document
    get_res_a = client.get(f"/documents/{doc_a_id}", headers=headers_a)
    assert get_res_a.status_code == 200
    assert get_res_a.json()["document_id"] == doc_a_id

    # User A can view chunks
    chunks_res_a = client.get(f"/documents/{doc_a_id}/chunks", headers=headers_a)
    assert chunks_res_a.status_code == 200
    assert chunks_res_a.json()["total"] >= 1

    # User A lists documents: contains doc_a_id
    list_res_a = client.get("/documents", headers=headers_a)
    assert list_res_a.status_code == 200
    assert any(d["document_id"] == doc_a_id for d in list_res_a.json()["items"])

    # User B lists documents: does NOT contain doc_a_id
    list_res_b = client.get("/documents", headers=headers_b)
    assert list_res_b.status_code == 200
    assert not any(d["document_id"] == doc_a_id for d in list_res_b.json()["items"])

    # User B tries to view User A's document -> returns 404 (safe, doesn't leak existence)
    get_res_b = client.get(f"/documents/{doc_a_id}", headers=headers_b)
    assert get_res_b.status_code == 404

    # User B tries to view chunks -> returns 404
    chunks_res_b = client.get(f"/documents/{doc_a_id}/chunks", headers=headers_b)
    assert chunks_res_b.status_code == 404

    # User B tries to delete User A's document -> returns 404
    del_res_b = client.delete(f"/documents/{doc_a_id}", headers=headers_b)
    assert del_res_b.status_code == 404

    # User A's document was NOT deleted by User B's attempt
    get_res_a_after = client.get(f"/documents/{doc_a_id}", headers=headers_a)
    assert get_res_a_after.status_code == 200

    # User A can delete their own document
    del_res_a = client.delete(f"/documents/{doc_a_id}", headers=headers_a)
    assert del_res_a.status_code == 200
    assert del_res_a.json()["deleted"] is True


def test_retrieval_and_rag_cross_tenant_isolation(client):
    token_a = _register_user(client, "alice2@propertyintel.com")
    token_b = _register_user(client, "bob2@propertyintel.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A ingests a doc
    file_bytes = b"Confidential tax and lien report for 742 Evergreen Terrace."
    upload_res = client.post(
        "/documents/ingest",
        headers=headers_a,
        files={"file": ("tax_lien.txt", io.BytesIO(file_bytes), "text/plain")},
    )
    assert upload_res.status_code == 200
    doc_a_id = upload_res.json()["document_id"]

    # User B attempts to query retrieval explicitly targeting User A's document_id
    search_res = client.post(
        "/retrieval/search",
        headers=headers_b,
        json={"query": "tax lien", "document_id": doc_a_id},
    )
    # Must be 422 or 404 because User B does not own doc_a_id
    assert search_res.status_code in (404, 422)

    # User B attempts to query RAG targeting User A's document_id
    rag_res = client.post(
        "/rag/ask",
        headers=headers_b,
        json={"question": "What is the lien amount?", "document_id": doc_a_id},
    )
    assert rag_res.status_code in (404, 422)


def test_upload_and_rag_rate_limiting(client):
    GLOBAL_RATE_LIMITER.reset()
    token = _register_user(client, "ratelimited_user@propertyintel.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload rate limit is 5 in settings
    for _ in range(5):
        resp = client.post(
            "/documents/ingest",
            headers=headers,
            files={"file": ("doc.txt", io.BytesIO(b"Hello world content"), "text/plain")},
        )
        assert resp.status_code == 200

    # 6th upload should trigger 429
    blocked_resp = client.post(
        "/documents/ingest",
        headers=headers,
        files={"file": ("doc.txt", io.BytesIO(b"Hello world content"), "text/plain")},
    )
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers
    GLOBAL_RATE_LIMITER.reset()
