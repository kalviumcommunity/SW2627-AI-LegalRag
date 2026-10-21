"""Deterministic, network-free test doubles for ingestion and retrieval."""

from __future__ import annotations

import hashlib
import math

from app.schemas.documents import IngestResponse
from app.services.ingestion_errors import DocumentIngestionError
from app.services.retrieval_store import (
    ChunkRecord,
    KeywordMatch,
    SearchFilters,
    SemanticMatch,
)


class FakeEmbeddingProvider:
    """Deterministic provider: the same text always gets the same vector."""

    def __init__(
        self,
        dimensions: int = 8,
        error: Exception | None = None,
        vectors: list[list[float]] | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.error = error
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        if self.vectors is not None:
            return self.vectors
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            raw = [
                float(digest[index % len(digest)]) + 1.0
                for index in range(self.dimensions)
            ]
            norm = math.sqrt(sum(value * value for value in raw))
            vectors.append([value / norm for value in raw])
        return vectors


class FakeDocumentStore:
    """In-memory store used by Phase 2 API regression tests."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.records: dict[tuple[str, str], IngestResponse] = {}
        self.saved_embeddings: list[list[list[float]]] = []
        self.save_calls = 0

    def ensure_ready(self) -> None:
        if self.error is not None:
            raise self.error

    def find_by_content_hash(
        self, content_hash: str, filename: str
    ) -> IngestResponse | None:
        self.ensure_ready()
        stored = self.records.get((content_hash, filename))
        return stored.model_copy(deep=True) if stored is not None else None

    def save(
        self,
        response: IngestResponse,
        content_hash: str,
        embeddings: list[list[float]],
    ) -> IngestResponse:
        self.ensure_ready()
        self.save_calls += 1
        if len(embeddings) not in (0, len(response.chunks)):
            raise DocumentIngestionError("embedding count mismatch")
        key = (content_hash, response.filename)
        existing = self.records.get(key)
        if existing is not None:
            return existing.model_copy(deep=True)
        self.records[key] = response.model_copy(deep=True)
        self.saved_embeddings.append(embeddings)
        return response

class FakeRetrievalStore:
    """In-memory retrieval store for service/API unit tests."""

    def __init__(
        self,
        semantic_results: list[SemanticMatch] | None = None,
        keyword_results: list[KeywordMatch] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.semantic_results = list(semantic_results or [])
        self.keyword_results = list(keyword_results or [])
        self.error = error
        self.semantic_calls: list[dict] = []
        self.keyword_calls: list[dict] = []
        self.ensure_ready_calls = 0

    def ensure_ready(self) -> None:
        self.ensure_ready_calls += 1
        if self.error is not None:
            raise self.error

    def search_semantic(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float | None = None,
    ) -> list[SemanticMatch]:
        self.ensure_ready()
        self.semantic_calls.append(
            {
                "query_vector": list(query_vector),
                "limit": limit,
                "filters": filters,
                "min_score": min_score,
            }
        )
        return self.semantic_results[:limit]

    def search_keyword(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters,
    ) -> list[KeywordMatch]:
        self.ensure_ready()
        self.keyword_calls.append(
            {"query": query, "limit": limit, "filters": filters}
        )
        return self.keyword_results[:limit]


def chunk_record(
    chunk_id: str,
    *,
    document_id: str = "doc_1",
    text: str | None = None,
    filename: str = "deed.pdf",
    source_type: str = "pdf",
    page_number: int | None = 1,
    page_numbers: list[int] | None = None,
    chunk_index: int = 0,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        text=text or f"Chunk text for {chunk_id}.",
        source_filename=filename,
        source_type=source_type,
        page_number=page_number,
        start_offset=0,
        end_offset=10,
        chunk_metadata={
            "page_numbers": page_numbers if page_numbers is not None else (
                [page_number] if page_number is not None else []
            ),
            "character_count": 10,
        },
    )


def semantic_match(
    chunk_id: str,
    *,
    distance: float = 0.25,
    **record_kwargs,
) -> SemanticMatch:
    return SemanticMatch(
        record=chunk_record(chunk_id, **record_kwargs),
        distance=distance,
        similarity=1.0 - distance,
    )


def keyword_match(
    chunk_id: str,
    *,
    rank: int = 1,
    relevance: float = 0.5,
    **record_kwargs,
) -> KeywordMatch:
    return KeywordMatch(
        record=chunk_record(chunk_id, **record_kwargs),
        rank=rank,
        relevance=relevance,
    )
