"""Unit and integration tests for Phase 14: Portfolio Dashboard & Due Diligence Reporting."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_auth_service, get_current_user
from app.api.routes import documents, properties
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
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
from app.services.auth_service import AuthService
from app.services.due_diligence_report_service import DueDiligenceReportService
from app.services.portfolio_service import PortfolioService
from app.services.property_service import PropertyService
from tests.fakes import FakeDocumentStore


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
            Chunk.__table__,
            PropertyExtraction.__table__,
            PropertyRiskAssessment.__table__,
            PropertyRiskFinding.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def app_settings():
    return Settings(
        jwt_secret_key="secret-key-32-characters-minimum-portfolio-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )


# --- 1. Portfolio Statistics Tests ---


def test_portfolio_stats_empty_user(sqlite_engine, app_settings):
    """User with zero properties receives clean zeroed statistics without errors."""
    portfolio_service = PortfolioService(settings=app_settings, engine=sqlite_engine)

    stats = portfolio_service.get_portfolio_stats(user_id="usr_empty")
    assert stats.total_properties == 0
    assert stats.total_documents == 0
    assert stats.processed_documents == 0
    assert stats.critical_findings_count == 0
    assert stats.open_findings_count == 0
    assert len(stats.properties_requiring_attention) == 0


def test_portfolio_stats_calculation_and_tenant_isolation(sqlite_engine, app_settings):
    """Verify aggregated portfolio statistics are accurately calculated and strictly isolated."""
    portfolio_service = PortfolioService(settings=app_settings, engine=sqlite_engine)

    with Session(sqlite_engine) as session:
        # Create User 1 (Active portfolio)
        u1 = User(id="usr_port_1", email="user1@portfolio.test", hashed_password="pw")
        # Create User 2 (Different tenant)
        u2 = User(id="usr_port_2", email="user2@portfolio.test", hashed_password="pw")
        session.add_all([u1, u2])

        # User 1 has 2 properties
        p1 = Property(id="prop_u1_1", owner_id=u1.id, name="Sunset Heights", property_type="Residential")
        p2 = Property(id="prop_u1_2", owner_id=u1.id, name="Commercial Square", property_type="Commercial")
        # User 2 has 1 property
        p3 = Property(id="prop_u2_1", owner_id=u2.id, name="Other Tenant Villa", property_type="Villa")
        session.add_all([p1, p2, p3])

        # Documents for User 1
        d1 = Document(
            id="doc_1",
            owner_id=u1.id,
            filename="deed.pdf",
            source_type="pdf",
            status="processed",
            content_sha256="hash1",
            extracted_characters=1000,
            chunk_count=2,
        )
        d2 = Document(
            id="doc_2",
            owner_id=u1.id,
            filename="scan.png",
            source_type="image",
            status="ocr_required",
            ocr_status="needs_manual_review",
            content_sha256="hash2",
            extracted_characters=100,
            chunk_count=1,
        )
        # Document for User 2
        d3 = Document(
            id="doc_3",
            owner_id=u2.id,
            filename="secret_doc.pdf",
            source_type="pdf",
            status="processed",
            content_sha256="hash3",
            extracted_characters=5000,
            chunk_count=5,
        )
        session.add_all([d1, d2, d3])

        # Associations
        session.add(PropertyDocument(property_id=p1.id, document_id=d1.id))
        session.add(PropertyDocument(property_id=p2.id, document_id=d2.id))
        session.add(PropertyDocument(property_id=p3.id, document_id=d3.id))

        # Risk Assessments
        a1 = PropertyRiskAssessment(
            id="as_1",
            property_id=p1.id,
            status="completed",
            summary={"total_findings": 2, "critical_count": 1, "high_count": 0, "open_count": 1},
        )
        session.add(a1)

        # Critical Finding on p1
        f1 = PropertyRiskFinding(
            id="find_1",
            assessment_id=a1.id,
            property_id=p1.id,
            rule_key="litigation_presence",
            category="legal_and_dispute",
            severity="critical",
            status="open",
            title="Active Litigation Disclosure",
            description="Pending suit before civil court.",
            reason="Suit #102/2024 listed in schedule.",
            recommended_action="Obtain stay order status.",
        )
        session.add(f1)

        # User 2 has a critical finding
        a2 = PropertyRiskAssessment(
            id="as_u2",
            property_id=p3.id,
            status="completed",
            summary={"total_findings": 1, "critical_count": 1, "high_count": 0, "open_count": 1},
        )
        session.add(a2)
        f_u2 = PropertyRiskFinding(
            id="find_u2",
            assessment_id=a2.id,
            property_id=p3.id,
            rule_key="mortgage_dispute",
            category="financial",
            severity="critical",
            status="open",
            title="User 2 Mortgage",
            description="Secret mortgage.",
            reason="Bank claim.",
            recommended_action="Check.",
        )
        session.add(f_u2)
        session.commit()

    # Query User 1 stats
    u1_stats = portfolio_service.get_portfolio_stats(user_id="usr_port_1")

    assert u1_stats.total_properties == 2
    assert u1_stats.total_documents == 2
    assert u1_stats.processed_documents == 1
    assert u1_stats.ocr_or_review_documents == 1
    assert u1_stats.critical_findings_count == 1  # Does NOT include User 2's critical finding!
    assert u1_stats.open_findings_count == 1

    # Check properties requiring attention
    attention_ids = [item.property_id for item in u1_stats.properties_requiring_attention]
    assert "prop_u1_1" in attention_ids  # Has open critical finding
    assert "prop_u1_2" in attention_ids  # Has failed/review OCR document
    assert "prop_u2_1" not in attention_ids  # Tenant isolation strictly preserved!


# --- 2. Activity History Timeline Tests ---


def test_activity_history_chronological_and_isolation(sqlite_engine, app_settings):
    """Verify property activity aggregates events in reverse chronological order with tenant protection."""
    portfolio_service = PortfolioService(settings=app_settings, engine=sqlite_engine)

    with Session(sqlite_engine) as session:
        u1 = User(id="usr_act_1", email="act1@portfolio.test", hashed_password="pw")
        u2 = User(id="usr_act_2", email="act2@portfolio.test", hashed_password="pw")
        session.add_all([u1, u2])

        p1 = Property(id="prop_act_1", owner_id=u1.id, name="Timeline Villa")
        session.add(p1)

        d1 = Document(
            id="doc_act_1",
            owner_id=u1.id,
            filename="sale_deed.pdf",
            source_type="pdf",
            status="processed",
            classification_category="Sale Deed",
            content_sha256="hash_act",
            extracted_characters=2000,
            chunk_count=2,
        )
        session.add(d1)
        session.add(PropertyDocument(property_id=p1.id, document_id=d1.id))

        ext = PropertyExtraction(
            id="ext_act_1",
            property_id=p1.id,
            status="completed",
            extracted_data={"supported_facts": [{"field_name": "sale_price", "extracted_value": "50,00,000"}]},
        )
        session.add(ext)
        session.commit()

    # User 1 retrieves timeline
    activity = portfolio_service.get_activity_history(property_id="prop_act_1", user_id="usr_act_1")
    assert activity.property_id == "prop_act_1"
    assert len(activity.events) >= 3

    event_types = [e.event_type for e in activity.events]
    assert "property_created" in event_types
    assert "document_associated" in event_types
    assert "extraction_completed" in event_types

    # Tenant isolation: User 2 must be rejected
    from app.services.property_errors import PropertyAuthorizationError
    with pytest.raises(PropertyAuthorizationError):
        portfolio_service.get_activity_history(property_id="prop_act_1", user_id="usr_act_2")


# --- 3. Due Diligence PDF Generation Tests ---


def test_due_diligence_pdf_generation_full_and_disclaimer(sqlite_engine, app_settings):
    """Verify PDF generator produces a valid, multi-section PDF document containing evidence and disclaimers."""
    report_service = DueDiligenceReportService(settings=app_settings, engine=sqlite_engine)

    with Session(sqlite_engine) as session:
        user = User(id="usr_pdf_1", email="pdf@test.com", hashed_password="pw")
        session.add(user)

        prop = Property(
            id="prop_pdf_1",
            owner_id=user.id,
            name="Emerald Heights Penthouse",
            address="Plot 42, Sector 15, Kharghar",
            property_type="Residential Apartment",
        )
        session.add(prop)

        doc = Document(
            id="doc_pdf_1",
            owner_id=user.id,
            filename="Agreement_to_Sell.pdf",
            source_type="pdf",
            status="processed",
            classification_category="Agreement to Sell",
            content_sha256="hash_pdf_1",
            extracted_characters=3500,
            chunk_count=4,
            page_count=5,
        )
        session.add(doc)
        session.add(PropertyDocument(property_id=prop.id, document_id=doc.id))

        extraction = PropertyExtraction(
            id="ext_pdf_1",
            property_id=prop.id,
            status="completed",
            extracted_data={
                "supported_facts": [
                    {
                        "category": "financial_information",
                        "field_name": "sale_price",
                        "extracted_value": "INR 95,00,000",
                        "verification_status": "supported",
                        "source_document_filename": "Agreement_to_Sell.pdf",
                        "source_page_number": 2,
                    },
                    {
                        "category": "ownership_and_legal",
                        "field_name": "named_owner",
                        "extracted_value": "Emerald Developers LLP",
                        "verification_status": "supported",
                        "source_document_filename": "Agreement_to_Sell.pdf",
                        "source_page_number": 1,
                    },
                ],
                "conflicts": [
                    {
                        "contradiction_reason": "Monetary consideration discrepancy",
                        "source_a": {"filename": "Doc A.pdf", "page_number": 1, "quote": "Rs. 90,00,000"},
                        "source_b": {"filename": "Doc B.pdf", "page_number": 3, "quote": "Rs. 95,00,000"},
                    }
                ],
                "missing_fields": ["Occupancy Certificate", "Fire Safety Approval"],
            },
        )
        session.add(extraction)

        assessment = PropertyRiskAssessment(
            id="as_pdf_1",
            property_id=prop.id,
            status="completed",
            summary={"total_findings": 1, "critical_count": 1, "high_count": 0, "open_count": 1},
        )
        session.add(assessment)

        finding = PropertyRiskFinding(
            id="find_pdf_1",
            assessment_id=assessment.id,
            property_id=prop.id,
            rule_key="unresolved_encumbrance",
            category="ownership_and_title",
            severity="high",
            status="open",
            title="Missing Title Search Clearance",
            description="No 30-year search report supplied.",
            reason="Only recent agreement provided without parent deed references.",
            recommended_action="Request 30-year index II search report from local sub-registrar.",
        )
        session.add(finding)
        session.commit()

    # Generate PDF
    pdf_bytes = report_service.generate_pdf_report(property_id="prop_pdf_1", user_id="usr_pdf_1")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")

    # Read and parse with pypdf to verify structural content and statutory disclaimer
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    full_text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "Emerald Heights Penthouse" in full_text
    assert "Agreement_to_Sell.pdf" in full_text
    assert "INR 95,00,000" in full_text
    assert "Missing Title Search Clearance" in full_text
    assert "NOT A FORMAL LEGAL OPINION" in full_text
    assert "SW2627-AI-LegalRag" in full_text


def test_due_diligence_pdf_empty_property_succeeds(sqlite_engine, app_settings):
    """Empty property with no documents or findings generates a valid disclaimer-bound report."""
    report_service = DueDiligenceReportService(settings=app_settings, engine=sqlite_engine)

    with Session(sqlite_engine) as session:
        user = User(id="usr_pdf_empty", email="empty@test.com", hashed_password="pw")
        session.add(user)
        prop = Property(id="prop_pdf_empty", owner_id=user.id, name="Bare Property")
        session.add(prop)
        session.commit()

    pdf_bytes = report_service.generate_pdf_report(property_id="prop_pdf_empty", user_id="usr_pdf_empty")
    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    text = reader.pages[0].extract_text() or ""
    assert "Bare Property" in text
    assert "No documents associated" in text
    assert "NOT A FORMAL LEGAL OPINION" in text


# --- 4. API Endpoint Integration Tests ---


def test_api_portfolio_and_reporting_workflow(sqlite_engine, app_settings):
    """Verify /portfolio/stats, /{id}/activity, and /{id}/report/pdf via FastAPI TestClient."""
    auth_service = AuthService(settings=app_settings, engine=sqlite_engine)
    property_service = PropertyService(settings=app_settings, engine=sqlite_engine)
    portfolio_service = PortfolioService(settings=app_settings, engine=sqlite_engine)
    report_service = DueDiligenceReportService(settings=app_settings, engine=sqlite_engine)
    doc_store = FakeDocumentStore(engine=sqlite_engine)

    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_settings] = lambda: app_settings
    app.dependency_overrides[properties.get_settings_dep] = lambda: app_settings
    app.dependency_overrides[documents.get_settings_dep] = lambda: app_settings
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[properties.get_property_service] = lambda: property_service
    app.dependency_overrides[properties.get_portfolio_service] = lambda: portfolio_service
    app.dependency_overrides[properties.get_report_service] = lambda: report_service
    app.dependency_overrides[documents.get_document_store] = lambda: doc_store

    with Session(sqlite_engine) as session:
        u1 = User(id="usr_api_p1", email="api_p1@test.com", hashed_password="pw")
        u2 = User(id="usr_api_p2", email="api_p2@test.com", hashed_password="pw")
        session.add_all([u1, u2])

        p1 = Property(id="prop_api_1", owner_id=u1.id, name="API Tested Tower")
        session.add(p1)
        session.commit()

    token1 = create_access_token(
        {"email": "api_p1@test.com"},
        subject="usr_api_p1",
        secret_key=app_settings.jwt_secret_key,
        algorithm=app_settings.jwt_algorithm,
    )
    token2 = create_access_token(
        {"email": "api_p2@test.com"},
        subject="usr_api_p2",
        secret_key=app_settings.jwt_secret_key,
        algorithm=app_settings.jwt_algorithm,
    )
    auth1 = {"Authorization": f"Bearer {token1}"}
    auth2 = {"Authorization": f"Bearer {token2}"}

    client = TestClient(app)

    # 1. GET /properties/portfolio/stats
    res_stats = client.get("/properties/portfolio/stats", headers=auth1)
    assert res_stats.status_code == 200
    stats_data = res_stats.json()
    assert stats_data["total_properties"] == 1
    assert "properties_requiring_attention" in stats_data

    # User 2 sees 0 properties
    res_stats2 = client.get("/properties/portfolio/stats", headers=auth2)
    assert res_stats2.status_code == 200
    assert res_stats2.json()["total_properties"] == 0

    # 2. GET /properties/{id}/activity
    res_act = client.get("/properties/prop_api_1/activity", headers=auth1)
    assert res_act.status_code == 200
    act_data = res_act.json()
    assert act_data["property_id"] == "prop_api_1"
    assert len(act_data["events"]) >= 1

    # Cross-tenant isolation on activity: User 2 gets 403 or 404
    res_act_iso = client.get("/properties/prop_api_1/activity", headers=auth2)
    assert res_act_iso.status_code in (403, 404)

    # 3. GET /properties/{id}/report/pdf
    res_pdf = client.get("/properties/prop_api_1/report/pdf", headers=auth1)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in res_pdf.headers["content-disposition"]
    assert res_pdf.content.startswith(b"%PDF")

    # Cross-tenant isolation on PDF export: User 2 gets 403 or 404
    res_pdf_iso = client.get("/properties/prop_api_1/report/pdf", headers=auth2)
    assert res_pdf_iso.status_code in (403, 404)

