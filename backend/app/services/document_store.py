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
from app.schemas.documents import (
    DocumentChunk,
    DocumentChunkSummary,
    DocumentDetailResponse,
    DocumentSummary,
    IngestResponse,
)
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


def get_shared_engine(settings: Settings) -> Engine:
    """Return a process-wide pool for the configured database.

    Shared by ingestion and retrieval so both use the same connection limits
    and schema verification without building separate pools per request.
    """
    url = settings.get_database_url(direct=False)
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


def verify_vector_schema(engine: Engine, settings: Settings) -> int:
    """Check the tables, pgvector column, and configured dimensions.

    Returns the physical vector dimension. Shared by ingestion and retrieval so
    both fail with the same safe configuration error instead of surfacing a
    database exception.
    """
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
    if dimension != settings.embedding_dimensions:
        raise DatabaseSchemaError(
            "Embedding dimension mismatch: the database vector column has "
            f"dimension {dimension}, but EMBEDDING_DIMENSIONS is "
            f"{settings.embedding_dimensions}. Create a migration "
            "for the new model dimensions before storing or retrieving chunks."
        )
    return dimension


def verify_database_connectivity(settings: Settings) -> dict[str, Any]:
    """Execute a comprehensive, safe verification of database connectivity and schema.

    Returns structured verification results without exposing credentials.
    """
    url = settings.get_database_url(direct=False)
    if not url:
        return {
            "status": "unconfigured",
            "message": "DATABASE_URL is not configured.",
        }

    from urllib.parse import urlsplit
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    is_neon = "neon.tech" in hostname
    is_pooled = "-pooler" in hostname

    report: dict[str, Any] = {
        "is_neon": is_neon,
        "is_pooled": is_pooled,
        "simple_query": False,
        "pgvector_installed": False,
        "pgvector_version": None,
        "tables_exist": False,
        "tables": [],
        "embedding_dimensions": None,
        "indexes_verified": False,
        "status": "error",
    }

    try:
        engine = get_shared_engine(settings)
        with engine.connect() as conn:
            # 1. Simple query
            res = conn.execute(text("SELECT 1")).scalar()
            report["simple_query"] = bool(res == 1)

            # 2. Check pgvector extension
            ext_row = conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if ext_row:
                report["pgvector_installed"] = True
                report["pgvector_version"] = ext_row[1]

            # 3. Check tables
            tables = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            ).scalars().all()
            report["tables"] = tables
            report["tables_exist"] = "documents" in tables and "chunks" in tables

            # 4. Check indexes on chunks
            if "chunks" in tables:
                indexes = conn.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'")
                ).scalars().all()
                report["indexes_verified"] = (
                    "ix_chunks_embedding_hnsw" in indexes and "ix_chunks_text_fts" in indexes
                )

        # 5. Check vector schema dimension compatibility
        dim = verify_vector_schema(engine, settings)
        report["embedding_dimensions"] = dim

        if report["simple_query"] and report["pgvector_installed"] and report["tables_exist"] and report["indexes_verified"]:
            report["status"] = "healthy"
            report["message"] = "Neon PostgreSQL connection, pgvector extension, and schema verified successfully."
        else:
            report["status"] = "partially_initialized"
            report["message"] = "Database reachable but schema or indexes are not fully initialized."

    except Exception as exc:
        report["status"] = "error"
        report["message"] = (
            "Database connectivity check failed. Check network access, SSL configuration, or credentials."
        )

    return report


class DocumentStore(Protocol):
    """Persistence interface consumed by ingestion and document management."""

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

    def get_document(
        self, document_id: str
    ) -> DocumentDetailResponse | None: ...

    def list_documents(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[DocumentSummary], int]: ...

    def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        include_text: bool = False,
    ) -> tuple[list[DocumentChunkSummary], int] | None: ...

    def delete_document(self, document_id: str) -> bool: ...


class UnavailableDocumentStore:
    """Store used when no DATABASE_URL is configured."""

    def ensure_ready(self) -> None:
        raise DatabaseConfigurationError(
            "Persistence is not configured. Set DATABASE_URL and run "
            "`alembic upgrade head` before managing or ingesting documents."
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

    def get_document(
        self, document_id: str
    ) -> DocumentDetailResponse | None:
        self.ensure_ready()
        return None

    def list_documents(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        self.ensure_ready()
        return [], 0

    def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        include_text: bool = False,
    ) -> tuple[list[DocumentChunkSummary], int] | None:
        self.ensure_ready()
        return None

    def delete_document(self, document_id: str) -> bool:
        self.ensure_ready()
        return False


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
                    self._engine = get_shared_engine(self.settings)
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
            self._verified_dimensions = verify_vector_schema(
                self._get_engine(), self.settings
            )

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

    def get_document(self, document_id: str) -> DocumentDetailResponse | None:
        self.ensure_ready()
        try:
            with self._get_session_factory()() as session:
                document = (
                    session.query(Document)
                    .filter(Document.id == document_id)
                    .one_or_none()
                )
                if document is None:
                    return None
                return DocumentDetailResponse(
                    document_id=document.id,
                    filename=document.filename,
                    source_type=document.source_type,
                    status=document.status,
                    content_sha256=document.content_sha256,
                    extracted_characters=document.extracted_characters,
                    chunk_count=document.chunk_count,
                    page_count=document.page_count,
                    warnings=list(document.warnings or []),
                    detail=document.detail,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "The stored document could not be read."
            ) from exc

    def list_documents(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        self.ensure_ready()
        try:
            with self._get_session_factory()() as session:
                query = session.query(Document)
                if status is not None:
                    query = query.filter(Document.status == status)
                if source_type is not None:
                    query = query.filter(Document.source_type == source_type)
                total = query.count()
                documents = (
                    query.order_by(Document.created_at.desc(), Document.id.desc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                items = [
                    DocumentSummary(
                        document_id=doc.id,
                        filename=doc.filename,
                        source_type=doc.source_type,
                        status=doc.status,
                        extracted_characters=doc.extracted_characters,
                        chunk_count=doc.chunk_count,
                        page_count=doc.page_count,
                        warnings=list(doc.warnings or []),
                        detail=doc.detail,
                        created_at=doc.created_at,
                        updated_at=doc.updated_at,
                    )
                    for doc in documents
                ]
                return items, total
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "Documents could not be listed."
            ) from exc

    def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        include_text: bool = False,
    ) -> tuple[list[DocumentChunkSummary], int] | None:
        self.ensure_ready()
        try:
            with self._get_session_factory()() as session:
                doc_exists = (
                    session.query(Document.id)
                    .filter(Document.id == document_id)
                    .scalar()
                )
                if doc_exists is None:
                    return None
                chunk_query = session.query(Chunk).filter(
                    Chunk.document_id == document_id
                )
                total = chunk_query.count()
                chunks = (
                    chunk_query.order_by(Chunk.chunk_index.asc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                items = [
                    DocumentChunkSummary(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        source_filename=chunk.source_filename,
                        source_type=chunk.source_type,
                        page_number=chunk.page_number,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        metadata=dict(chunk.chunk_metadata or {}),
                        text=chunk.text if include_text else None,
                    )
                    for chunk in chunks
                ]
                return items, total
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "Document chunks could not be read."
            ) from exc

    def delete_document(self, document_id: str) -> bool:
        self.ensure_ready()
        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    doc = (
                        session.query(Document)
                        .filter(Document.id == document_id)
                        .one_or_none()
                    )
                    if doc is None:
                        return False
                    session.delete(doc)
                return True
        except OperationalError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError(
                "The document could not be deleted."
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
