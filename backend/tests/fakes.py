"""Deterministic, network-free test doubles for ingestion and retrieval."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime

from app.schemas.documents import (
    DocumentChunkSummary,
    DocumentDetailResponse,
    DocumentSummary,
    IngestResponse,
)
from app.schemas.retrieval import (
    RetrievalResult,
    RetrievalResultMetadata,
    RetrievalSearchResponse,
    ScoreType,
)
from app.services.ingestion_errors import DocumentIngestionError
from app.services.retrieval_service import RetrievalOutcome
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
    """In-memory store used by API regression and document management tests."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.records: dict[tuple[str, str], IngestResponse] = {}
        self.by_id: dict[str, IngestResponse] = {}
        self.content_hashes: dict[str, str] = {}
        self.created_at: dict[str, datetime] = {}
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
        copied = response.model_copy(deep=True)
        now = datetime.now()
        self.records[key] = copied
        self.by_id[response.document_id] = copied
        self.content_hashes[response.document_id] = content_hash
        self.created_at[response.document_id] = now
        self.saved_embeddings.append(embeddings)
        return response

    def get_document(self, document_id: str) -> DocumentDetailResponse | None:
        self.ensure_ready()
        stored = self.by_id.get(document_id)
        if stored is None:
            return None
        source_type = stored.chunks[0].source_type if stored.chunks else (
            "pdf" if stored.filename.lower().endswith(".pdf") else (
                "markdown" if stored.filename.lower().endswith(".md") else "txt"
            )
        )
        return DocumentDetailResponse(
            document_id=stored.document_id,
            filename=stored.filename,
            source_type=source_type,
            status=stored.status,
            content_sha256=self.content_hashes.get(document_id, "0" * 64),
            extracted_characters=stored.extracted_characters,
            chunk_count=stored.chunk_count,
            page_count=stored.page_count,
            warnings=list(stored.warnings),
            detail=stored.detail,
            created_at=self.created_at.get(document_id),
            updated_at=self.created_at.get(document_id),
        )

    def list_documents(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        self.ensure_ready()
        docs = list(self.by_id.values())
        filtered = []
        for doc in docs:
            doc_source_type = doc.chunks[0].source_type if doc.chunks else (
                "pdf" if doc.filename.lower().endswith(".pdf") else (
                    "markdown" if doc.filename.lower().endswith(".md") else "txt"
                )
            )
            if status is not None and doc.status != status:
                continue
            if source_type is not None and doc_source_type != source_type:
                continue
            filtered.append(
                DocumentSummary(
                    document_id=doc.document_id,
                    filename=doc.filename,
                    source_type=doc_source_type,
                    status=doc.status,
                    extracted_characters=doc.extracted_characters,
                    chunk_count=doc.chunk_count,
                    page_count=doc.page_count,
                    warnings=list(doc.warnings),
                    detail=doc.detail,
                    created_at=self.created_at.get(doc.document_id),
                    updated_at=self.created_at.get(doc.document_id),
                )
            )
        total = len(filtered)
        return filtered[offset : offset + limit], total

    def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        include_text: bool = False,
    ) -> tuple[list[DocumentChunkSummary], int] | None:
        self.ensure_ready()
        stored = self.by_id.get(document_id)
        if stored is None:
            return None
        total = len(stored.chunks)
        paged_chunks = stored.chunks[offset : offset + limit]
        items = [
            DocumentChunkSummary(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                source_filename=chunk.source_filename,
                source_type=chunk.source_type,
                page_number=chunk.page_number,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                metadata=dict(chunk.metadata),
                text=chunk.text if include_text else None,
            )
            for chunk in paged_chunks
        ]
        return items, total

    def delete_document(self, document_id: str) -> bool:
        self.ensure_ready()
        stored = self.by_id.pop(document_id, None)
        if stored is None:
            return False
        content_hash = self.content_hashes.pop(document_id, None)
        if content_hash:
            self.records.pop((content_hash, stored.filename), None)
        self.created_at.pop(document_id, None)
        return True

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


class FakeRetrievalService:
    """Synchronous retrieval double for RAG orchestration tests."""

    def __init__(
        self,
        results: list[RetrievalResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results or [])
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def search(self, query: str, **kwargs) -> RetrievalOutcome:
        self.calls.append((query, kwargs))
        if self.error is not None:
            raise self.error
        mode = kwargs.get("mode", "semantic")
        return RetrievalOutcome(
            response=RetrievalSearchResponse(
                query=query,
                mode=mode,
                results=self.results,
                result_count=len(self.results),
            ),
            embedding_duration_ms=0.0,
            database_duration_ms=0.0,
            total_duration_ms=0.0,
        )


class FakeLLMService:
    """Async LLM double that records prompts and returns canned content."""

    def __init__(
        self,
        response: str = "{}",
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    async def generate(self, **kwargs) -> str:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


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
    start_offset: int = 0,
    end_offset: int = 10,
    document_created_at: datetime | None = None,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        text=text or f"Chunk text for {chunk_id}.",
        source_filename=filename,
        source_type=source_type,
        page_number=page_number,
        start_offset=start_offset,
        end_offset=end_offset,
        chunk_metadata={
            "page_numbers": page_numbers if page_numbers is not None else (
                [page_number] if page_number is not None else []
            ),
            "character_count": end_offset - start_offset,
        },
        document_created_at=document_created_at,
    )


def retrieval_result(
    chunk_id: str,
    *,
    score: float = 0.9,
    score_type: ScoreType = "cosine_similarity",
    semantic_score: float | None = None,
    keyword_rank: int | None = None,
    **record_kwargs,
) -> RetrievalResult:
    record = chunk_record(chunk_id, **record_kwargs)
    pages = record.chunk_metadata.get("page_numbers") or []
    resolved_semantic_score = (
        score if semantic_score is None and score_type == "cosine_similarity"
        else semantic_score
    )
    return RetrievalResult(
        chunk_id=record.chunk_id,
        document_id=record.document_id,
        text=record.text,
        score=score,
        score_type=score_type,
        distance=(
            1.0 - resolved_semantic_score
            if resolved_semantic_score is not None
            else None
        ),
        semantic_score=resolved_semantic_score,
        keyword_rank=keyword_rank,
        metadata=RetrievalResultMetadata(
            filename=record.source_filename,
            source_type=record.source_type,
            page_number=record.page_number,
            page_numbers=list(pages),
            chunk_index=record.chunk_index,
            start_offset=record.start_offset,
            end_offset=record.end_offset,
            chunk_metadata=record.chunk_metadata,
            document_created_at=record.document_created_at,
        ),
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
