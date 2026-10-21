"""Semantic and hybrid retrieval over stored document chunks.

The service owns query validation, query embedding, ranking, fusion, and safe
error handling. It has no FastAPI dependency so it can be reused by the API,
the evaluation runner, and future RAG phases.

Score semantics
---------------
* Semantic ``score`` is cosine similarity (higher is better), derived from
  pgvector cosine distance: ``similarity = 1 - distance``.
* Hybrid ``score`` is an RRF score (higher is better). RRF combines rank
  positions only, so it is not comparable to cosine similarity or to scores
  from another retrieval mode.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import cast

from app.core.config import Settings, get_settings
from app.schemas.documents import SourceType
from app.schemas.retrieval import (
    RetrievalFilters,
    RetrievalMode,
    RetrievalResult,
    RetrievalResultMetadata,
    RetrievalSearchResponse,
    ScoreType,
)
from app.services.embedding_service import EmbeddingError, EmbeddingService
from app.services.retrieval_errors import (
    RetrievalConfigurationError,
    RetrievalError,
    RetrievalExecutionError,
    RetrievalQueryError,
)
from app.services.retrieval_store import (
    ChunkRecord,
    RetrievalStore,
    SearchFilters,
    create_retrieval_store,
)

logger = logging.getLogger(__name__)

_MODES = {"semantic", "hybrid"}


@dataclass(frozen=True)
class RetrievalOutcome:
    """A response plus timing data for observability and evaluation."""

    response: RetrievalSearchResponse
    embedding_duration_ms: float
    database_duration_ms: float
    total_duration_ms: float


@dataclass
class _FusedCandidate:
    record: ChunkRecord
    fused_score: float = 0.0
    semantic_distance: float | None = None
    semantic_score: float | None = None
    semantic_rank: int | None = None
    keyword_rank: int | None = None


class RetrievalService:
    """Validated, database-backed semantic and hybrid retrieval."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        embedding_service: EmbeddingService | None = None,
        store: RetrievalStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService(
            self.settings
        )
        self.store = store or create_retrieval_store(self.settings)

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        mode: RetrievalMode = "semantic",
        document_id: str | None = None,
        filters: RetrievalFilters | None = None,
        min_score: float | None = None,
    ) -> RetrievalOutcome:
        """Retrieve the most relevant chunks for ``query``.

        Results are ordered by cosine similarity (semantic) or reciprocal rank
        fusion (hybrid), always with deterministic chunk-ID tie breaking.
        """
        started = time.perf_counter()
        normalized_query = self._normalize_query(query)
        requested_top_k = self._validate_top_k(top_k)
        selected_mode = self._validate_mode(mode)
        threshold = self._validate_min_score(min_score)
        search_filters = _to_search_filters(document_id, filters)
        filter_fields = _used_filter_fields(search_filters)

        try:
            self.store.ensure_ready()
        except RetrievalError as exc:
            logger.warning(
                "retrieval_failed mode=%s top_k=%d error=%s filters=%s",
                selected_mode,
                requested_top_k,
                type(exc).__name__,
                filter_fields,
            )
            raise

        embedding_started = time.perf_counter()
        try:
            query_vector = self._embed_query(normalized_query)
        except (EmbeddingError, RetrievalError) as exc:
            logger.warning(
                "retrieval_failed mode=%s top_k=%d error=%s filters=%s",
                selected_mode,
                requested_top_k,
                type(exc).__name__,
                filter_fields,
            )
            raise
        except Exception as exc:
            logger.warning(
                "retrieval_failed mode=%s top_k=%d error=%s filters=%s",
                selected_mode,
                requested_top_k,
                type(exc).__name__,
                filter_fields,
            )
            raise RetrievalExecutionError(
                "The query could not be embedded safely."
            ) from exc
        embedding_duration_ms = (time.perf_counter() - embedding_started) * 1000

        database_started = time.perf_counter()
        try:
            if selected_mode == "semantic":
                results = self._semantic_results(
                    query_vector,
                    limit=requested_top_k,
                    search_filters=search_filters,
                    min_score=threshold,
                )
            else:
                results = self._hybrid_results(
                    normalized_query,
                    query_vector,
                    limit=requested_top_k,
                    search_filters=search_filters,
                    min_score=threshold,
                )
        except RetrievalError as exc:
            logger.warning(
                "retrieval_failed mode=%s top_k=%d error=%s filters=%s",
                selected_mode,
                requested_top_k,
                type(exc).__name__,
                filter_fields,
            )
            raise
        except Exception as exc:
            logger.warning(
                "retrieval_failed mode=%s top_k=%d error=%s filters=%s",
                selected_mode,
                requested_top_k,
                type(exc).__name__,
                filter_fields,
            )
            raise RetrievalExecutionError(
                "Retrieval failed safely; no results were returned."
            ) from exc
        database_duration_ms = (time.perf_counter() - database_started) * 1000
        total_duration_ms = (time.perf_counter() - started) * 1000

        response = RetrievalSearchResponse(
            query=normalized_query,
            mode=selected_mode,
            results=results,
            result_count=len(results),
        )
        logger.info(
            "retrieval_completed mode=%s top_k=%d returned=%d "
            "embedding_ms=%.1f database_ms=%.1f total_ms=%.1f "
            "filters=%s empty=%s",
            selected_mode,
            requested_top_k,
            len(results),
            embedding_duration_ms,
            database_duration_ms,
            total_duration_ms,
            filter_fields,
            not results,
        )
        return RetrievalOutcome(
            response=response,
            embedding_duration_ms=embedding_duration_ms,
            database_duration_ms=database_duration_ms,
            total_duration_ms=total_duration_ms,
        )

    # --- validation ------------------------------------------------------

    def _normalize_query(self, query: str) -> str:
        if not isinstance(query, str):
            raise RetrievalQueryError("query must be text.")
        cleaned = " ".join(query.split())
        if not cleaned:
            raise RetrievalQueryError(
                "query must not be empty or whitespace-only."
            )
        if len(cleaned) > self.settings.retrieval_max_query_chars:
            raise RetrievalQueryError(
                "query exceeds the "
                f"{self.settings.retrieval_max_query_chars} character limit."
            )
        return cleaned

    def _validate_top_k(self, top_k: int | None) -> int:
        requested = (
            self.settings.retrieval_default_top_k if top_k is None else top_k
        )
        if isinstance(requested, bool) or not isinstance(requested, int):
            raise RetrievalQueryError("top_k must be an integer.")
        if requested < 1:
            raise RetrievalQueryError("top_k must be at least 1.")
        if requested > self.settings.retrieval_max_top_k:
            raise RetrievalQueryError(
                "top_k exceeds the configured maximum of "
                f"{self.settings.retrieval_max_top_k}."
            )
        return requested

    @staticmethod
    def _validate_mode(mode: str) -> RetrievalMode:
        if mode not in _MODES:
            raise RetrievalQueryError(
                "mode must be either 'semantic' or 'hybrid'."
            )
        return cast(RetrievalMode, mode)

    @staticmethod
    def _validate_min_score(min_score: float | None) -> float | None:
        if min_score is None:
            return None
        if isinstance(min_score, bool) or not isinstance(
            min_score, (int, float)
        ):
            raise RetrievalQueryError("min_score must be numeric.")
        value = float(min_score)
        if not math.isfinite(value) or value < -1.0 or value > 1.0:
            raise RetrievalQueryError(
                "min_score must be a finite cosine similarity in [-1, 1]."
            )
        return value

    def _embed_query(self, query: str) -> list[float]:
        vectors = self.embedding_service.embed_texts([query])
        if len(vectors) != 1:
            raise RetrievalExecutionError(
                "The embedding service returned an unexpected number of "
                "query vectors."
            )
        vector = vectors[0]
        if not isinstance(vector, (list, tuple)):
            raise RetrievalExecutionError(
                "The embedding service returned a malformed query vector."
            )
        if len(vector) != self.settings.embedding_dimensions:
            raise RetrievalConfigurationError(
                "Query embedding dimension mismatch: the embedding service "
                f"returned {len(vector)} dimensions, but "
                f"EMBEDDING_DIMENSIONS is {self.settings.embedding_dimensions}."
            )
        numeric: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RetrievalExecutionError(
                    "The embedding service returned a malformed query vector."
                )
            number = float(value)
            if not math.isfinite(number):
                raise RetrievalExecutionError(
                    "The embedding service returned a non-finite query vector."
                )
            numeric.append(number)
        return numeric

    # --- semantic and hybrid ranking ------------------------------------

    def _semantic_results(
        self,
        query_vector: list[float],
        *,
        limit: int,
        search_filters: SearchFilters,
        min_score: float | None,
    ) -> list[RetrievalResult]:
        matches = self.store.search_semantic(
            query_vector,
            limit=limit,
            filters=search_filters,
            min_score=min_score,
        )
        return [
            _to_result(
                match.record,
                score=match.similarity,
                score_type="cosine_similarity",
                distance=match.distance,
                semantic_score=match.similarity,
            )
            for match in matches[:limit]
        ]

    def _hybrid_results(
        self,
        query: str,
        query_vector: list[float],
        *,
        limit: int,
        search_filters: SearchFilters,
        min_score: float | None,
    ) -> list[RetrievalResult]:
        candidate_limit = max(
            limit, self.settings.retrieval_hybrid_candidate_limit
        )
        semantic_matches = self.store.search_semantic(
            query_vector,
            limit=candidate_limit,
            filters=search_filters,
            min_score=min_score,
        )
        keyword_matches = self.store.search_keyword(
            query,
            limit=candidate_limit,
            filters=search_filters,
        )

        fused: dict[str, _FusedCandidate] = {}
        for rank, match in enumerate(semantic_matches, start=1):
            candidate = fused.setdefault(
                match.record.chunk_id, _FusedCandidate(record=match.record)
            )
            candidate.fused_score += 1.0 / (self.settings.retrieval_rrf_k + rank)
            candidate.semantic_distance = match.distance
            candidate.semantic_score = match.similarity
            candidate.semantic_rank = rank

        for match in keyword_matches:
            candidate = fused.setdefault(
                match.record.chunk_id, _FusedCandidate(record=match.record)
            )
            candidate.fused_score += 1.0 / (
                self.settings.retrieval_rrf_k + match.rank
            )
            candidate.keyword_rank = match.rank

        ordered = sorted(
            fused.values(),
            key=lambda item: (
                -item.fused_score,
                item.semantic_rank
                if item.semantic_rank is not None
                else float("inf"),
                item.keyword_rank
                if item.keyword_rank is not None
                else float("inf"),
                item.record.chunk_id,
            ),
        )
        return [
            _to_result(
                candidate.record,
                score=candidate.fused_score,
                score_type="reciprocal_rank_fusion",
                distance=candidate.semantic_distance,
                semantic_score=candidate.semantic_score,
                keyword_rank=candidate.keyword_rank,
            )
            for candidate in ordered[:limit]
        ]


