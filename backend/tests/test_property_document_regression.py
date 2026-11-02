"""Regression tests verifying property document association, extraction, and risk assessment pipeline.

Covers:
1. Uploaded documents appear under the correct property (upload with property_id and explicit association).
2. Documents associated with a property are retrieved by extraction.
3. TXT documents produce extracted facts.
4. Extraction results persist in the database.
5. Risk assessment uses associated documents.
6. Assessment document count reflects actual evaluated documents.
7. Missing-document findings are distinguishable from evidence-backed findings.
8. Cross-user isolation remains intact (cross-user document access and query isolation).
9. Reassessment preserves user reviewer actions (status and notes).
"""

from __future__ import annotations

import io
from typing import Any
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_auth_service, get_current_user
from app.api.routes import auth, documents, properties
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import (
    Chunk,
    Document,
    Property,
    PropertyDocument,
    PropertyExtraction,
    PropertyRiskAssessment,
    PropertyRiskFinding,
    User,
)
from app.main import create_app
from app.schemas.property_risk import RiskFindingStatus, RiskSeverity
from app.services.auth_service import AuthService
from app.services.document_ingestion import DocumentIngestionService
from app.services.embedding_service import EmbeddingService
from app.services.property_extraction import PropertyExtractionService
from app.services.property_risk_assessment import PropertyRiskAssessmentService
from app.services.property_service import PropertyService
from tests.fakes import FakeDocumentStore, FakeEmbeddingProvider, FakeLLMService


@pytest.fixture
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def connect(dbapi_con, con_record):
        dbapi_con.create_function("to_tsvector", 2, lambda a, b: "", deterministic=True)

    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Property.__table__,
            Document.__table__,
            PropertyDocument.__table__,
            PropertyExtraction.__table__,
            PropertyRiskAssessment.__table__,
            PropertyRiskFinding.__table__,
            Chunk.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def app_settings():
    return Settings(
        jwt_secret_key="secret-key-32-characters-minimum-regression-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        rate_limit_upload_per_minute=60,
        rate_limit_rag_per_minute=60,
        embedding_dimensions=8,
    )


@pytest.fixture
def auth_srv(sqlite_engine, app_settings):
    return AuthService(settings=app_settings, engine=sqlite_engine)


@pytest.fixture
def prop_srv(sqlite_engine, app_settings):
    return PropertyService(settings=app_settings, engine=sqlite_engine)


@pytest.fixture
def fake_doc_store(sqlite_engine):
    return FakeDocumentStore(engine=sqlite_engine)


@pytest.fixture
def fake_embedding_srv(app_settings):
    provider = FakeEmbeddingProvider(dimensions=8)
    return EmbeddingService(settings=app_settings, provider=provider)


@pytest.fixture
def extraction_srv(sqlite_engine, app_settings):
    fake_llm = FakeLLMService(response="")
    return PropertyExtractionService(
        settings=app_settings,
        llm_service=fake_llm,
        engine=sqlite_engine,
    )


@pytest.fixture
def risk_srv(sqlite_engine, app_settings, extraction_srv):
    return PropertyRiskAssessmentService(
        settings=app_settings,
        extraction_service=extraction_srv,
        engine=sqlite_engine,
    )


@pytest.fixture
def client(auth_srv, prop_srv, extraction_srv, risk_srv, fake_doc_store, fake_embedding_srv, sqlite_engine):
    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[auth.get_auth_service] = lambda: auth_srv
    app.dependency_overrides[get_auth_service] = lambda: auth_srv
    app.dependency_overrides[get_settings] = lambda: auth_srv.settings
    app.dependency_overrides[documents.get_settings_dep] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_settings_dep] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_property_service] = lambda: prop_srv
    app.dependency_overrides[properties.get_extraction_service] = lambda: extraction_srv
    app.dependency_overrides[properties.get_risk_assessment_service] = lambda: risk_srv
    app.dependency_overrides[documents.get_property_service] = lambda: prop_srv
    app.dependency_overrides[documents.get_document_store] = lambda: fake_doc_store
    app.dependency_overrides[documents.get_embedding_service] = lambda: fake_embedding_srv

    def _get_ingestion_service():
        return DocumentIngestionService(
            settings=auth_srv.settings,
            embedding_service=fake_embedding_srv,
            store=fake_doc_store,
        )

    app.dependency_overrides[documents.get_ingestion_service] = _get_ingestion_service

    with TestClient(app) as test_client:
        yield test_client


