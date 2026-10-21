"""Phase 2 document ingestion tests: validation, extraction, API, cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents
from app.core.config import Settings
from app.main import create_app
from app.services.document_validation import sanitize_filename
from app.services.embedding_service import EmbeddingService
from app.services.text_cleaning import clean_text
from tests.fakes import FakeDocumentStore, FakeEmbeddingProvider
from tests.pdf_factory import make_pdf

RESPONSE_KEYS = {
    "document_id",
    "filename",
    "status",
    "extracted_characters",
    "chunk_count",
    "chunks",
    "page_count",
    "warnings",
    "detail",
}
CHUNK_KEYS = {
    "chunk_id",
    "document_id",
    "chunk_index",
    "text",
    "source_filename",
    "source_type",
    "page_number",
    "start_offset",
    "end_offset",
    "metadata",
}

SAMPLE_TEXT = (
    "SALE DEED\n\n"
    "Clause 1. The seller agrees to sell the property described in Schedule A.\n\n"
    "Clause 2. Consideration is Rs. 50,00,000 payable on 2026-12-01 at Bengaluru."
)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "groq_api_key": None,
        "document_temp_dir": str(tmp_path / "ingest_temp"),
        "embedding_dimensions": 8,
    }
    values.update(overrides)
    return Settings(**values)


def _client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[documents.get_settings_dep] = lambda: settings
    embedding_service = EmbeddingService(
        settings,
        provider=FakeEmbeddingProvider(dimensions=settings.embedding_dimensions),
    )
    store = FakeDocumentStore()
    app.dependency_overrides[documents.get_embedding_service] = (
        lambda: embedding_service
    )
    app.dependency_overrides[documents.get_document_store] = lambda: store
    return TestClient(app)


def _ingest(
    client: TestClient,
    settings: Settings,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
):
    return client.post(
        f"{settings.api_prefix}/documents/ingest",
        files={"file": (filename, data, content_type)},
    )


# --- Successful ingestion ----------------------------------------------------


def test_valid_txt_ingestion_returns_traceable_chunks(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    response = _ingest(client, settings, "property_notes.txt", SAMPLE_TEXT.encode())

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["status"] == "processed"
    assert body["filename"] == "property_notes.txt"
    assert body["document_id"].startswith("doc_")
    assert body["page_count"] is None
    assert body["chunk_count"] == len(body["chunks"]) >= 1
    assert body["extracted_characters"] == len(clean_text(SAMPLE_TEXT))

    cleaned = clean_text(SAMPLE_TEXT)
    chunk_ids = set()
    for index, chunk in enumerate(body["chunks"]):
        assert set(chunk) == CHUNK_KEYS
        assert chunk["chunk_id"].startswith("chk_")
        assert chunk["chunk_id"] not in chunk_ids
        chunk_ids.add(chunk["chunk_id"])
        assert chunk["document_id"] == body["document_id"]
        assert chunk["chunk_index"] == index
        assert chunk["source_filename"] == "property_notes.txt"
        assert chunk["source_type"] == "txt"
        assert chunk["page_number"] is None
        assert cleaned[chunk["start_offset"] : chunk["end_offset"]] == chunk["text"]
        assert "Rs. 50,00,000" in chunk["text"]
        assert chunk["metadata"]["character_count"] == len(chunk["text"])


def test_valid_markdown_ingestion_preserves_headings_and_paragraphs(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    markdown = (
        "# Property Report\n\n"
        "## Locality\n\n"
        "The metro station is 2 km away.\n\n"
        "## Legal\n\n"
        "The title is subject to verification."
    )
    response = _ingest(
        client, settings, "report.md", markdown.encode("utf-8"), "text/markdown"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["chunks"][0]["source_type"] == "markdown"
    chunk_text = "\n".join(chunk["text"] for chunk in body["chunks"])
    assert "# Property Report" in chunk_text
    assert "## Locality" in chunk_text
    assert "## Legal" in chunk_text


def test_text_based_pdf_preserves_page_numbers(tmp_path):
    settings = _settings(
        tmp_path,
        document_chunk_size_chars=40,
        document_chunk_overlap_chars=0,
    )
    client = _client(settings)
    pdf = make_pdf(
        [
            "Page one sale deed clause.",
            "Page two encumbrance certificate.",
        ]
    )
    response = _ingest(client, settings, "deed.pdf", pdf, "application/pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["page_count"] == 2
    assert body["chunk_count"] == 2
    assert [chunk["page_number"] for chunk in body["chunks"]] == [1, 2]
    assert body["chunks"][0]["metadata"]["page_numbers"] == [1]
    assert body["chunks"][1]["metadata"]["page_numbers"] == [2]
    assert body["chunks"][0]["source_type"] == "pdf"


def test_multi_page_pdf_chunk_preserves_all_page_references(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    pdf = make_pdf(["Page one short clause.", "Page two short clause."])
    response = _ingest(client, settings, "combined.pdf", pdf, "application/pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] == 1
    chunk = body["chunks"][0]
    assert chunk["page_number"] is None
    assert chunk["metadata"]["page_numbers"] == [1, 2]
    assert chunk["metadata"]["total_pages"] == 2


def test_chunk_identifiers_are_unique_and_document_identifiers_match(tmp_path):
    settings = _settings(
        tmp_path,
        document_chunk_size_chars=60,
        document_chunk_overlap_chars=10,
    )
    client = _client(settings)
    response = _ingest(client, settings, "long.txt", ("Legal clause. " * 100).encode())

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] > 2
    chunk_ids = [chunk["chunk_id"] for chunk in body["chunks"]]
    assert len(set(chunk_ids)) == len(chunk_ids)
    assert all(chunk["document_id"] == body["document_id"] for chunk in body["chunks"])
    assert [chunk["chunk_index"] for chunk in body["chunks"]] == list(
        range(body["chunk_count"])
    )


# --- Validation failures -----------------------------------------------------


def test_empty_upload_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(_client(settings), settings, "empty.txt", b"", "text/plain")
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_whitespace_only_text_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings), settings, "blank.txt", b"  \n\t\r\n ", "text/plain"
    )
    assert response.status_code == 400
    assert "no readable text" in response.json()["detail"].lower()


def test_unsupported_extension_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings), settings, "notes.docx", b"not a docx", "application/msword"
    )
    assert response.status_code == 415
    assert ".docx" in response.json()["detail"]


def test_invalid_mime_type_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    pdf = make_pdf(["A valid pdf page."])
    response = _ingest(_client(settings), settings, "deed.pdf", pdf, "image/png")
    assert response.status_code == 415


def test_malformed_pdf_signature_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings),
        settings,
        "fake.pdf",
        b"this is not a pdf",
        "application/pdf",
    )
    assert response.status_code == 400
    assert "pdf signature" in response.json()["detail"].lower()


def test_binary_content_with_text_extension_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings),
        settings,
        "binary.txt",
        b"\x00\x01\x02\x03binary",
        "text/plain",
    )
    assert response.status_code == 400


def test_invalid_text_encoding_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings),
        settings,
        "latin1.txt",
        b"Valid prefix \xff\xfe invalid utf-8",
        "text/plain",
    )
    assert response.status_code == 400
    assert "encoding" in response.json()["detail"].lower()


def test_upload_size_limit_is_enforced(tmp_path):
    settings = _settings(tmp_path, document_max_upload_bytes=50)
    response = _ingest(
        _client(settings), settings, "large.txt", b"a" * 51, "text/plain"
    )
    assert response.status_code == 413
    assert "limit" in response.json()["detail"].lower()


# --- Extraction failures and OCR --------------------------------------------


def test_encrypted_pdf_returns_failed_status_without_internals(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    pdf = make_pdf(["Protected sale deed."], password="secret-password")
    response = _ingest(client, settings, "protected.pdf", pdf, "application/pdf")

    assert response.status_code == 422
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["status"] == "failed"
    assert "password" in body["detail"].lower()
    assert "traceback" not in response.text.lower()
    assert "secret-password" not in response.text
    assert list((tmp_path / "ingest_temp").iterdir()) == []


def test_malformed_pdf_returns_failed_status(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    response = _ingest(
        client,
        settings,
        "broken.pdf",
        b"%PDF-1.4\nthis is not a structurally valid pdf\n",
        "application/pdf",
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "failed"
    assert body["chunk_count"] == 0
    assert "traceback" not in response.text.lower()
    assert list((tmp_path / "ingest_temp").iterdir()) == []


def test_scanned_or_text_empty_pdf_is_marked_ocr_required(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    response = _ingest(
        client, settings, "scan.pdf", make_pdf(["", ""]), "application/pdf"
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["status"] == "ocr_required"
    assert body["chunk_count"] == 0
    assert body["chunks"] == []
    assert body["page_count"] == 2
    assert "OCR" in body["detail"]
    assert any("OCR" in warning for warning in body["warnings"])


# --- Filenames and temporary files -----------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.txt", "passwd.txt"),
        ("..\\..\\windows\\evil.md", "evil.md"),
        ("  report.pdf  ", "report.pdf"),
        ("..", "upload"),
        ("", "upload"),
    ],
)
def test_sanitize_filename_removes_paths_and_controls(raw, expected):
    assert sanitize_filename(raw) == expected


def test_path_traversal_filename_is_sanitized_in_response(tmp_path):
    settings = _settings(tmp_path)
    response = _ingest(
        _client(settings),
        settings,
        "../../../etc/passwd.txt",
        SAMPLE_TEXT.encode(),
        "text/plain",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "passwd.txt"
    assert all(chunk["source_filename"] == "passwd.txt" for chunk in body["chunks"])
    assert ".." not in body["filename"]
    assert list((tmp_path / "ingest_temp").iterdir()) == []


def test_temporary_files_are_removed_after_success(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    assert _ingest(client, settings, "notes.txt", SAMPLE_TEXT.encode()).status_code == 200
    assert list((tmp_path / "ingest_temp").iterdir()) == []


def test_temporary_files_are_removed_after_validation_failure(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    response = _ingest(client, settings, "bad.pdf", b"not-a-pdf", "application/pdf")
    assert response.status_code == 400
    temp_dir = tmp_path / "ingest_temp"
    assert not temp_dir.exists() or list(temp_dir.iterdir()) == []


# --- Response contract ------------------------------------------------------


def test_failed_response_has_stable_schema_and_safe_detail(tmp_path):
    settings = _settings(tmp_path)
    client = _client(settings)
    pdf = make_pdf(["Encrypted."], password="pw")
    response = _ingest(client, settings, "enc.pdf", pdf, "application/pdf")
    assert set(response.json()) == RESPONSE_KEYS
    assert response.json()["status"] == "failed"
    assert response.headers["content-type"].startswith("application/json")
