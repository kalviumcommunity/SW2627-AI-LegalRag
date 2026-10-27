"""Unit and API tests for Phase 6 document management endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents
from app.core.config import Settings
from app.main import create_app
from app.schemas.documents import IngestResponse
from app.services.embedding_service import EmbeddingService
from app.services.storage_errors import DatabaseUnavailableError
from tests.fakes import FakeDocumentStore, FakeEmbeddingProvider
from tests.pdf_factory import make_pdf

SAMPLE_TEXT = (
    "PROPERTY SALE AGREEMENT\n\n"
    "Clause 1. Description of Property: Survey No. 42, Whitefield, Bengaluru.\n\n"
    "Clause 2. Total Consideration: INR 1,25,00,000 paid via RTGS.\n\n"
    "Clause 3. Possession date is 2026-12-31 with clear marketable title."
)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "groq_api_key": None,
        "document_temp_dir": str(tmp_path / "mgmt_temp"),
        "embedding_dimensions": 8,
    }
    values.update(overrides)
    return Settings(**values)


def _client_with_store(settings: Settings, store: FakeDocumentStore) -> TestClient:
    app = create_app()
    app.dependency_overrides[documents.get_settings_dep] = lambda: settings
    embedding_service = EmbeddingService(
        settings,
        provider=FakeEmbeddingProvider(dimensions=settings.embedding_dimensions),
    )
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


# --- Document Listing & Pagination --------------------------------------------


def test_list_documents_empty(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    response = client.get(f"{settings.api_prefix}/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 0


def test_list_documents_pagination(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    # Ingest 3 documents
    for i in range(3):
        res = _ingest(
            client,
            settings,
            f"doc_{i}.txt",
            f"Agreement text for document number {i}".encode(),
        )
        assert res.status_code == 200

    # Page 1 with page_size=2
    res_p1 = client.get(f"{settings.api_prefix}/documents?page=1&page_size=2")
    assert res_p1.status_code == 200
    p1_body = res_p1.json()
    assert len(p1_body["items"]) == 2
    assert p1_body["total"] == 3
    assert p1_body["page"] == 1
    assert p1_body["page_size"] == 2
    assert p1_body["total_pages"] == 2

    # Page 2 with page_size=2
    res_p2 = client.get(f"{settings.api_prefix}/documents?page=2&page_size=2")
    assert res_p2.status_code == 200
    p2_body = res_p2.json()
    assert len(p2_body["items"]) == 1
    assert p2_body["total"] == 3
    assert p2_body["page"] == 2

    # Ensure items do not overlap
    p1_ids = {item["document_id"] for item in p1_body["items"]}
    p2_ids = {item["document_id"] for item in p2_body["items"]}
    assert p1_ids.isdisjoint(p2_ids)


def test_list_documents_filtering_by_status_and_source_type(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    # Ingest a processed text document
    _ingest(client, settings, "notes.txt", b"Clear property notes")

    # Ingest an OCR-required PDF
    empty_pdf = make_pdf(["", ""])
    ocr_res = _ingest(
        client, settings, "scanned.pdf", empty_pdf, content_type="application/pdf"
    )
    assert ocr_res.status_code == 200
    assert ocr_res.json()["status"] == "ocr_required"

    # Filter by status=ocr_required
    res_ocr = client.get(f"{settings.api_prefix}/documents?status=ocr_required")
    assert res_ocr.status_code == 200
    ocr_body = res_ocr.json()
    assert ocr_body["total"] == 1
    assert ocr_body["items"][0]["status"] == "ocr_required"
    assert ocr_body["items"][0]["filename"] == "scanned.pdf"

    # Filter by source_type=txt
    res_txt = client.get(f"{settings.api_prefix}/documents?source_type=txt")
    assert res_txt.status_code == 200
    txt_body = res_txt.json()
    assert txt_body["total"] == 1
    assert txt_body["items"][0]["source_type"] == "txt"
    assert txt_body["items"][0]["filename"] == "notes.txt"


def test_list_documents_invalid_pagination(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    # page < 1
    res = client.get(f"{settings.api_prefix}/documents?page=0")
    assert res.status_code == 422

    # page_size > 100
    res2 = client.get(f"{settings.api_prefix}/documents?page_size=101")
    assert res2.status_code == 422


# --- Document Metadata Retrieval ----------------------------------------------


def test_get_document_metadata_success(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    ingest_res = _ingest(client, settings, "deed.txt", SAMPLE_TEXT.encode())
    doc_id = ingest_res.json()["document_id"]

    res = client.get(f"{settings.api_prefix}/documents/{doc_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["document_id"] == doc_id
    assert body["filename"] == "deed.txt"
    assert body["source_type"] == "txt"
    assert body["status"] == "processed"
    assert len(body["content_sha256"]) == 64
    assert body["extracted_characters"] > 0
    assert body["chunk_count"] > 0
    assert body["created_at"] is not None


def test_get_document_metadata_not_found(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    res = client.get(f"{settings.api_prefix}/documents/doc_doesnotexist")
    assert res.status_code == 404
    assert res.json()["detail"] == "Document not found."


def test_get_document_metadata_invalid_id(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    # Whitespace id
    res = client.get(f"{settings.api_prefix}/documents/%20%20%20")
    assert res.status_code == 422


# --- Chunk Metadata Inspection ------------------------------------------------


def test_get_document_chunks_without_and_with_text(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    ingest_res = _ingest(client, settings, "deed.txt", SAMPLE_TEXT.encode())
    doc_id = ingest_res.json()["document_id"]

    # Default: include_text is False (protects content)
    res_no_text = client.get(f"{settings.api_prefix}/documents/{doc_id}/chunks")
    assert res_no_text.status_code == 200
    body_no_text = res_no_text.json()
    assert body_no_text["document_id"] == doc_id
    assert body_no_text["total"] >= 1
    assert len(body_no_text["items"]) >= 1
    chunk = body_no_text["items"][0]
    assert chunk["text"] is None
    assert chunk["chunk_id"].startswith("chk_")
    assert chunk["source_filename"] == "deed.txt"
    assert "character_count" in chunk["metadata"]

    # Requesting include_text=True returns chunk text
    res_with_text = client.get(
        f"{settings.api_prefix}/documents/{doc_id}/chunks?include_text=true"
    )
    assert res_with_text.status_code == 200
    body_with_text = res_with_text.json()
    assert body_with_text["items"][0]["text"] is not None
    assert "PROPERTY SALE AGREEMENT" in body_with_text["items"][0]["text"]


def test_get_document_chunks_not_found(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    res = client.get(f"{settings.api_prefix}/documents/doc_missing/chunks")
    assert res.status_code == 404
    assert res.json()["detail"] == "Document not found."


def test_get_document_chunks_pagination(tmp_path):
    settings = _settings(tmp_path)
    # Configure smaller chunks to generate multiple chunks
    settings = _settings(tmp_path, document_chunk_size_chars=50, document_chunk_overlap_chars=10)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    long_text = "Paragraph number one. " * 20
    ingest_res = _ingest(client, settings, "multi_chunk.txt", long_text.encode())
    doc_id = ingest_res.json()["document_id"]
    total_chunks = ingest_res.json()["chunk_count"]
    assert total_chunks > 2

    # Get page 1 with page_size=2
    res = client.get(f"{settings.api_prefix}/documents/{doc_id}/chunks?page=1&page_size=2")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["total"] == total_chunks
    assert body["page"] == 1
    assert body["page_size"] == 2


# --- Document Deletion & Lifecycle --------------------------------------------


def test_delete_document_success(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    ingest_res = _ingest(client, settings, "to_delete.txt", SAMPLE_TEXT.encode())
    doc_id = ingest_res.json()["document_id"]

    # Delete
    del_res = client.delete(f"{settings.api_prefix}/documents/{doc_id}")
    assert del_res.status_code == 200
    del_body = del_res.json()
    assert del_body["document_id"] == doc_id
    assert del_body["deleted"] is True

    # Subsequent GET document metadata returns 404
    get_res = client.get(f"{settings.api_prefix}/documents/{doc_id}")
    assert get_res.status_code == 404

    # Subsequent GET chunks returns 404
    chunks_res = client.get(f"{settings.api_prefix}/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 404

    # Subsequent DELETE returns 404
    del2_res = client.delete(f"{settings.api_prefix}/documents/{doc_id}")
    assert del2_res.status_code == 404


def test_delete_and_reupload_is_clean(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore()
    client = _client_with_store(settings, store)

    # Initial upload
    res1 = _ingest(client, settings, "reupload.txt", b"Unique content 12345")
    assert res1.status_code == 200
    doc_id1 = res1.json()["document_id"]

    # Idempotent re-upload returns same doc_id
    res_idempotent = _ingest(client, settings, "reupload.txt", b"Unique content 12345")
    assert res_idempotent.json()["document_id"] == doc_id1

    # Delete
    del_res = client.delete(f"{settings.api_prefix}/documents/{doc_id1}")
    assert del_res.status_code == 200

    # Re-upload exact same document after deletion
    res2 = _ingest(client, settings, "reupload.txt", b"Unique content 12345")
    assert res2.status_code == 200
    doc_id2 = res2.json()["document_id"]
    assert doc_id2 != doc_id1  # Fresh document generated cleanly


def test_database_error_handling(tmp_path):
    settings = _settings(tmp_path)
    store = FakeDocumentStore(error=DatabaseUnavailableError("The database is unavailable."))
    client = _client_with_store(settings, store)

    res_list = client.get(f"{settings.api_prefix}/documents")
    assert res_list.status_code == 503
    assert "database is unavailable" in res_list.json()["detail"].lower()
