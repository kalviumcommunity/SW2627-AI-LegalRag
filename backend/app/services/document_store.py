"""Durable document/chunk/embedding storage backed by PostgreSQL + pgvector.

The store is deliberately small and transactional. Ingestion only reports
success after ``save`` has committed the document, every chunk, and every
embedding. Identical uploads (same bytes and filename) are treated as the same
document: the existing persisted response is returned and no duplicate rows are
created.
"""

from __future__ import annotations

import re
import threading
from typing import Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.schemas.documents import DocumentChunk, IngestResponse
from app.services.storage_errors import (
    DatabaseConfigurationError,
    DatabaseSchemaError,
    DatabaseUnavailableError,
    DatabaseWriteError,
)

_VECTOR_TYPE_RE = re.compile(r"vector\((\d+)\)")

# One connection pool per distinct database configuration, shared by all
# request-scoped store instances.
_ENGINE_CACHE: dict[tuple, Engine] = {}
_ENGINE_CACHE_LOCK = threading.Lock()


def _shared_engine(settings: Settings) -> Engine:
    url = (settings.database_url or "").strip()
    if not url:
        raise DatabaseConfigurationError(
            "Persistence is not configured. Set DATABASE_URL "
            "and run `alembic upgrade head`."
        )
    key = (
        url,
        settings.database_echo,
        settings.database_pool_size,
        settings.database_connect_timeout_seconds,
    )
    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(key)
        if engine is None:
            try:
                engine = create_engine(
                    url,
                    echo=settings.database_echo,
                    pool_pre_ping=True,
                    pool_size=settings.database_pool_size,
                    connect_args={
                        "connect_timeout": (
                            settings.database_connect_timeout_seconds
                        )
                    },
                )
            except Exception as exc:
                raise DatabaseConfigurationError(
                    "The database connection could not be configured. "
                    "Check DATABASE_URL."
                ) from exc
            _ENGINE_CACHE[key] = engine
    return engine


class DocumentStore(Protocol):
    """Persistence interface consumed by the ingestion service."""

    def ensure_ready(self) -> None: ...

    def find_by_content_hash(
        self, content_hash: str, filename: str
    ) -> IngestResponse | None: ...

    def save(
        self,
        response: IngestResponse,
        content_hash: str,
        embeddings: list[list[float]],
    ) -> IngestResponse: ...


class UnavailableDocumentStore:
    """Store used when no DATABASE_URL is configured."""

    def ensure_ready(self) -> None:
        raise DatabaseConfigurationError(
            "Persistence is not configured. Set DATABASE_URL and run "
            "`alembic upgrade head` before ingesting documents."
        )

    def find_by_content_hash(
        self, content_hash: str, filename: str
    ) -> IngestResponse | None:
        self.ensure_ready()
        return None

    def save(
        self,
        response: IngestResponse,
        content_hash: str,
        embeddings: list[list[float]],
    ) -> IngestResponse:
        self.ensure_ready()
        return response


