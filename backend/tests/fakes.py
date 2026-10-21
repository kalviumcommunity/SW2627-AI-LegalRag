"""Deterministic, network-free test doubles for Phase 3."""

from __future__ import annotations

import hashlib
import math

from app.schemas.documents import IngestResponse
from app.services.ingestion_errors import DocumentIngestionError


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