def auth_header(client: TestClient, email: str = "reg_test@example.com") -> tuple[dict[str, str], str]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = resp.json()["access_token"]
    user_id = resp.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


class TestPropertyDocumentRegression:
    def test_property_document_association_and_listing(self, client):
        """1. Uploaded documents appear under the correct property after association."""
        headers, user_id = auth_header(client, "user1@example.com")

        # Create property
        prop_resp = client.post(
            "/api/v1/properties",
            headers=headers,
            json={"name": "Taj Mahal", "address": "Agra, UP"},
        )
        assert prop_resp.status_code == 201
        prop_id = prop_resp.json()["id"]

        # Ingest document
        file_content = b"Sale Deed. Owner: Aarav Sharma. Sale price: 8,500,000 INR. Area: 1500 sq ft."
        upload_resp = client.post(
            "/api/v1/documents/ingest",
            headers=headers,
            files={"file": ("sale_deed.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["document_id"]

        # Before association: property document list has 0
        list_before = client.get(f"/api/v1/properties/{prop_id}/documents", headers=headers)
        assert list_before.status_code == 200
        assert list_before.json()["total"] == 0

        # Associate document with property
        assoc_resp = client.post(
            f"/api/v1/properties/{prop_id}/documents/{doc_id}/associate",
            headers=headers,
        )
        assert assoc_resp.status_code == 200
        assert assoc_resp.json()["associated"] is True

        # After association: property document list returns the document
        list_after = client.get(f"/api/v1/properties/{prop_id}/documents", headers=headers)
        assert list_after.status_code == 200
        assert list_after.json()["total"] == 1
        assert list_after.json()["items"][0]["document_id"] == doc_id
        assert list_after.json()["items"][0]["filename"] == "sale_deed.txt"

    def test_txt_documents_produce_extracted_facts_and_persist(self, client):
        """2, 3, 4. TXT documents associated with property produce extracted facts that persist."""
        headers, user_id = auth_header(client, "user2@example.com")

        prop_resp = client.post(
            "/api/v1/properties",
            headers=headers,
            json={"name": "Taj Mahal", "address": "Agra"},
        )
        prop_id = prop_resp.json()["id"]

        # Ingest TXT document
        content = (
            b"Document Type: Sale Deed\n"
            b"Property Name: Taj Mahal\n"
            b"Owner: Rajesh Kumar\n"
            b"Sale Consideration: Rs. 9,200,000\n"
            b"Carpet Area: 1420 sq ft\n"
            b"Litigation: Pending suit OS-2024-118 in District Court regarding boundary line."
        )
        upload_resp = client.post(
            "/api/v1/documents/ingest",
            headers=headers,
            files={"file": ("02_sale_deed.txt", io.BytesIO(content), "text/plain")},
        )
        doc_id = upload_resp.json()["document_id"]

        # Associate
        client.post(
            f"/api/v1/properties/{prop_id}/documents/{doc_id}/associate",
            headers=headers,
        )

        # Trigger extraction
        extract_resp = client.post(f"/api/v1/properties/{prop_id}/extract", headers=headers)
        assert extract_resp.status_code == 200
        ext_data = extract_resp.json()

        assert ext_data["document_count"] == 1
        assert ext_data["status"] == "completed"

        # Check extracted facts from TXT heuristic/LLM
        ident = ext_data["data"]["identity"]
        fin = ext_data["data"]["financial"]

        assert fin["sale_price"]["extracted_value"] is not None
        assert ident["carpet_area"]["extracted_value"] is not None

        # Verify extraction persistence via GET
        get_ext = client.get(f"/api/v1/properties/{prop_id}/extraction", headers=headers)
        assert get_ext.status_code == 200
        assert get_ext.json()["document_count"] == 1
        assert get_ext.json()["data"]["financial"]["sale_price"]["extracted_value"] == fin["sale_price"]["extracted_value"]

    def test_risk_assessment_evaluates_documents_and_evidence(self, client):
        """5, 6, 7. Risk assessment evaluates associated documents, count reflects evaluated documents, and findings distinguish evidence."""
        headers, user_id = auth_header(client, "user3@example.com")

        prop_resp = client.post(
            "/api/v1/properties",
            headers=headers,
            json={"name": "Taj Mahal", "address": "Agra"},
        )
        prop_id = prop_resp.json()["id"]

        # Baseline: 0 documents associated -> 9 missing-document findings, 0 evaluated docs
        assess_0 = client.post(f"/api/v1/properties/{prop_id}/risk-assessment", headers=headers)
        assert assess_0.status_code == 200
        assert assess_0.json()["document_count"] == 0
        assert assess_0.json()["summary"]["total_findings"] == 9
        for f in assess_0.json()["findings"]:
            assert len(f["evidence"]) == 0, "Missing-document findings must have empty evidence"

        # Now associate a document with litigation & encumbrance
        content = (
            b"Sale Deed for Taj Mahal. Owner: Aarav Sharma.\n"
            b"Total consideration: Rs. 8,500,000.\n"
            b"Carpet area: 1500 sq ft.\n"
            b"Subject to pending litigation in High Court regarding title dispute.\n"
            b"Property is subject to active mortgage bank charge with State Bank."
        )
        doc_resp = client.post(
            "/api/v1/documents/ingest",
            headers=headers,
            files={"file": ("deed.txt", io.BytesIO(content), "text/plain")},
        )
        doc_id = doc_resp.json()["document_id"]
        client.post(f"/api/v1/properties/{prop_id}/documents/{doc_id}/associate", headers=headers)

        # Trigger reassessment
        assess_1 = client.post(f"/api/v1/properties/{prop_id}/risk-assessment/refresh", headers=headers)
        assert assess_1.status_code == 200
        data_1 = assess_1.json()

        # Document count reflects actual evaluated documents (1)
        assert data_1["document_count"] == 1

        # Evidence-backed findings are present
        evidence_backed = [f for f in data_1["findings"] if len(f["evidence"]) > 0]
        assert len(evidence_backed) > 0, "Evidence-backed findings should have evidence items"

        # Missing-document findings have empty evidence
        missing_findings = [f for f in data_1["findings"] if f["rule_key"].startswith("missing_")]
        for mf in missing_findings:
            assert len(mf["evidence"]) == 0

    def test_cross_user_isolation(self, client):
        """8. Cross-user isolation: User B cannot access, associate, or evaluate User A's documents."""
        headers_a, user_a_id = auth_header(client, "user_a@example.com")
        headers_b, user_b_id = auth_header(client, "user_b@example.com")

        # User A creates property and document
        prop_a = client.post("/api/v1/properties", headers=headers_a, json={"name": "Prop A"}).json()["id"]
        doc_a = client.post(
            "/api/v1/documents/ingest",
            headers=headers_a,
            files={"file": ("doc_a.txt", io.BytesIO(b"Secret Document A"), "text/plain")},
        ).json()["document_id"]

        # User B cannot associate User A's document to User B's property
        prop_b = client.post("/api/v1/properties", headers=headers_b, json={"name": "Prop B"}).json()["id"]
        assoc_deny = client.post(f"/api/v1/properties/{prop_b}/documents/{doc_a}/associate", headers=headers_b)
        assert assoc_deny.status_code in (403, 404)

        # User B extraction and risk assessment sees 0 documents
        ext_b = client.post(f"/api/v1/properties/{prop_b}/extract", headers=headers_b)
        assert ext_b.json()["document_count"] == 0

        risk_b = client.post(f"/api/v1/properties/{prop_b}/risk-assessment", headers=headers_b)
        assert risk_b.json()["document_count"] == 0

    def test_reassessment_preserves_reviewer_actions(self, client):
        """9. Reassessment does not destroy reviewer actions (status and notes)."""
        headers, user_id = auth_header(client, "reviewer@example.com")

        prop_id = client.post("/api/v1/properties", headers=headers, json={"name": "Review Prop"}).json()["id"]
        assess_init = client.post(f"/api/v1/properties/{prop_id}/risk-assessment", headers=headers).json()

        findings = assess_init["findings"]
        first_finding = findings[0]
        risk_id = first_finding["risk_id"]

        # Reviewer marks finding as under_review with notes
        update_resp = client.patch(
            f"/api/v1/properties/{prop_id}/risk-assessment/findings/{risk_id}",
            headers=headers,
            json={"status": "under_review", "user_notes": "Attorney verifying title search."},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "under_review"
        assert update_resp.json()["user_notes"] == "Attorney verifying title search."

        # Reassess
        reassess = client.post(f"/api/v1/properties/{prop_id}/risk-assessment/refresh", headers=headers).json()
        matching = [f for f in reassess["findings"] if f["risk_id"] == risk_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "under_review"
        assert matching[0]["user_notes"] == "Attorney verifying title search."
