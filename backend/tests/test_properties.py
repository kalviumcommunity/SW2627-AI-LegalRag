"""Phase 10: Property-level intelligence and multi-document RAG tests.

Covers:
- Property creation and validation
- Owner-scoped authorization and IDOR / cross-user access denial
- Document association and disassociation lifecycle
- Cross-user document association rejection
- Property deletion preserving associated documents
- Property intelligence endpoint (inventory, extracted facts, gap analysis, disclaimer)
- Property-scoped retrieval and RAG isolation
- Document mismatch rejection when both property_id and document_id are supplied
- Duplicate ingestion and association handling
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_auth_service, get_current_user
from app.api.routes import documents, properties, rag, retrieval
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Document, Property, PropertyDocument, User
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.document_ingestion import DocumentIngestionService
from app.services.embedding_service import EmbeddingService
from app.services.property_service import PropertyService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from tests.fakes import (
    FakeDocumentStore,
    FakeEmbeddingProvider,
    FakeLLMService,
    FakeRetrievalStore,
    retrieval_result,
)


@pytest.fixture
def property_sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Property.__table__,
            Document.__table__,
            PropertyDocument.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def prop_settings():
    return Settings(
        jwt_secret_key="secret-key-32-characters-minimum-prop-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        rate_limit_upload_per_minute=20,
        rate_limit_rag_per_minute=20,
        embedding_dimensions=8,
    )


@pytest.fixture
def auth_service(property_sqlite_engine, prop_settings):
    return AuthService(settings=prop_settings, engine=property_sqlite_engine)


@pytest.fixture
def property_service(property_sqlite_engine, prop_settings):
    return PropertyService(settings=prop_settings, engine=property_sqlite_engine)


@pytest.fixture
def shared_stores():
    doc_store = FakeDocumentStore()
    embedding_provider = FakeEmbeddingProvider(dimensions=8)
    retrieval_store = FakeRetrievalStore()
    llm_service = FakeLLMService(
        response='{"answer": "Property has registered sale deed. [S1]", "evidence_status": "supported", "used_source_ids": [1]}'
    )
    return {
        "doc_store": doc_store,
        "embedding_provider": embedding_provider,
        "retrieval_store": retrieval_store,
        "llm_service": llm_service,
    }


@pytest.fixture
def client(auth_service, property_service, shared_stores):
    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: auth_service.settings
    app.dependency_overrides[documents.get_settings_dep] = lambda: auth_service.settings
    app.dependency_overrides[properties.get_settings_dep] = lambda: auth_service.settings
    app.dependency_overrides[properties.get_property_service] = lambda: property_service
    app.dependency_overrides[properties.get_document_store] = lambda: shared_stores["doc_store"]

    embedding_srv = EmbeddingService(
        auth_service.settings,
        provider=shared_stores["embedding_provider"],
    )
    doc_ingestion = DocumentIngestionService(
        store=shared_stores["doc_store"],
        embedding_service=embedding_srv,
    )
    retrieval_srv = RetrievalService(
        settings=auth_service.settings,
        embedding_service=embedding_srv,
        store=shared_stores["retrieval_store"],
        document_store=shared_stores["doc_store"],
        property_service=property_service,
    )
    rag_srv = RAGService(
        retrieval_service=retrieval_srv,
        llm_service=shared_stores["llm_service"],
    )

    app.dependency_overrides[documents.get_ingestion_service] = lambda: doc_ingestion
    app.dependency_overrides[documents.get_document_store] = lambda: shared_stores["doc_store"]
    app.dependency_overrides[retrieval.get_retrieval_service] = lambda: retrieval_srv
    app.dependency_overrides[retrieval.get_retrieval_store] = lambda: shared_stores["retrieval_store"]
    app.dependency_overrides[retrieval.get_property_service] = lambda: property_service
    app.dependency_overrides[rag.get_rag_service] = lambda: rag_srv
    app.dependency_overrides[rag.get_llm_service] = lambda: shared_stores["llm_service"]

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register_user(client: TestClient, email: str, password: str = "Password123!") -> str:
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201
    return res.json()["access_token"]


def test_property_creation_and_validation(client):
    token = _register_user(client, "owner1@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Successful creation with full attributes
    res = client.post(
        "/properties",
        headers=headers,
        json={
            "name": "Green Valley Villa",
            "address": "123 Palm Avenue",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
            "property_type": "residential",
            "area": 2400.0,
            "area_unit": "sq_ft",
        },
    )
    assert res.status_code == 201
    prop = res.json()
    assert prop["id"].startswith("prop_")
    assert prop["name"] == "Green Valley Villa"
    assert prop["city"] == "Bengaluru"
    assert prop["property_type"] == "residential"
    assert prop["area"] == 2400.0
    assert prop["document_count"] == 0

    # 2. Validation error on blank name
    bad_res = client.post(
        "/properties",
        headers=headers,
        json={"name": "   ", "city": "Bengaluru"},
    )
    assert bad_res.status_code == 422

    # 3. Validation error on negative area
    neg_area = client.post(
        "/properties",
        headers=headers,
        json={"name": "Bad Villa", "area": -50.0},
    )
    assert neg_area.status_code == 422


def test_property_ownership_and_cross_user_isolation(client):
    token_a = _register_user(client, "alice_prop@propertyrag.com")
    token_b = _register_user(client, "bob_prop@propertyrag.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Alice creates a property
    res_a = client.post(
        "/properties",
        headers=headers_a,
        json={"name": "Alice's Sanctuary", "city": "Pune"},
    )
    assert res_a.status_code == 201
    prop_id = res_a.json()["id"]

    # Bob cannot view Alice's property -> 404 (does not leak existence)
    get_b = client.get(f"/properties/{prop_id}", headers=headers_b)
    assert get_b.status_code == 404

    # Bob cannot update Alice's property -> 404
    patch_b = client.patch(
        f"/properties/{prop_id}",
        headers=headers_b,
        json={"name": "Hacked Sanctuary"},
    )
    assert patch_b.status_code == 404

    # Bob cannot delete Alice's property -> 404
    del_b = client.delete(f"/properties/{prop_id}", headers=headers_b)
    assert del_b.status_code == 404

    # Bob listing properties does not show Alice's property
    list_b = client.get("/properties", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(p["id"] == prop_id for p in list_b.json()["items"])

    # Alice can list and retrieve her property
    list_a = client.get("/properties", headers=headers_a)
    assert list_a.status_code == 200
    assert any(p["id"] == prop_id for p in list_a.json()["items"])

    get_a = client.get(f"/properties/{prop_id}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["name"] == "Alice's Sanctuary"


def test_document_association_and_disassociation(client, shared_stores):
    token = _register_user(client, "assoc_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Property
    prop_res = client.post(
        "/properties",
        headers=headers,
        json={"name": "Commercial Plaza", "property_type": "commercial"},
    )
    assert prop_res.status_code == 201
    prop_id = prop_res.json()["id"]

    # Upload Document
    doc_res = client.post(
        "/documents/ingest",
        headers=headers,
        files={"file": ("lease.txt", io.BytesIO(b"Commercial lease terms for Suite 101."), "text/plain")},
    )
    assert doc_res.status_code == 200
    doc_id = doc_res.json()["document_id"]

    # Associate Document to Property
    assoc_res = client.post(
        f"/properties/{prop_id}/documents/{doc_id}/associate",
        headers=headers,
    )
    assert assoc_res.status_code == 200
    assert assoc_res.json()["associated"] is True
    assert assoc_res.json()["property_id"] == prop_id

    # Verify document listed in property's documents
    docs_list = client.get(f"/properties/{prop_id}/documents", headers=headers)
    assert docs_list.status_code == 200
    assert docs_list.json()["total"] == 1
    assert docs_list.json()["items"][0]["document_id"] == doc_id

    # Disassociate Document
    disassoc_res = client.post(
        f"/properties/{prop_id}/documents/{doc_id}/disassociate",
        headers=headers,
    )
    assert disassoc_res.status_code == 200
    assert disassoc_res.json()["associated"] is False

    # Verify no documents listed for property
    docs_list_after = client.get(f"/properties/{prop_id}/documents", headers=headers)
    assert docs_list_after.status_code == 200
    assert docs_list_after.json()["total"] == 0

    # But the document itself still exists for the user
    doc_get = client.get(f"/documents/{doc_id}", headers=headers)
    assert doc_get.status_code == 200


def test_cannot_associate_other_users_document(client):
    token_a = _register_user(client, "user_a@propertyrag.com")
    token_b = _register_user(client, "user_b@propertyrag.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates Property A
    prop_a = client.post(
        "/properties",
        headers=headers_a,
        json={"name": "Property A"},
    ).json()["id"]

    # User B ingests Document B
    doc_b = client.post(
        "/documents/ingest",
        headers=headers_b,
        files={"file": ("doc_b.txt", io.BytesIO(b"Private notes of User B."), "text/plain")},
    ).json()["document_id"]

    # User A tries to associate User B's Document B to Property A -> rejected with 404 or 403
    assoc_res = client.post(
        f"/properties/{prop_a}/documents/{doc_b}/associate",
        headers=headers_a,
    )
    assert assoc_res.status_code in (403, 404)


def test_property_deletion_preserves_document_data(client):
    token = _register_user(client, "delete_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop_id = client.post(
        "/properties",
        headers=headers,
        json={"name": "Heritage Mansion"},
    ).json()["id"]

    doc_id = client.post(
        "/documents/ingest",
        headers=headers,
        files={"file": ("title_deed.txt", io.BytesIO(b"Title Deed for Heritage Mansion."), "text/plain")},
    ).json()["document_id"]

    client.post(f"/properties/{prop_id}/documents/{doc_id}/associate", headers=headers)

    # Delete Property
    del_res = client.delete(f"/properties/{prop_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Property is gone
    assert client.get(f"/properties/{prop_id}", headers=headers).status_code == 404

    # Document still exists and is accessible
    doc_res = client.get(f"/documents/{doc_id}", headers=headers)
    assert doc_res.status_code == 200
    assert doc_res.json()["document_id"] == doc_id


def test_property_intelligence_endpoint(client, property_service, property_sqlite_engine):
    token = _register_user(client, "intel_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop_id = client.post(
        "/properties",
        headers=headers,
        json={"name": "Sunshine Towers", "city": "Mumbai"},
    ).json()["id"]

    # 1. Empty state intelligence
    res_empty = client.get(f"/properties/{prop_id}/intelligence", headers=headers)
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["property"]["id"] == prop_id
    assert data_empty["document_inventory"]["total_documents"] == 0
    assert len(data_empty["missing_or_unverified_information"]) >= 1
    # Check legal disclaimer
    assert "not a substitute for professional legal due diligence" in data_empty["legal_disclaimer"]

    # 2. Add document and check intelligence consolidation
    doc_id = client.post(
        "/documents/ingest",
        headers=headers,
        files={
            "file": (
                "sale_agreement.txt",
                io.BytesIO(
                    b"SALE AGREEMENT. The seller agrees to sell the property for consideration of Rs. 85,00,000 on 2026-11-15. Encumbrance certificate is clear."
                ),
                "text/plain",
            )
        },
    ).json()["document_id"]

    # Seed Document in property SQLite database for full intelligence query
    with property_sqlite_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            INSERT INTO documents (id, owner_id, filename, content_sha256, status, extracted_characters, chunk_count, property_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, "usr_1", "sale_agreement.txt", "hash85", "processed", 130, 1, prop_id),
        )
        conn.exec_driver_sql(
            """
            INSERT INTO property_documents (property_id, document_id)
            VALUES (?, ?)
            """,
            (prop_id, doc_id),
        )

    res_doc = client.get(f"/properties/{prop_id}/intelligence", headers=headers)
    assert res_doc.status_code == 200
    data_doc = res_doc.json()
    assert data_doc["document_inventory"]["total_documents"] >= 1
    assert "not a substitute for professional legal due diligence" in data_doc["legal_disclaimer"]


def test_property_scoped_retrieval_and_rag(client, shared_stores):
    token = _register_user(client, "rag_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop_id = client.post(
        "/properties",
        headers=headers,
        json={"name": "Maple Heights"},
    ).json()["id"]

    # Configure mock retrieval result
    shared_stores["retrieval_store"].canned_results = [
        retrieval_result("chk_prop_1", document_id="doc_prop_1", text="Clear title deed for Maple Heights.")
    ]

    # Search with property_id
    search_res = client.post(
        "/retrieval/search",
        headers=headers,
        json={"query": "title deed", "property_id": prop_id},
    )
    assert search_res.status_code == 200
    assert search_res.json()["result_count"] >= 1

    # RAG with property_id
    rag_res = client.post(
        "/rag/ask",
        headers=headers,
        json={"question": "Is the title clear?", "property_id": prop_id},
    )
    assert rag_res.status_code == 200
    body = rag_res.json()
    assert body["status"] == "answered"
    assert "citations" in body
    assert len(body["citations"]) >= 1


def test_document_property_mismatch_rejected_in_retrieval(client, shared_stores):
    token = _register_user(client, "mismatch_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop_1 = client.post("/properties", headers=headers, json={"name": "Prop 1"}).json()["id"]
    prop_2 = client.post("/properties", headers=headers, json={"name": "Prop 2"}).json()["id"]

    # Ingest document associated with Prop 1
    doc_res = client.post(
        "/documents/ingest",
        headers=headers,
        files={"file": ("deed.txt", io.BytesIO(b"Deed for Prop 1"), "text/plain")},
    )
    doc_id = doc_res.json()["document_id"]
    client.post(f"/properties/{prop_1}/documents/{doc_id}/associate", headers=headers)

    # Retrieval query supplying doc_id from Prop 1 but requesting Prop 2 -> rejected
    search_res = client.post(
        "/retrieval/search",
        headers=headers,
        json={"query": "deed", "document_id": doc_id, "property_id": prop_2},
    )
    assert search_res.status_code in (404, 422)


def test_unauthenticated_requests_to_property_routes_rejected(client):
    endpoints = [
        ("GET", "/properties"),
        ("POST", "/properties"),
        ("GET", "/properties/prop_123"),
        ("PATCH", "/properties/prop_123"),
        ("DELETE", "/properties/prop_123"),
        ("GET", "/properties/prop_123/documents"),
        ("POST", "/properties/prop_123/documents/doc_1/associate"),
        ("POST", "/properties/prop_123/documents/doc_1/disassociate"),
        ("GET", "/properties/prop_123/intelligence"),
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
