"""Unit and integration tests for Phase 11 structured property information extraction."""

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
from app.db.models import Chunk, Document, Property, PropertyDocument, PropertyExtraction, User
from app.main import create_app
from app.schemas.property_extraction import (
    PropertyExtractionData,
    PropertyExtractionResponse,
    PropertyExtractionStatusResponse,
)
from app.services.auth_service import AuthService
from app.services.document_ingestion import DocumentIngestionService
from app.services.embedding_service import EmbeddingService
from app.services.property_extraction import (
    PropertyExtractionService,
    normalize_date_string,
)
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
            Chunk.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def app_settings():
    return Settings(
        jwt_secret_key="secret-key-32-characters-minimum-extraction-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        rate_limit_upload_per_minute=30,
        rate_limit_rag_per_minute=30,
        embedding_dimensions=8,
    )


@pytest.fixture
def auth_srv(sqlite_engine, app_settings):
    return AuthService(settings=app_settings, engine=sqlite_engine)


@pytest.fixture
def prop_srv(sqlite_engine, app_settings):
    return PropertyService(settings=app_settings, engine=sqlite_engine)


MOCK_VALID_EXTRACTION_JSON = """{
  "property_identity": {
    "property_name": {"value": "Emerald Heights", "original_value": "Emerald Heights", "page_number": 1, "supporting_quote": "Emerald Heights Apartments", "confidence": 0.95},
    "property_address": {"value": "Plot 42, Sector 5, Kharghar, Navi Mumbai", "original_value": "Plot 42, Sector 5, Kharghar, Navi Mumbai", "page_number": 1, "supporting_quote": "situated at Plot 42, Sector 5, Kharghar, Navi Mumbai", "confidence": 0.95},
    "property_type": {"value": "residential apartment", "original_value": "residential apartment", "page_number": 1, "supporting_quote": "residential apartment unit", "confidence": 0.9},
    "unit_number": {"value": "Flat No. 402", "original_value": "Flat No. 402, 4th Floor", "page_number": 1, "supporting_quote": "Flat No. 402, 4th Floor", "confidence": 0.95},
    "carpet_area": {"value": "1250 sq ft", "original_value": "1,250 sq.ft. carpet area", "page_number": 2, "supporting_quote": "having a carpet area of 1,250 sq.ft.", "confidence": 0.95},
    "built_up_area": {"value": "1500 sq ft", "original_value": "1,500 sq.ft. super built-up", "page_number": 2, "supporting_quote": "1,500 sq.ft. super built-up area", "confidence": 0.9},
    "area_unit": {"value": "sq ft", "original_value": "sq.ft.", "page_number": 2, "supporting_quote": "in sq.ft.", "confidence": 0.9}
  },
  "financial_information": {
    "sale_price": {"value": "8500000", "original_value": "Rs. 85,00,000 (Rupees Eighty Five Lakhs)", "page_number": 3, "supporting_quote": "Total consideration of Rs. 85,00,000 paid by purchaser", "confidence": 0.95},
    "booking_amount": {"value": "500000", "original_value": "Rs. 5,00,000", "page_number": 3, "supporting_quote": "booking token amount of Rs. 5,00,000", "confidence": 0.9},
    "payment_schedule": {"value": "Construction linked 5-stage plan", "original_value": "Construction linked 5-stage plan", "page_number": 3, "supporting_quote": "payment shall follow a construction linked 5-stage plan", "confidence": 0.85},
    "maintenance_charges": {"value": "Rs. 3500 per month", "original_value": "Rs. 3,500/- per month", "page_number": 4, "supporting_quote": "monthly maintenance charges of Rs. 3,500/- per month", "confidence": 0.85},
    "deposits_and_additional_charges": {"value": "Clubhouse and car parking Rs. 2,00,000", "original_value": "Rs. 2,00,000 for parking", "page_number": 4, "supporting_quote": "one-time deposit of Rs. 2,00,000 for parking", "confidence": 0.85}
  },
  "ownership_legal": {
    "named_owner_or_seller": {"value": "Rajesh Kumar Sharma", "original_value": "Rajesh Kumar Sharma, Vendor", "page_number": 1, "supporting_quote": "executed between Rajesh Kumar Sharma, Vendor", "confidence": 0.95},
    "title_deed_references": {"value": "Registered Deed No. 1234/2022", "original_value": "Doc No. 1234 of 2022 Book I", "page_number": 2, "supporting_quote": "registered as Doc No. 1234 of 2022 Book I", "confidence": 0.9},
    "ownership_claims": {"value": "Freehold clear title", "original_value": "freehold marketable title", "page_number": 2, "supporting_quote": "vendor holds freehold marketable title", "confidence": 0.9},
    "encumbrance_information": {"value": "Free from all encumbrances", "original_value": "free from all encumbrances and liens", "page_number": 4, "supporting_quote": "property is free from all encumbrances and liens", "confidence": 0.9},
    "litigation_references": {"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}
  },
  "approvals": {
    "project_registration_references": {"value": "P51700012345", "original_value": "MahaRERA Reg No. P51700012345", "page_number": 1, "supporting_quote": "MahaRERA Reg No. P51700012345", "confidence": 0.95},
    "building_plan_approvals": {"value": "CIDCO Sanction CIDCO/BP/2021/89", "original_value": "CIDCO/BP/2021/89", "page_number": 2, "supporting_quote": "sanctioned building plan CIDCO/BP/2021/89", "confidence": 0.9},
    "completion_certificates": {"value": "CC-2023-456", "original_value": "CC Certificate CC-2023-456", "page_number": 5, "supporting_quote": "Completion certificate CC-2023-456 issued", "confidence": 0.9},
    "occupancy_certificates": {"value": "OC issued on 2024-01-15", "original_value": "OC No. 89/2024", "page_number": 5, "supporting_quote": "Occupancy certificate OC No. 89/2024", "confidence": 0.9},
    "fire_and_environmental_approvals": {"value": "Fire NOC valid till 2027", "original_value": "Fire NOC Ref FN-882", "page_number": 5, "supporting_quote": "Fire NOC Ref FN-882 valid till 2027", "confidence": 0.85}
  },
  "dates_obligations": {
    "agreement_date": {"value": "2022-04-10", "original_value": "10th April 2022", "page_number": 1, "supporting_quote": "Agreement made on this 10th April 2022", "confidence": 0.95},
    "possession_date": {"value": "2024-06-30", "original_value": "30th June 2024", "page_number": 3, "supporting_quote": "possession on or before 30th June 2024", "confidence": 0.9},
    "payment_deadlines": {"value": "Within 30 days of each slab completion", "original_value": "within 30 days of notice", "page_number": 3, "supporting_quote": "within 30 days of notice", "confidence": 0.8},
    "renewal_dates": {"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0},
    "contractual_obligations": {"value": "Interest at 9% for delayed payment", "original_value": "penalty interest of 9% p.a.", "page_number": 4, "supporting_quote": "penalty interest of 9% p.a.", "confidence": 0.85}
  }
}"""


