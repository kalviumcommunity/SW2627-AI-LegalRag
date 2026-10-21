"""PostgreSQL/pgvector persistence tests.

These tests require a dedicated database supplied through TEST_DATABASE_URL.
They are skipped (not silently passed) when it is absent.
"""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import Settings
from app.schemas.documents import DocumentChunk, IngestResponse
from app.services.document_store import SqlAlchemyDocumentStore
from app.services.storage_errors import (
    DatabaseSchemaError,
    DatabaseUnavailableError,
    DatabaseWriteError,
)


def _database_url(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def _settings(url: str, **overrides) -> Settings:
    values = {
        "database_url": url,
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 768,
    }
    values.update(overrides)
    return Settings(**values)


def _vector(seed: int = 1) -> list[float]:
    vector = [0.0] * 768
    vector[seed % 768] = 1.0
    return vector


def _response(
    document_id: str = "doc_test",
    filename: str = "deed.pdf",
    chunks: list[DocumentChunk] | None = None,
) -> IngestResponse:
    if chunks is None:
        chunks = [
            DocumentChunk(
                chunk_id=f"chk_{document_id}_{index}",
                document_id=document_id,
                chunk_index=index,
                text=f"Clause {index + 1}: sale deed text.",
                source_filename=filename,
                source_type="pdf",
                page_number=index + 1,
                start_offset=index * 10,
                end_offset=index * 10 + 9,
                metadata={
                    "character_count": 27,
                    "page_numbers": [index + 1],
                    "total_pages": 2,
                    "chunking": {
                        "strategy": "character",
                        "chunk_size_chars": 3200,
                        "overlap_chars": 480,
                    },
                },
            )
            for index in range(2)
        ]
    return IngestResponse(
        document_id=document_id,
        filename=filename,
        status="processed",
        extracted_characters=100,
        chunk_count=len(chunks),
        chunks=chunks,
        page_count=2,
        warnings=["sample warning"],
        detail=None,
    )


def test_document_chunks_metadata_and_vectors_are_stored(clean_database):
    store = SqlAlchemyDocumentStore(_settings(_database_url(clean_database)))
    response = _response()

    saved = store.save(response, "a" * 64, [_vector(1), _vector(2)])

    assert saved.document_id == "doc_test"
    with clean_database.connect() as connection:
        document = connection.execute(
            text(
                "SELECT filename, source_type, status, chunk_count, page_count, "
                "warnings FROM documents WHERE id = :id"
            ),
            {"id": "doc_test"},
        ).mappings().one()
        assert document["filename"] == "deed.pdf"
        assert document["source_type"] == "pdf"
        assert document["status"] == "processed"
        assert document["chunk_count"] == 2
        assert document["page_count"] == 2
        assert document["warnings"] == ["sample warning"]

        chunks = connection.execute(
            text(
                "SELECT id, chunk_index, text, page_number, start_offset, "
                "end_offset, metadata, vector_dims(embedding) AS dims "
                "FROM chunks WHERE document_id = :id ORDER BY chunk_index"
            ),
            {"id": "doc_test"},
        ).mappings().all()
        assert [row["chunk_index"] for row in chunks] == [0, 1]
        assert [row["page_number"] for row in chunks] == [1, 2]
        assert chunks[0]["text"] == "Clause 1: sale deed text."
        assert chunks[0]["start_offset"] == 0
        assert chunks[0]["end_offset"] == 9
        assert chunks[0]["metadata"]["page_numbers"] == [1]
        assert all(row["dims"] == 768 for row in chunks)


def test_persisted_records_survive_a_new_store_instance(clean_database):
    url = _database_url(clean_database)
    first = SqlAlchemyDocumentStore(_settings(url))
    first.save(_response(), "b" * 64, [_vector(1), _vector(2)])

    second = SqlAlchemyDocumentStore(_settings(url))
    restored = second.find_by_content_hash("b" * 64, "deed.pdf")

    assert restored is not None
    assert restored.document_id == "doc_test"
    assert restored.chunk_count == 2
    assert [chunk.chunk_index for chunk in restored.chunks] == [0, 1]
    assert restored.chunks[0].metadata["total_pages"] == 2


def test_identical_reingestion_returns_existing_record_without_duplicates(
    clean_database,
):
    store = SqlAlchemyDocumentStore(_settings(_database_url(clean_database)))
    first = store.save(_response(), "c" * 64, [_vector(1), _vector(2)])
    second = store.save(_response(), "c" * 64, [_vector(3), _vector(4)])

    assert first.document_id == second.document_id == "doc_test"
    with clean_database.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM documents) AS docs, "
                "(SELECT count(*) FROM chunks) AS chunks"
            )
        ).one()
    assert counts.docs == 1
    assert counts.chunks == 2


