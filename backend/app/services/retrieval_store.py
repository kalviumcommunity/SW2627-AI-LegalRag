"""Database access for semantic and full-text retrieval.

Semantic search uses pgvector's cosine distance operator (``<=>``) against the
existing HNSW index (``vector_cosine_ops``). Cosine distance is in [0, 2] for
normalized vectors; the service exposes ``1 - distance`` as cosine similarity,
where higher is better. Hybrid keyword search uses PostgreSQL full-text search
(``to_tsvector`` / ``plainto_tsquery`` / ``ts_rank_cd``) and never introduces a
second search service.

All metadata filters are applied as parameterized SQL predicates before rows
leave PostgreSQL.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.services.document_store import get_shared_engine, verify_vector_schema
from app.services.retrieval_errors import (
    RetrievalConfigurationError,
    RetrievalDatabaseError,
    RetrievalExecutionError,
)
from app.services.storage_errors import DocumentStorageUnavailableError


@dataclass(frozen=True)
class SearchFilters:
    """Validated filters passed from the retrieval service to the store."""

    document_id: str | None = None
    source_filename: str | None = None
    source_type: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class ChunkRecord:
    """A chunk row without any ranking information."""

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    source_filename: str
    source_type: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None
    chunk_metadata: dict[str, Any] = field(default_factory=dict)
    document_created_at: datetime | None = None


@dataclass(frozen=True)
class SemanticMatch:
    record: ChunkRecord
    distance: float
    similarity: float


@dataclass(frozen=True)
class KeywordMatch:
    record: ChunkRecord
    rank: int
    relevance: float


class RetrievalStore(Protocol):
    """Database interface consumed by :class:`RetrievalService`."""

    def ensure_ready(self) -> None: ...

    def search_semantic(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float | None = None,
    ) -> list[SemanticMatch]: ...

    def search_keyword(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters,
    ) -> list[KeywordMatch]: ...


class UnavailableRetrievalStore:
    """Store used when no DATABASE_URL is configured."""

    def ensure_ready(self) -> None:
        raise RetrievalConfigurationError(
            "Retrieval is not configured. Set DATABASE_URL and run "
            "`alembic upgrade head`."
        )

    def search_semantic(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float | None = None,
    ) -> list[SemanticMatch]:
        self.ensure_ready()
        return []

    def search_keyword(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters,
    ) -> list[KeywordMatch]:
        self.ensure_ready()
        return []


class SqlAlchemyRetrievalStore:
    """PostgreSQL/pgvector implementation of the retrieval store."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: Engine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._engine = engine
        self._session_factory: sessionmaker[Session] | None = None
        self._ready = False
        self._lock = threading.RLock()

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

    def ensure_ready(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            try:
                verify_vector_schema(self._get_engine(), self.settings)
            except DocumentStorageUnavailableError as exc:
                raise RetrievalConfigurationError(exc.message) from exc
            self._ready = True

    def search_semantic(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float | None = None,
    ) -> list[SemanticMatch]:
        self.ensure_ready()
        distance_expression = Chunk.embedding.cosine_distance(query_vector)
        statement = (
            select(
                Chunk,
                Document.created_at.label("document_created_at"),
                distance_expression.label("distance"),
            )
            .join(Document, Document.id == Chunk.document_id)
        )
        statement = self._apply_filters(statement, filters)
        if min_score is not None:
            statement = statement.where(
                (1.0 - distance_expression) >= min_score
            )
        statement = statement.order_by(
            distance_expression.asc(), Chunk.id.asc()
        ).limit(limit)

        try:
            with self._get_session_factory()() as session:
                rows = session.execute(statement).all()
        except OperationalError as exc:
            raise RetrievalDatabaseError(
                "The database is unavailable."
            ) from exc
        except ProgrammingError as exc:
            raise RetrievalConfigurationError(
                "The database schema or vector configuration is invalid. "
                "Run `alembic upgrade head` and verify EMBEDDING_DIMENSIONS."
            ) from exc
        except SQLAlchemyError as exc:
            raise RetrievalExecutionError(
                "The retrieval query failed safely; no results were returned."
            ) from exc

        matches: list[SemanticMatch] = []
        for chunk, document_created_at, distance in rows:
            distance_value = float(distance)
            matches.append(
                SemanticMatch(
                    record=_to_record(chunk, document_created_at),
                    distance=distance_value,
                    similarity=_clamp_similarity(1.0 - distance_value),
                )
            )
        return matches

    def search_keyword(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters,
    ) -> list[KeywordMatch]:
        self.ensure_ready()
        # A literal regconfig lets PostgreSQL match the GIN expression index
        # (``to_tsvector('english', text)``) instead of a bind parameter that
        # the planner cannot prove stable at plan time.
        english = literal_column("'english'::regconfig")
        document_vector = func.to_tsvector(english, Chunk.text)
        query_vector = func.plainto_tsquery(english, query)
        relevance = func.ts_rank_cd(document_vector, query_vector)

        statement = (
            select(
                Chunk,
                Document.created_at.label("document_created_at"),
                relevance.label("relevance"),
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(document_vector.op("@@")(query_vector))
        )
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(
            relevance.desc(), Chunk.id.asc()
        ).limit(limit)

        try:
            with self._get_session_factory()() as session:
                rows = session.execute(statement).all()
        except OperationalError as exc:
            raise RetrievalDatabaseError(
                "The database is unavailable."
            ) from exc
        except ProgrammingError as exc:
            raise RetrievalConfigurationError(
                "The database schema or full-text configuration is invalid. "
                "Run `alembic upgrade head`."
            ) from exc
        except SQLAlchemyError as exc:
            raise RetrievalExecutionError(
                "The keyword retrieval query failed safely; no results were "
                "returned."
            ) from exc

        return [
            KeywordMatch(
                record=_to_record(chunk, document_created_at),
                rank=index,
                relevance=float(score),
            )
            for index, (chunk, document_created_at, score) in enumerate(
                rows, start=1
            )
        ]

    @staticmethod
    def _apply_filters(statement, filters: SearchFilters):
        if filters.document_id is not None:
            statement = statement.where(
                Chunk.document_id == filters.document_id
            )
        if filters.source_filename is not None:
            statement = statement.where(
                Chunk.source_filename == filters.source_filename
            )
        if filters.source_type is not None:
            statement = statement.where(
                Chunk.source_type == filters.source_type
            )
        if filters.page_number is not None:
            # Phase 2 sets page_number only for single-page chunks and stores
            # the full page set in metadata.page_numbers for spans.
            statement = statement.where(
                or_(
                    Chunk.page_number == filters.page_number,
                    Chunk.chunk_metadata["page_numbers"].contains(
                        [filters.page_number]
                    ),
                )
            )
        return statement


def _to_record(
    chunk: Chunk, document_created_at: datetime | None = None
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        source_filename=chunk.source_filename,
        source_type=chunk.source_type,
        page_number=chunk.page_number,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        chunk_metadata=dict(chunk.chunk_metadata or {}),
        document_created_at=document_created_at,
    )


def _clamp_similarity(value: float) -> float:
    """Keep floating-point noise inside cosine similarity's [-1, 1] range."""
    return max(-1.0, min(1.0, value))


def create_retrieval_store(settings: Settings | None = None) -> RetrievalStore:
    """Build the configured store, or a safe unavailable placeholder."""
    settings = settings or get_settings()
    if not settings.is_database_configured:
        return UnavailableRetrievalStore()
    return SqlAlchemyRetrievalStore(settings)