@pytest.fixture
def fake_llm():
    return FakeLLMService(response=MOCK_VALID_EXTRACTION_JSON)


@pytest.fixture
def extraction_srv(sqlite_engine, app_settings, fake_llm):
    return PropertyExtractionService(
        settings=app_settings,
        llm_service=fake_llm,
        engine=sqlite_engine,
    )


@pytest.fixture
def client(auth_srv, prop_srv, extraction_srv, sqlite_engine):
    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[auth.get_auth_service] = lambda: auth_srv
    app.dependency_overrides[get_settings] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_settings_dep] = lambda: auth_srv.settings
    app.dependency_overrides[properties.get_property_service] = lambda: prop_srv
    app.dependency_overrides[properties.get_extraction_service] = lambda: extraction_srv

    doc_store = FakeDocumentStore(engine=sqlite_engine)
    app.dependency_overrides[documents.get_document_store] = lambda: doc_store
    app.dependency_overrides[properties.get_document_store] = lambda: doc_store

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str) -> str:
    res = client.post("/auth/register", json={"email": email, "password": "Password123!"})
    assert res.status_code == 201
    return res.json()["access_token"]


def _seed_document_and_chunks(engine, doc_id: str, owner_id: str, prop_id: str, filename: str, text: str):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            INSERT OR REPLACE INTO documents (id, owner_id, filename, source_type, content_sha256, status, extracted_characters, chunk_count, property_id, warnings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, owner_id, filename, "txt", f"hash_{doc_id}", "processed", len(text), 1, prop_id, "[]"),
        )
        conn.exec_driver_sql(
            """
            INSERT OR REPLACE INTO property_documents (property_id, document_id)
            VALUES (?, ?)
            """,
            (prop_id, doc_id),
        )
        conn.exec_driver_sql(
            """
            INSERT OR REPLACE INTO chunks (id, document_id, chunk_index, text, source_filename, source_type, page_number, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"chk_{doc_id}", doc_id, 0, text, filename, "txt", 1, "{}", "[0.1, 0.2]"),
        )


# --- Unit Tests: Normalization --------------------------------------------

def test_normalization_dates():
    assert normalize_date_string("2026-11-15") == "2026-11-15"
    assert normalize_date_string("15-11-2026") == "2026-11-15"
    assert normalize_date_string("15th November 2026") == "2026-11-15"
    assert normalize_date_string("November 15, 2026") == "2026-11-15"
    assert normalize_date_string("In the year 2026") == "2026"
    assert normalize_date_string("") is None
    assert normalize_date_string(None) is None


# --- Integration Tests: Structured Extraction -----------------------------

def test_extract_property_information_structured(client, sqlite_engine):
    token = _register(client, "owner_struct@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Property
    prop = client.post("/properties", headers=headers, json={"name": "Emerald Heights"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Seed Document with chunk
    sample_text = (
        "SALE DEED. Property: Emerald Heights Flat 402, Navi Mumbai. "
        "Carpet Area: 1,250 sq.ft. Consideration: Rs. 85,00,000 paid to Rajesh Kumar Sharma. "
        "MahaRERA Reg No. P51700012345. Execution date: 10th April 2022."
    )
    _seed_document_and_chunks(sqlite_engine, "doc_101", owner_id, prop_id, "sale_deed.txt", sample_text)

    # Trigger extraction
    res = client.post(f"/properties/{prop_id}/extract", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["document_count"] == 1
    assert body["is_stale"] is False

    data = body["data"]
    # Check Property Identity
    identity = data["identity"]
    assert identity["property_name"]["extracted_value"] == "Emerald Heights"
    assert identity["property_name"]["verification_status"] == "supported"
    assert identity["carpet_area"]["extracted_value"] == "1250 sq ft"
    assert identity["carpet_area"]["normalized_value"] == 1250.0
    assert identity["carpet_area"]["unit"] == "sq ft"
    assert identity["carpet_area"]["document_id"] == "doc_101"
    assert identity["carpet_area"]["filename"] == "sale_deed.txt"

    # Check Financials
    financial = data["financial"]
    assert financial["sale_price"]["normalized_value"] == 8500000.0
    assert financial["sale_price"]["unit"] == "INR"
    assert financial["sale_price"]["verification_status"] == "supported"
    assert financial["sale_price"]["document_id"] == "doc_101"

    # Check Ownership
    ownership = data["ownership_legal"]
    assert ownership["named_owner_or_seller"]["extracted_value"] == "Rajesh Kumar Sharma"
    assert ownership["named_owner_or_seller"]["verification_status"] == "supported"

    # Check Approvals
    approvals = data["approvals"]
    assert approvals["project_registration_references"]["extracted_value"] == "P51700012345"

    # Check Dates
    dates = data["dates_obligations"]
    assert dates["agreement_date"]["normalized_value"] == "2022-04-10"

    # Check Missing fields explicit handling (litigation, renewal dates were null in JSON)
    assert ownership["litigation_references"]["verification_status"] == "missing"
    assert "Litigation References / Legal Disputes" in data["missing_fields"]
    assert dates["renewal_dates"]["verification_status"] == "missing"


def test_malformed_llm_response_handled_gracefully(client, extraction_srv, sqlite_engine):
    token = _register(client, "malformed@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Malformed Test"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    sample_text = (
        "AGREEMENT TO SELL. Seller: John Doe. Consideration: INR 50,00,000. "
        "Carpet Area: 850 sq ft. Date: 2025-05-20."
    )
    _seed_document_and_chunks(sqlite_engine, "doc_malformed", owner_id, prop_id, "contract.txt", sample_text)

    # Set LLM to return completely invalid / corrupted JSON
    extraction_srv.llm_service = FakeLLMService(response="THIS IS NOT VALID JSON AT ALL {{{{ broken")

    # Should not crash; heuristic fallback should extract consideration, area, date
    res = client.post(f"/properties/{prop_id}/extract", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    data = body["data"]

    # Heuristic fallback extracted consideration
    assert data["financial"]["sale_price"]["normalized_value"] == 5000000.0
    assert data["financial"]["sale_price"]["verification_status"] in ("supported", "unverified")
    # Missing fields are safely cataloged
    assert len(data["missing_fields"]) > 0


def test_contradictory_documents_detected_and_preserved(client, extraction_srv, sqlite_engine):
    token = _register(client, "conflict@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Conflict Towers"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Document 1: Sale Agreement asserting 85 Lakhs
    text_1 = "Sale agreement consideration Rs. 85,00,000 for Flat 101."
    _seed_document_and_chunks(sqlite_engine, "doc_a", owner_id, prop_id, "agreement.txt", text_1)

    # Document 2: Builder Invoice asserting 95 Lakhs
    text_2 = "Builder invoice consideration Rs. 95,00,000 for Flat 101."
    _seed_document_and_chunks(sqlite_engine, "doc_b", owner_id, prop_id, "invoice.txt", text_2)

    # Configure extraction service with a custom mock LLM that returns different prices per doc
    class DynamicLLM:
        async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
            if "agreement.txt" in user_prompt:
                return MOCK_VALID_EXTRACTION_JSON  # 85,00,000
            else:
                # 95,00,000
                return MOCK_VALID_EXTRACTION_JSON.replace("8500000", "9500000").replace("85,00,000", "95,00,000")

    extraction_srv.llm_service = DynamicLLM()

    res = client.post(f"/properties/{prop_id}/extract", headers=headers)
    assert res.status_code == 200
    body = res.json()
    data = body["data"]

    # Sale price should be marked conflicting
    sale_price = data["financial"]["sale_price"]
    assert sale_price["verification_status"] == "conflicting"
    assert len(sale_price["alternative_values"]) >= 1

    # Conflict list must contain the contradiction explanation
    assert len(data["conflicts"]) >= 1
    assert any("agreement.txt" in c["description"] and "invoice.txt" in c["description"] for c in data["conflicts"])


def test_cross_user_isolation(client, sqlite_engine):
    token_a = _register(client, "user_a_ext@propertyrag.com")
    token_b = _register(client, "user_b_ext@propertyrag.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates Property
    prop_a = client.post("/properties", headers=headers_a, json={"name": "User A Villa"}).json()
    prop_a_id = prop_a["id"]

    # User B attempts to extract User A's property -> 404
    res_b = client.post(f"/properties/{prop_a_id}/extract", headers=headers_b)
    assert res_b.status_code == 404

    # User B attempts to get User A's extraction -> 404
    get_b = client.get(f"/properties/{prop_a_id}/extraction", headers=headers_b)
    assert get_b.status_code == 404

    # User B attempts to check status -> 404
    status_b = client.get(f"/properties/{prop_a_id}/extraction/status", headers=headers_b)
    assert status_b.status_code == 404


def test_extraction_persistence_and_retrieval(client, sqlite_engine):
    token = _register(client, "persist_user@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Persist Manor"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    _seed_document_and_chunks(
        sqlite_engine, "doc_p1", owner_id, prop_id, "deed.txt", "Title deed for Persist Manor. Price: Rs. 60,00,000."
    )

    # 1. Initial status is not_started
    st_res = client.get(f"/properties/{prop_id}/extraction/status", headers=headers)
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "not_started"

    # 2. Trigger extraction
    ext_res = client.post(f"/properties/{prop_id}/extract", headers=headers)
    assert ext_res.status_code == 200
    assert ext_res.json()["status"] == "completed"

    # 3. Retrieve extraction via GET endpoint
    get_res = client.get(f"/properties/{prop_id}/extraction", headers=headers)
    assert get_res.status_code == 200
    get_body = get_res.json()
    assert get_body["status"] == "completed"
    assert get_body["property_id"] == prop_id
    assert get_body["data"]["identity"]["property_name"]["extracted_value"] == "Emerald Heights"

    # 4. Check status endpoint after extraction
    st_res_after = client.get(f"/properties/{prop_id}/extraction/status", headers=headers)
    assert st_res_after.status_code == 200
    st_data = st_res_after.json()
    assert st_data["status"] == "completed"
    assert st_data["document_count"] == 1
    assert st_data["last_extracted_at"] is not None


def test_re_extraction_after_document_change(client, sqlite_engine):
    token = _register(client, "refresh_user@propertyrag.com")
    headers = {"Authorization": f"Bearer {token}"}

    prop = client.post("/properties", headers=headers, json={"name": "Refresh Residency"}).json()
    prop_id = prop["id"]
    owner_id = prop["owner_id"]

    # Seed 1 document initially
    _seed_document_and_chunks(
        sqlite_engine, "doc_r1", owner_id, prop_id, "initial.txt", "Initial agreement Rs. 40,00,000."
    )

    client.post(f"/properties/{prop_id}/extract", headers=headers)

    # Add a second document to the property
    _seed_document_and_chunks(
        sqlite_engine, "doc_r2", owner_id, prop_id, "addendum.txt", "Addendum agreement Rs. 45,00,000."
    )

    # Status should now report as stale!
    st_res = client.get(f"/properties/{prop_id}/extraction/status", headers=headers)
    assert st_res.status_code == 200
    assert st_res.json()["is_stale"] is True

    # Call refresh endpoint
    refresh_res = client.post(f"/properties/{prop_id}/extraction/refresh", headers=headers)
    assert refresh_res.status_code == 200
    ref_body = refresh_res.json()
    assert ref_body["status"] == "completed"
    assert ref_body["document_count"] == 2
    assert ref_body["is_stale"] is False