class SqlAlchemyDocumentStore:
    """SQLAlchemy implementation of the durable document store."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: Engine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._engine = engine
        self._session_factory: sessionmaker[Session] | None = None
        self._verified_dimensions: int | None = None
        # Reentrant: ensure_ready holds the lock while _get_engine/_get_session
        # factory may also need it.
        self._lock = threading.RLock()

    # --- engine/session --------------------------------------------------

    def _get_engine(self) -> Engine:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = _shared_engine(self.settings)
        return self._engine

    def _get_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            with self._lock:
                if self._session_factory is None:
                    self._session_factory = sessionmaker(
                        bind=self._get_engine(),
                        expire_on_commit=False,
                    )
        return self._session_factory

    # --- schema verification --------------------------------------------

    def ensure_ready(self) -> None:
        """Verify connectivity, schema presence, and vector dimensions."""
        if self._verified_dimensions is not None:
            return
        with self._lock:
            if self._verified_dimensions is not None:
                return
            engine = self._get_engine()
            try:
                with engine.connect() as connection:
                    tables = connection.execute(
                        text(
                            "SELECT to_regclass('documents'), to_regclass('chunks')"
                        )
                    ).one()
                    if tables[0] is None or tables[1] is None:
                        raise DatabaseSchemaError(
                            "The database schema is not initialized. Run "
                            "`alembic upgrade head`."
                        )
                    vector_type = connection.execute(
                        text(
                            "SELECT format_type(atttypid, atttypmod) "
                            "FROM pg_attribute "
                            "WHERE attrelid = 'chunks'::regclass "
                            "AND attname = 'embedding' AND NOT attisdropped"
                        )
                    ).scalar_one_or_none()
            except (DatabaseSchemaError, DatabaseConfigurationError):
                raise
            except ProgrammingError as exc:
                raise DatabaseSchemaError(
                    "The database schema is not initialized or the pgvector "
                    "extension is missing. Run `CREATE EXTENSION vector` and "
                    "`alembic upgrade head`."
                ) from exc
            except OperationalError as exc:
                raise DatabaseUnavailableError(
                    "The database is unavailable. Check that PostgreSQL is "
                    "running and DATABASE_URL is correct."
                ) from exc
            except SQLAlchemyError as exc:
                raise DatabaseUnavailableError(
                    "The database could not be reached."
                ) from exc

        match = _VECTOR_TYPE_RE.fullmatch(vector_type or "")
        if match is None:
            raise DatabaseSchemaError(
                "The chunks.embedding column is not a pgvector vector column. "
                "Run `alembic upgrade head`."
            )
        dimension = int(match.group(1))
        if dimension != self.settings.embedding_dimensions:
            raise DatabaseSchemaError(
                "Embedding dimension mismatch: the database vector column has "
                f"dimension {dimension}, but EMBEDDING_DIMENSIONS is "
                f"{self.settings.embedding_dimensions}. Create a migration "
                "for the new model dimensions before ingesting."
            )
        self._verified_dimensions = dimension

    # --- reads -----------------------------------------------------------

    def find_by_content_hash(
        self, content_hash: str, filename: str
    ) -> IngestResponse | None:
        self.ensure_ready()
        try:
            with self._get_session_factory()() as session:
                document = session.query(Document).filter_by(
                    content_sha256=content_hash, filename=filename
                ).one_or_none()
                if document is None:
                    return None
                return _to_response(document)
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "The stored document could not be read."
            ) from exc

    # --- writes ----------------------------------------------------------

    def save(
        self,
        response: IngestResponse,
        content_hash: str,
        embeddings: list[list[float]],
    ) -> IngestResponse:
        self.ensure_ready()
        if len(embeddings) != len(response.chunks):
            raise DatabaseWriteError(
                "Embedding count does not match the number of chunks."
            )
        for vector in embeddings:
            if len(vector) != self.settings.embedding_dimensions:
                raise DatabaseWriteError(
                    "An embedding does not match the configured dimensions."
                )

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    document = Document(
                        id=response.document_id,
                        filename=response.filename,
                        source_type=(
                            response.chunks[0].source_type
                            if response.chunks
                            else _source_type_for(response)
                        ),
                        status=response.status,
                        content_sha256=content_hash,
                        extracted_characters=response.extracted_characters,
                        chunk_count=response.chunk_count,
                        page_count=response.page_count,
                        warnings=list(response.warnings),
                        detail=response.detail,
                    )
                    session.add(document)
                    for chunk, vector in zip(response.chunks, embeddings):
                        session.add(
                            Chunk(
                                id=chunk.chunk_id,
                                document_id=response.document_id,
                                chunk_index=chunk.chunk_index,
                                text=chunk.text,
                                source_filename=chunk.source_filename,
                                source_type=chunk.source_type,
                                page_number=chunk.page_number,
                                start_offset=chunk.start_offset,
                                end_offset=chunk.end_offset,
                                chunk_metadata=dict(chunk.metadata),
                                embedding=list(vector),
                            )
                        )
            return response
        except IntegrityError as exc:
            # A concurrent request may have inserted the same document after
            # our duplicate check. Return the committed record if it exists.
            existing = self.find_by_content_hash(content_hash, response.filename)
            if existing is not None:
                return existing
            raise DatabaseWriteError(
                "The document could not be stored because of a database "
                "constraint conflict."
            ) from exc
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database became unavailable while storing the document."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "The document could not be stored; no records were committed."
            ) from exc


def _source_type_for(response: IngestResponse) -> str:
    if response.filename.lower().endswith(".pdf"):
        return "pdf"
    if response.filename.lower().endswith(".md"):
        return "markdown"
    return "txt"


def _to_response(document: Document) -> IngestResponse:
    chunks = [
        DocumentChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            source_filename=chunk.source_filename,
            source_type=chunk.source_type,
            page_number=chunk.page_number,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            metadata=dict(chunk.chunk_metadata or {}),
        )
        for chunk in sorted(document.chunks, key=lambda item: item.chunk_index)
    ]
    return IngestResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        extracted_characters=document.extracted_characters,
        chunk_count=document.chunk_count,
        chunks=chunks,
        page_count=document.page_count,
        warnings=list(document.warnings or []),
        detail=document.detail,
    )


def create_document_store(settings: Settings | None = None) -> DocumentStore:
    """Build the configured store, or a safe unavailable placeholder."""
    settings = settings or get_settings()
    if not settings.is_database_configured:
        return UnavailableDocumentStore()
    return SqlAlchemyDocumentStore(settings)
