"""End-to-end ingestion -> chunk -> embed -> persist integration tests.

Requires TEST_DATABASE_URL (PostgreSQL with pgvector). Embedding calls are
mocked; no external provider is contacted.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.routes import documents
from app.core.config import Settings
from app.main import create_app
from app.services.embedding_service import EmbeddingService
from app.services.storage_errors import DatabaseWriteError
from tests.fakes import FakeDocumentStore, FakeEmbeddingProvider

SAMPLE_TEXT = (
    "SALE DEED\n\n"
    "Clause 1. The seller agrees to sell the property described in Schedule A.\n\n"
    "Clause 2. Consideration is Rs. 50,00,000 payable on 2026-12-01 at Bengaluru."
)


def _database_url(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def _settings(url: str, tmp_path: Path, **overrides) -> Settings:
    values = {
        "groq_api_key": None,
        "database_url": url,
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 768,
        "document_temp_dir": str(tmp_path / "ingest_temp"),
    }
    values.update(overrides)
    return Settings(**values)


def _client(
    settings: Settings,
    embedding_provider=None,
    store=None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[documents.get_settings_dep] = lambda: settings
    service = EmbeddingService(
        settings,
        provider=embedding_provider
        or FakeEmbeddingProvider(dimensions=settings.embedding_dimensions),
    )
    app.dependency_overrides[documents.get_embedding_service] = lambda: service
    if store is not None:
        app.dependency_overrides[documents.get_document_store] = lambda: store
    return TestClient(app)


def _ingest(client: TestClient, settings: Settings, filename: str, data: bytes):
    return client.post(
        f"{settings.api_prefix}/documents/ingest",
        files={"file": (filename, data, "text/plain")},
    )


def test_ingestion_persists_document_chunks_and_embeddings(
    clean_database, tmp_path
):
    settings = _settings(_database_url(clean_database), tmp_path)
    client = _client(settings)

    response = _ingest(
        client, settings, "property_notes.txt", SAMPLE_TEXT.encode()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["chunk_count"] >= 1

    with clean_database.connect() as connection:
        document = connection.execute(
            text(
                "SELECT status, chunk_count FROM documents WHERE id = :id"
            ),
            {"id": body["document_id"]},
        ).mappings().one()
        assert document["status"] == "processed"
        assert document["chunk_count"] == body["chunk_count"]

        chunks = connection.execute(
            text(
                "SELECT text, chunk_index, metadata, vector_dims(embedding) "
                "AS dims FROM chunks WHERE document_id = :id "
                "ORDER BY chunk_index"
            ),
            {"id": body["document_id"]},
        ).mappings().all()

    assert len(chunks) == body["chunk_count"]
    assert chunks[0]["text"] == body["chunks"][0]["text"]
    assert chunks[0]["metadata"]["character_count"] == len(chunks[0]["text"])
    assert all(row["dims"] == 768 for row in chunks)


def test_duplicate_ingestion_does_not_create_duplicate_rows(
    clean_database, tmp_path
):
    settings = _settings(_database_url(clean_database), tmp_path)
    client = _client(settings)

    first = _ingest(client, settings, "duplicate.txt", SAMPLE_TEXT.encode())
    second = _ingest(client, settings, "duplicate.txt", SAMPLE_TEXT.encode())

    assert first.status_code == second.status_code == 200
    assert first.json()["document_id"] == second.json()["document_id"]

    with clean_database.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM documents) AS docs, "
                "(SELECT count(*) FROM chunks) AS chunks"
            )
        ).one()
    assert counts.docs == 1
    assert counts.chunks == first.json()["chunk_count"]


def test_embedding_failure_returns_502_and_stores_nothing(
    clean_database, tmp_path
):
    settings = _settings(_database_url(clean_database), tmp_path)
    provider = FakeEmbeddingProvider(
        dimensions=768,
        error=RuntimeError("internal provider failure with secret-value"),
    )
    client = _client(settings, embedding_provider=provider)

    response = _ingest(client, settings, "failure.txt", SAMPLE_TEXT.encode())

    assert response.status_code == 502
    assert "secret-value" not in response.text
    assert "internal provider failure" not in response.text
    assert "traceback" not in response.text.lower()
    with clean_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM chunks")).scalar() == 0


def test_storage_failure_returns_500_and_never_reports_success(
    clean_database, tmp_path
):
    settings = _settings(_database_url(clean_database), tmp_path)
    store = FakeDocumentStore(error=DatabaseWriteError("mock write failure"))
    client = _client(settings, store=store)

    response = _ingest(client, settings, "storage_failure.txt", SAMPLE_TEXT.encode())

    assert response.status_code == 500
    assert "traceback" not in response.text.lower()
    with clean_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar() == 0


def test_unavailable_database_returns_safe_503(clean_database, tmp_path):
    password = "super-secret-password"
    settings = _settings(
        f"postgresql+psycopg://property:{password}@127.0.0.1:59999/nope",
        tmp_path,
        database_connect_timeout_seconds=1,
    )
    client = _client(settings)

    response = _ingest(client, settings, "offline.txt", SAMPLE_TEXT.encode())

    assert response.status_code == 503
    assert password not in response.text
    assert "traceback" not in response.text.lower()
    assert "database" in response.json()["detail"].lower()