def _to_search_filters(
    document_id: str | None, filters: RetrievalFilters | None
) -> SearchFilters:
    metadata_filters = filters or RetrievalFilters()
    return SearchFilters(
        document_id=document_id,
        source_filename=metadata_filters.source_filename,
        source_type=metadata_filters.source_type,
        page_number=metadata_filters.page_number,
    )


def _used_filter_fields(filters: SearchFilters) -> str:
    fields = [
        name
        for name in (
            "document_id",
            "source_filename",
            "source_type",
            "page_number",
        )
        if getattr(filters, name) is not None
    ]
    return ",".join(fields) if fields else "none"


def _to_result(
    record: ChunkRecord,
    *,
    score: float,
    score_type: ScoreType,
    distance: float | None = None,
    semantic_score: float | None = None,
    keyword_rank: int | None = None,
) -> RetrievalResult:
    metadata = record.chunk_metadata or {}
    raw_pages = metadata.get("page_numbers")
    page_numbers = (
        [int(page) for page in raw_pages if isinstance(page, int)]
        if isinstance(raw_pages, list)
        else []
    )
    return RetrievalResult(
        chunk_id=record.chunk_id,
        document_id=record.document_id,
        text=record.text,
        score=score,
        score_type=score_type,
        distance=distance,
        semantic_score=semantic_score,
        keyword_rank=keyword_rank,
        metadata=RetrievalResultMetadata(
            filename=record.source_filename,
            source_type=cast(SourceType, record.source_type),
            page_number=record.page_number,
            page_numbers=page_numbers,
            chunk_index=record.chunk_index,
            start_offset=record.start_offset,
            end_offset=record.end_offset,
            chunk_metadata=metadata,
        ),
    )
