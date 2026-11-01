"""Unit and integration tests for Phase 12 property risk assessment and due diligence intelligence."""

from __future__ import annotations

import io
from typing import Any
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
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
from app.schemas.property_risk import (
    PropertyRiskAssessmentResponse,
    PropertyRiskAssessmentStatusResponse,
    PropertyRiskFindingResponse,
    RiskCategory,
    RiskFindingStatus,
    RiskSeverity,
)
from app.services.auth_service import AuthService
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
        jwt_secret_key="secret-key-32-characters-minimum-risk-assessment-test",
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
def client(auth_srv, prop_srv, extraction_srv, risk_srv, sqlite_engine):
    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[auth.get_auth_service] = lambda: auth_srv
    app.dependency_overrides[get_settings] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_settings_dep] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_property_service] = lambda: prop_srv
    app.dependency_overrides[properties.get_extraction_service] = lambda: extraction_srv
    app.dependency_overrides[properties.get_risk_assessment_service] = lambda: risk_srv

    doc_store = FakeDocumentStore(engine=sqlite_engine)
    app.dependency_overrides[documents.get_document_store] = lambda: doc_store
    app.dependency_overrides[properties.get_document_store] = lambda: doc_store

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str, password: str = "StrongPass123!") -> str:
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


def _seed_document_and_chunks(
    engine,
    doc_id: str,
    owner_id: str,
    property_id: str,
    filename: str,
    content: str,
    doc_status: str = "processed",
):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            INSERT INTO documents (
                id, owner_id, property_id, filename, source_type, status,
                content_sha256, extracted_characters, chunk_count, page_count,
                warnings, detail, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'txt', ?, 'hash_' || ?, ?, 1, 1, '[]', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (doc_id, owner_id, property_id, filename, doc_status, doc_id, len(content)),
        )
        conn.exec_driver_sql(
            """
            INSERT INTO property_documents (property_id, document_id, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (property_id, doc_id),
        )
        conn.exec_driver_sql(
            """
            INSERT INTO chunks (
                id, document_id, chunk_index, text, source_filename, source_type,
                page_number, start_offset, end_offset, metadata, embedding
            ) VALUES (?, ?, 0, ?, ?, 'txt', 1, 0, ?, '{}', '[0.1, 0.2]')
            """,
            (f"chunk_{doc_id}", doc_id, content, filename, len(content)),
        )


# --- Unit / Integration Tests --------------------------------------------

def test_risk_assessment_end_to_end_detection(client, sqlite_engine):
    """Verify detection of critical litigation, encumbrance, and missing approvals."""
    token = _register(client, "risk_owner@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Palm Grove"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Seed document with explicit adverse litigation and active bank charge
    doc_text = (
        "SALE AGREEMENT. Property: Palm Grove Flat 301, Mumbai. "
        "Seller: Ramesh Patel. Consideration: Rs. 65,00,000. Carpet area: 950 sq ft. "
        "Litigation note: Property is subject to pending civil suit CS/2023/104 in High Court with interim stay order. "
        "Encumbrance: Mortgaged to Apex Bank Limited under registered mortgage deed."
    )
    _seed_document_and_chunks(sqlite_engine, "doc_risk_1", owner_id, prop_id, "sale_agreement.txt", doc_text)

    # Trigger risk assessment
    res = client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["property_id"] == prop_id

    summary = body["summary"]
    assert summary["total_findings"] > 0
    assert summary["critical_count"] >= 1  # Litigation and/or Encumbrance detected

    findings = body["findings"]
    rules = {f["rule_key"]: f for f in findings}

    # Verify Litigation Finding
    assert "litigation_detected" in rules
    lit_finding = rules["litigation_detected"]
    assert lit_finding["severity"] == "critical"
    assert lit_finding["category"] == "legal_dispute"
    assert "pending civil suit" in lit_finding["reason"].lower() or "litigation" in lit_finding["reason"].lower()
    assert len(lit_finding["evidence"]) > 0

    # Verify Encumbrance Finding
    assert "encumbrance_detected" in rules
    enc_finding = rules["encumbrance_detected"]
    assert enc_finding["severity"] == "critical"
    assert "mortgage" in enc_finding["reason"].lower()

    # Verify Missing Approvals (OC & CC absence treated as diligence gap)
    assert "missing_occupancy_certificate" in rules
    oc_finding = rules["missing_occupancy_certificate"]
    assert oc_finding["severity"] == "medium"
    assert "not found" in oc_finding["title"].lower()


def test_cross_document_conflicts_generate_high_severity_risks(client, sqlite_engine):
    """Conflicting monetary figures and areas between documents must generate high severity risks."""
    token = _register(client, "conflict_risk@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Twin Towers"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Document 1: Sale Deed with 85 Lakhs and 1200 sq ft
    doc1 = (
        "CONVEYANCE DEED. Property: Twin Towers Flat 101. "
        "Vendor: Rajesh Kumar. Consideration: Rs. 85,00,000. Carpet area: 1,200 sq.ft."
    )
    _seed_document_and_chunks(sqlite_engine, "doc_c1", owner_id, prop_id, "conveyance_deed.txt", doc1)

    # Document 2: Agreement with 95 Lakhs and 1450 sq ft
    doc2 = (
        "AGREEMENT TO SELL. Property: Twin Towers Flat 101. "
        "Vendor: Rajesh Kumar. Consideration: Rs. 95,00,000. Carpet area: 1,450 sq.ft."
    )
    _seed_document_and_chunks(sqlite_engine, "doc_c2", owner_id, prop_id, "agreement_to_sell.txt", doc2)

    res = client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)
    assert res.status_code == 200
    body = res.json()
    rules = {f["rule_key"]: f for f in body["findings"]}

    # Conflicting financial consideration
    assert "financial_price_conflict" in rules
    price_risk = rules["financial_price_conflict"]
    assert price_risk["severity"] == "high"
    assert price_risk["category"] == "financial"
    # Preserves evidence from both documents
    assert len(price_risk["evidence"]) >= 2
    filenames = {e["filename"] for e in price_risk["evidence"]}
    assert "conveyance_deed.txt" in filenames
    assert "agreement_to_sell.txt" in filenames

    # Conflicting carpet area
    assert "area_conflict" in rules
    area_risk = rules["area_conflict"]
    assert area_risk["severity"] == "high"
    assert area_risk["category"] == "property_identity"


def test_finding_status_patch_and_summary_update(client, sqlite_engine):
    """User can mark a finding as under_review or resolved with custom notes."""
    token = _register(client, "reviewer@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Review Test"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    doc_text = "AGREEMENT. Property: Review Test Unit 5. Consideration: Rs. 40,00,000. Carpet area: 700 sq ft."
    _seed_document_and_chunks(sqlite_engine, "doc_rev", owner_id, prop_id, "agreement.txt", doc_text)

    # Run assessment
    res = client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)
    assert res.status_code == 200
    findings = res.json()["findings"]
    assert len(findings) > 0

    first_finding = findings[0]
    risk_id = first_finding["risk_id"]

    # PATCH finding status to under_review
    patch_res = client.patch(
        f"/properties/{prop_id}/risk-assessment/findings/{risk_id}",
        headers=headers,
        json={"status": "under_review", "user_notes": "Advocate Sharma reviewing title search."},
    )
    assert patch_res.status_code == 200
    updated_finding = patch_res.json()
    assert updated_finding["status"] == "under_review"
    assert updated_finding["user_notes"] == "Advocate Sharma reviewing title search."

    # Verify updated assessment summary
    get_res = client.get(f"/properties/{prop_id}/risk-assessment", headers=headers)
    assert get_res.status_code == 200
    summary = get_res.json()["summary"]
    assert summary["under_review_count"] >= 1


def test_reassessment_preserves_user_reviewed_status(client, sqlite_engine):
    """Reassessment retains user-reviewed statuses and notes rather than overwriting with 'open'."""
    token = _register(client, "preserve_review@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Preserve Test"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    doc_text = "SALE DEED. Property: Preserve Test Unit 1. Consideration: Rs. 50,00,000. Carpet area: 800 sq ft."
    _seed_document_and_chunks(sqlite_engine, "doc_pres", owner_id, prop_id, "deed.txt", doc_text)

    # 1. First assessment
    res1 = client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)
    findings = res1.json()["findings"]
    oc_finding = next(f for f in findings if f["rule_key"] == "missing_occupancy_certificate")

    # 2. User marks missing OC as 'dismissed' (e.g. Under-construction project where OC not yet due)
    client.patch(
        f"/properties/{prop_id}/risk-assessment/findings/{oc_finding['risk_id']}",
        headers=headers,
        json={"status": "dismissed", "user_notes": "Project is under construction; OC due Dec 2026."},
    )

    # 3. Force refresh reassessment
    res2 = client.post(f"/properties/{prop_id}/risk-assessment/refresh", headers=headers)
    assert res2.status_code == 200
    refreshed_findings = res2.json()["findings"]
    refreshed_oc = next(f for f in refreshed_findings if f["rule_key"] == "missing_occupancy_certificate")

    # Status and user notes must be preserved!
    assert refreshed_oc["status"] == "dismissed"
    assert "OC due Dec 2026" in refreshed_oc["user_notes"]


def test_security_tenant_isolation(client, sqlite_engine):
    """User B cannot access or modify risk assessment of User A's property."""
    token_a = _register(client, "user_a@propertyrag.com")
    token_b = _register(client, "user_b@propertyrag.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates property & assessment
    prop_a = client.post("/properties", headers=headers_a, json={"name": "User A Property"}).json()
    prop_a_id = prop_a["id"]
    _seed_document_and_chunks(
        sqlite_engine, "doc_a", prop_a["owner_id"], prop_a_id, "doc_a.txt", "Some agreement content"
    )

    client.post(f"/properties/{prop_a_id}/risk-assessment", headers=headers_a)

    # User B attempts to access User A's assessment
    get_res = client.get(f"/properties/{prop_a_id}/risk-assessment", headers=headers_b)
    assert get_res.status_code == 404

    # User B attempts to trigger assessment on User A's property
    post_res = client.post(f"/properties/{prop_a_id}/risk-assessment", headers=headers_b)
    assert post_res.status_code == 404

    # User B attempts to update finding of User A's property
    patch_res = client.patch(
        f"/properties/{prop_a_id}/risk-assessment/findings/some_id",
        headers=headers_b,
        json={"status": "resolved"},
    )
    assert patch_res.status_code == 404


def test_scanned_ocr_required_documents_generate_completeness_risk(client, sqlite_engine):
    """Documents marked ocr_required generate documentation completeness risks."""
    token = _register(client, "ocr_tester@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Scanned Property"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Seed document with status 'ocr_required'
    _seed_document_and_chunks(
        sqlite_engine, "doc_scanned", owner_id, prop_id, "scanned_index_ii.pdf", "Scanned content", doc_status="ocr_required"
    )

    res = client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)
    assert res.status_code == 200
    findings = res.json()["findings"]
    rules = {f["rule_key"]: f for f in findings}

    assert "scanned_ocr_required_docs" in rules
    ocr_risk = rules["scanned_ocr_required_docs"]
    assert ocr_risk["category"] == "documentation_completeness"
    assert ocr_risk["severity"] == "medium"
    assert "OCR" in ocr_risk["title"]


def test_assessment_status_lightweight_endpoint(client, sqlite_engine):
    """Status endpoint returns accurate metadata without loading full findings list."""
    token = _register(client, "status_test@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Status Property"}).json()
    prop_id = prop["id"]

    # Before assessment
    res0 = client.get(f"/properties/{prop_id}/risk-assessment/status", headers=headers)
    assert res0.status_code == 200
    assert res0.json()["status"] == "not_started"

    # Seed doc and assess
    _seed_document_and_chunks(
        sqlite_engine, "doc_st", prop["owner_id"], prop_id, "doc.txt", "SALE DEED. Unit 1. Rs. 20,00,000."
    )
    client.post(f"/properties/{prop_id}/risk-assessment", headers=headers)

    # After assessment
    res1 = client.get(f"/properties/{prop_id}/risk-assessment/status", headers=headers)
    assert res1.status_code == 200
    body = res1.json()
    assert body["status"] == "completed"
    assert body["total_findings"] > 0
    assert body["is_stale"] is False
