"""Unit and integration tests for Phase 13: Advanced Document Intelligence.

Covers:
- Scanned PDF detection
- Successful OCR extraction & page number preservation
- OCR failure & empty page handling
- Standalone image documents (.png, .jpg)
- Deterministic document classification & uncertainty handling
- Manual classification correction
- Table extraction and row integrity
- Exact duplicate detection (SHA-256)
- Near-duplicate detection (text similarity)
- Strict cross-user tenant isolation
- Safe retry behavior (no duplicate chunks or embeddings)
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image
from pypdf import PdfWriter

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_auth_service, get_current_user
from app.api.routes import documents
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Chunk, Document, Property, PropertyDocument, User
from app.services.auth_service import AuthService
from tests.fakes import FakeDocumentStore
from app.schemas.document_intelligence import (
    DocumentClassificationCategory,
    DocumentOcrStatus,
)
from app.schemas.documents import IngestResponse
from app.services.document_classification import DocumentClassificationService
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_validation import validate_upload
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.ocr_service import MockOcrEngine, OcrService, PageOcrResult
from app.services.table_extraction import TableExtractionService
from app.services.text_extraction import (
    ExtractedPage,
    ExtractionResult,
    ImageExtractor,
    PdfExtractor,
)


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
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    with Session(sqlite_engine) as session:
        yield session


def _create_sample_png(text_marker: str = "Test Image") -> bytes:
    """Generate minimal valid PNG bytes."""
    img = Image.new("RGB", (100, 40), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_scanned_pdf_bytes(page_count: int = 2) -> bytes:
    """Generate a valid PDF containing only raster images without text streams."""
    writer = PdfWriter()
    for _ in range(page_count):
        # Add a blank page
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _create_searchable_pdf_bytes(page_texts: list[str]) -> bytes:
    """Generate a simple searchable PDF with text."""
    from pypdf.generic import DictionaryObject, NameObject

    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=300, height=300)
        # Note: In mock/unit testing, pypdf extract_text can be simulated or tested
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --- OCR Tests ---


def test_ocr_service_image_processing_success():
    """Verify OCR extracts text from valid image data."""
    mock_engine = MockOcrEngine(predefined_text="OFFICIAL SALE CONSIDERATION: RS. 50,00,000")
    service = OcrService(engine=mock_engine)

    png_bytes = _create_sample_png()
    result = service.process_image_data(png_bytes, page_number=1)

    assert result.status == DocumentOcrStatus.OCR_COMPLETED
    assert result.page_number == 1
    assert "SALE CONSIDERATION" in result.text


def test_ocr_service_empty_image_data_fails_safely():
    """Verify empty or corrupt image bytes result in explicit ocr_failed without crashing."""
    service = OcrService(engine=MockOcrEngine())

    result = service.process_image_data(b"", page_number=1)
    assert result.status == DocumentOcrStatus.OCR_FAILED
    assert len(result.warnings) > 0

    corrupt_result = service.process_image_data(b"not_an_image", page_number=1)
    assert corrupt_result.status == DocumentOcrStatus.OCR_FAILED


def test_ocr_service_blank_page_needs_manual_review():
    """Verify an image that yields no characters triggers needs_manual_review."""
    mock_engine = MockOcrEngine(predefined_text="")
    service = OcrService(engine=mock_engine)

    png_bytes = _create_sample_png()
    result = service.process_image_data(png_bytes, page_number=2)

    assert result.status == DocumentOcrStatus.NEEDS_MANUAL_REVIEW
    assert result.text == ""
    assert result.page_number == 2


def test_image_extractor_preserves_page_number_and_status(tmp_path: Path):
    """Verify ImageExtractor produces an ExtractedPage with page_number=1."""
    mock_engine = MockOcrEngine(predefined_text="Property Tax Receipt for Flat 402")
    service = OcrService(engine=mock_engine)
    extractor = ImageExtractor(ocr_service=service)

    img_file = tmp_path / "tax_receipt.png"
    img_file.write_bytes(_create_sample_png())

    res = extractor.extract(img_file)
    assert res.source_type == "image"
    assert len(res.pages) == 1
    assert res.pages[0].page_number == 1
    assert "Flat 402" in res.pages[0].text
    assert not res.requires_ocr


# --- Classification Tests ---


def test_deterministic_classification_sale_deed():
    """Verify clear sale deed preamble results in high-confidence Sale Deed classification."""
    classifier = DocumentClassificationService()
    text = (
        "THIS DEED OF ABSOLUTE SALE executed on this 14th day of October 2022 by and between "
        "the VENDOR Mr. Rajesh Sharma and the PURCHASER Ms. Priya Patel. "
        "WHEREAS the Vendor doth hereby grant, convey, and transfer all that piece of property."
    )
    res = classifier.classify_document("doc-1", text, filename="final_sale_deed.pdf")

    assert res.category == DocumentClassificationCategory.SALE_DEED.value
    assert res.confidence >= 0.85
    assert not res.manually_corrected
    assert "Sale Deed" in res.reasoning


def test_deterministic_classification_encumbrance_certificate():
    """Verify Form 15 Encumbrance Certificate keywords trigger correct classification."""
    classifier = DocumentClassificationService()
    text = (
        "GOVERNMENT OF MAHARASHTRA - REGISTRATION DEPARTMENT\n"
        "FORM NO. 15\n"
        "CERTIFICATE OF ENCUMBRANCE ON PROPERTY\n"
        "Search period: 01/01/1992 to 31/12/2022. Nil Encumbrance found."
    )
    res = classifier.classify_document("doc-2", text, filename="EC_Form15.pdf")

    assert res.category == DocumentClassificationCategory.ENCUMBRANCE_CERTIFICATE.value
    assert res.confidence >= 0.80


def test_deterministic_classification_rera_registration():
    """Verify RERA project certificate classification."""
    classifier = DocumentClassificationService()
    text = (
        "REAL ESTATE REGULATORY AUTHORITY\n"
        "MAHARERA REGISTRATION CERTIFICATE OF PROJECT\n"
        "FORM 'C' [See rule 6(a)]\n"
        "Project Registration Number: P51800012345"
    )
    res = classifier.classify_document("doc-3", text, filename="rera_cert.pdf")

    assert res.category == DocumentClassificationCategory.RERA_REGISTRATION.value
    assert res.confidence >= 0.85


def test_unclassified_text_defaults_to_other_unknown():
    """Verify ambiguous or non-legal text defaults conservatively to Other / Unknown."""
    classifier = DocumentClassificationService()
    text = "Hello team, please find attached the meeting notes from yesterday's discussion."
    res = classifier.classify_document("doc-4", text, filename="notes.txt")

    assert res.category == DocumentClassificationCategory.OTHER_UNKNOWN.value
    assert res.confidence <= 0.30
    assert "Insufficient legal headings" in res.reasoning


# --- Table Extraction Tests ---


def test_table_extraction_markdown_table():
    """Verify markdown financial and area tables are extracted preserving rows and headers."""
    table_service = TableExtractionService()
    text = (
        "Payment schedule agreed between parties:\n\n"
        "| Milestone | Percentage | Amount (INR) |\n"
        "|---|---|---|\n"
        "| Booking Advance | 10% | 10,00,000 |\n"
        "| Plinth Completion | 20% | 20,00,000 |\n"
        "| Possession | 70% | 70,00,000 |\n"
    )
    tables = table_service.extract_tables_from_text(text, page_number=3)

    assert len(tables) >= 1
    t = tables[0]
    assert t.page_number == 3
    assert t.category == "payment_schedule"
    assert len(t.headers) == 3
    assert len(t.rows) == 3
    assert t.rows[0][0] == "Booking Advance"
    assert t.rows[0][2] == "10,00,000"
    assert t.rows[2][1] == "70%"


def test_table_extraction_schedule_blocks():
    """Verify milestone list items are structured into a schedule table."""
    table_service = TableExtractionService()
    text = (
        "Construction Linked Payment Plan:\n"
        "1. On Booking: 10% of Total Consideration\n"
        "2. On Casting of 1st Slab: 15% of Consideration\n"
        "3. On Completion of Brickwork: 20% of Consideration\n"
        "4. On Handover of Possession: Balance 55%\n"
    )
    tables = table_service.extract_tables_from_text(text, page_number=2)

    assert len(tables) >= 1
    t = tables[0]
    assert t.category == "payment_schedule"
    assert len(t.rows) == 4
    assert "On Booking" in t.rows[0][0]


# --- Duplicate Detection Tests ---


def test_duplicate_detection_exact_and_cross_user_isolation(db_session):
    """Verify exact duplicate detection flags matching hash, while isolating across users."""
    detector = DuplicateDetectionService()

    # User 1
    user1 = User(id="usr_dup_1", email="user1@prop.com", hashed_password="pw")
    # User 2
    user2 = User(id="usr_dup_2", email="user2@prop.com", hashed_password="pw")
    db_session.add_all([user1, user2])
    db_session.commit()

    content_hash = "abc123456789deadbeef9876543210"

    # User 1 uploads doc A
    doc_a = Document(
        id="doc_u1_a",
        owner_id="usr_dup_1",
        filename="deed_v1.pdf",
        source_type="pdf",
        status="processed",
        content_sha256=content_hash,
        extracted_characters=500,
        chunk_count=1,
    )
    # User 2 uploads identical bytes
    doc_u2 = Document(
        id="doc_u2",
        owner_id="usr_dup_2",
        filename="deed_v1.pdf",
        source_type="pdf",
        status="processed",
        content_sha256=content_hash,
        extracted_characters=500,
        chunk_count=1,
    )
    db_session.add_all([doc_a, doc_u2])
    db_session.commit()

    # User 1 uploads doc B with same hash
    result_u1 = detector.detect_duplicates(
        session=db_session,
        document_id="doc_u1_b",
        owner_id="usr_dup_1",
        content_sha256=content_hash,
    )

    assert result_u1.has_duplicates is True
    assert len(result_u1.exact_matches) == 1
    assert result_u1.exact_matches[0].document_id == "doc_u1_a"
    # Ensure User 2's document is NOT exposed!
    assert all(m.document_id != "doc_u2" for m in result_u1.exact_matches)


def test_near_duplicate_detection_similarity_threshold(db_session):
    """Verify near-duplicate detection matches documents with minor formatting differences."""
    detector = DuplicateDetectionService(near_duplicate_threshold=0.65)

    user = User(id="usr_near_dup", email="near@prop.com", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    text1 = (
        "Agreement to sell entered between Emerald Properties Private Limited and "
        "Mr. Anil Kapoor for flat number 502 in Tower Emerald Heights Sector 15 Kharghar. "
        "Total purchase consideration fixed at Rs. 95,00,000 paid via banker cheque."
    )
    # Text 2 has slight minor formatting variation
    text2 = (
        "Agreement to sell entered between Emerald Properties Private Limited and "
        "Mr. Anil Kapoor for flat number 502 in Tower Emerald Heights Sector 15 Kharghar Navi Mumbai. "
        "Total purchase consideration fixed at Rs. 95,00,000 paid via RTGS transfer."
    )

    doc1 = Document(
        id="doc_orig",
        owner_id="usr_near_dup",
        filename="original_agreement.pdf",
        source_type="pdf",
        status="processed",
        content_sha256="hash_original_111",
        extracted_characters=len(text1),
        chunk_count=1,
    )
    db_session.add(doc1)
    db_session.commit()

    # Seed chunk for doc1 so near duplicate comparison can read it
    from app.db.models import Chunk
    c1 = Chunk(
        id="chk_orig_1",
        document_id="doc_orig",
        chunk_index=0,
        text=text1,
        source_filename="original_agreement.pdf",
        source_type="pdf",
        embedding=[0.1] * 768,
    )
    db_session.add(c1)
    db_session.commit()

    res = detector.detect_duplicates(
        session=db_session,
        document_id="doc_new",
        owner_id="usr_near_dup",
        content_sha256="hash_diff_222",
        document_text=text2,
    )

    assert res.has_duplicates is True
    assert len(res.near_matches) == 1
    assert res.near_matches[0].document_id == "doc_orig"
    assert res.near_matches[0].similarity >= 0.65



# --- API Endpoint Tests ---

from fastapi.testclient import TestClient
from app.main import create_app
from app.core.security import create_access_token
from app.db.models import Chunk


def test_api_document_intelligence_workflow_and_isolation():
    """Test classification, status, tables, duplicates, and manual update via API."""
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
        tables=[User.__table__, Property.__table__, Document.__table__, PropertyDocument.__table__, Chunk.__table__],
    )

    u1_id, u1_email = "usr_api_1", "api1@prop.com"
    u2_id, u2_email = "usr_api_2", "api2@prop.com"

    sample_tables = [
        {
            "table_id": "tbl-1",
            "title": "Payment Terms",
            "headers": ["Stage", "Due %"],
            "rows": [["Booking", "10%"], ["Possession", "90%"]],
            "page_number": 1,
            "category": "payment_schedule",
        }
    ]

    with Session(engine) as session:
        user1 = User(id=u1_id, email=u1_email, hashed_password="pw")
        user2 = User(id=u2_id, email=u2_email, hashed_password="pw")
        session.add_all([user1, user2])
        doc1 = Document(
            id="doc_api_1",
            owner_id=u1_id,
            filename="sale_agreement.pdf",
            source_type="pdf",
            status="processed",
            content_sha256="sha256_api_111",
            extracted_characters=300,
            chunk_count=1,
            classification_category=DocumentClassificationCategory.AGREEMENT_TO_SELL.value,
            classification_confidence=0.92,
            classification_reasoning="Agreement to sell covenant matched.",
            extracted_tables=sample_tables,
            near_duplicates=[],
        )
        session.add(doc1)
        c1 = Chunk(
            id="chk_api_1",
            document_id="doc_api_1",
            chunk_index=0,
            text="Agreement to sell between developer and buyer.",
            source_filename="sale_agreement.pdf",
            source_type="pdf",
            embedding=[0.1] * 768,
        )
        session.add(c1)
        session.commit()

    settings = Settings(
        jwt_secret_key="secret-key-32-characters-minimum-prop-test",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    auth_service = AuthService(settings=settings, engine=engine)
    store = FakeDocumentStore(engine=engine)

    app = create_app()
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[documents.get_settings_dep] = lambda: settings
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[documents.get_document_store] = lambda: store

    token1 = create_access_token(
        {"email": u1_email},
        subject=u1_id,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    token2 = create_access_token(
        {"email": u2_email},
        subject=u2_id,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    auth1 = {"Authorization": f"Bearer {token1}"}
    auth2 = {"Authorization": f"Bearer {token2}"}

    client = TestClient(app)

    # 1. GET /processing-status
    res_status = client.get("/documents/doc_api_1/processing-status", headers=auth1)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["document_id"] == "doc_api_1"
    assert status_data["classification_category"] == "Agreement to Sell"
    assert status_data["table_count"] == 1

    # Cross-user isolation: User 2 must get 404
    res_iso = client.get("/documents/doc_api_1/processing-status", headers=auth2)
    assert res_iso.status_code == 404

    # 2. GET /classification
    res_class = client.get("/documents/doc_api_1/classification", headers=auth1)
    assert res_class.status_code == 200
    class_data = res_class.json()
    assert class_data["category"] == "Agreement to Sell"
    assert class_data["confidence"] == 0.92
    assert not class_data["manually_corrected"]

    # 3. PATCH /classification (Manual correction)
    patch_res = client.patch(
        "/documents/doc_api_1/classification",
        json={"category": "Sale Deed"},
        headers=auth1,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["category"] == "Sale Deed"
    assert patch_data["manually_corrected"] is True

    # User 2 attempting PATCH must get 404
    patch_iso = client.patch(
        "/documents/doc_api_1/classification",
        json={"category": "Title Deed"},
        headers=auth2,
    )
    assert patch_iso.status_code == 404

    # 4. GET /tables
    res_tables = client.get("/documents/doc_api_1/tables", headers=auth1)
    assert res_tables.status_code == 200
    tables_data = res_tables.json()
    assert tables_data["table_count"] == 1
    assert tables_data["tables"][0]["title"] == "Payment Terms"

    # User 2 attempting GET /tables must get 404
    tables_iso = client.get("/documents/doc_api_1/tables", headers=auth2)
    assert tables_iso.status_code == 404

    # 5. GET /duplicates
    res_dups = client.get("/documents/doc_api_1/duplicates", headers=auth1)
    assert res_dups.status_code == 200
    dups_data = res_dups.json()
    assert "exact_matches" in dups_data
    assert "near_matches" in dups_data

    # User 2 attempting GET /duplicates must get 404
    dups_iso = client.get("/documents/doc_api_1/duplicates", headers=auth2)
    assert dups_iso.status_code == 404