def test_same_content_with_a_different_filename_is_a_new_document(
    clean_database,
):
    store = SqlAlchemyDocumentStore(_settings(_database_url(clean_database)))
    store.save(_response(), "d" * 64, [_vector(1), _vector(2)])
    store.save(
        _response(document_id="doc_other", filename="other.pdf"),
        "d" * 64,
        [_vector(1), _vector(2)],
    )

    with clean_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar() == 2


def test_transaction_rolls_back_document_when_a_chunk_fails(clean_database):
    store = SqlAlchemyDocumentStore(_settings(_database_url(clean_database)))
    bad_chunks = [
        DocumentChunk(
            chunk_id="chk_duplicate",
            document_id="doc_rollback",
            chunk_index=0,
            text="first",
            source_filename="bad.pdf",
            source_type="pdf",
            metadata={},
        ),
        DocumentChunk(
            chunk_id="chk_duplicate",
            document_id="doc_rollback",
            chunk_index=1,
            text="second",
            source_filename="bad.pdf",
            source_type="pdf",
            metadata={},
        ),
    ]

    try:
        store.save(
            _response(document_id="doc_rollback", chunks=bad_chunks),
            "e" * 64,
            [_vector(1), _vector(2)],
        )
    except DatabaseWriteError:
        pass
    else:  # pragma: no cover - the constraint must reject this
        raise AssertionError("expected DatabaseWriteError")

    with clean_database.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM documents) AS docs, "
                "(SELECT count(*) FROM chunks) AS chunks"
            )
        ).one()
    assert counts.docs == 0
    assert counts.chunks == 0


def test_deleting_a_document_cascades_to_chunks(clean_database):
    store = SqlAlchemyDocumentStore(_settings(_database_url(clean_database)))
    store.save(_response(), "f" * 64, [_vector(1), _vector(2)])

    with clean_database.begin() as connection:
        connection.execute(text("DELETE FROM documents WHERE id = 'doc_test'"))

    with clean_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM chunks")).scalar() == 0


def test_database_dimension_mismatch_is_a_clear_configuration_error(
    clean_database,
):
    store = SqlAlchemyDocumentStore(
        _settings(_database_url(clean_database), embedding_dimensions=4)
    )

    try:
        store.ensure_ready()
    except DatabaseSchemaError as exc:
        assert "dimension mismatch" in exc.message.lower()
    else:  # pragma: no cover
        raise AssertionError("expected DatabaseSchemaError")


def test_missing_migration_is_reported_safely(clean_database):
    with clean_database.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS phase3_missing CASCADE"))
        connection.execute(text("CREATE SCHEMA phase3_missing"))

    url = (
        f"{_database_url(clean_database)}"
        "?options=-csearch_path%3Dphase3_missing"
    )
    store = SqlAlchemyDocumentStore(_settings(url))
    try:
        store.ensure_ready()
    except DatabaseSchemaError as exc:
        assert "alembic upgrade head" in exc.message
    else:  # pragma: no cover
        raise AssertionError("expected DatabaseSchemaError")
    finally:
        with clean_database.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS phase3_missing CASCADE"))


def test_unreachable_database_is_reported_without_credentials():
    password = "super-secret-password"
    store = SqlAlchemyDocumentStore(
        _settings(
            f"postgresql+psycopg://property:{password}@127.0.0.1:59999/nope",
            database_connect_timeout_seconds=1,
        )
    )
    try:
        store.ensure_ready()
    except DatabaseUnavailableError as exc:
        assert password not in exc.message
        assert "unavailable" in exc.message.lower()
    else:  # pragma: no cover
        raise AssertionError("expected DatabaseUnavailableError")
