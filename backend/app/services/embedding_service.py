"""Reusable embedding generation with pluggable providers (Phase 3).

Two providers are supported out of the box:

* ``fastembed`` (default): a local ONNX model, no API key or per-call cost.
* ``openai``: any OpenAI-compatible ``/embeddings`` endpoint.

All vectors are validated (non-empty, numeric, finite, expected dimension) and
L2-normalized before they are returned. Normalization makes cosine similarity
(and pgvector's ``vector_cosine_ops`` index) well-defined regardless of the
provider's raw output scale. Input order is always preserved.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Protocol, Sequence

from app.core.config import Settings, get_settings
from app.schemas.documents import DocumentChunk
from app.services.ingestion_errors import DocumentIngestionError


class EmbeddingError(DocumentIngestionError):
    """Base class for safe embedding failures."""

    status_code = 502


class EmbeddingConfigurationError(EmbeddingError):
    """The provider, credentials, or model configuration is unusable."""

    status_code = 503


class EmbeddingInputError(EmbeddingError):
    """A chunk text is empty or otherwise invalid."""

    status_code = 400


class EmbeddingProviderError(EmbeddingError):
    """The embedding provider failed or is unreachable."""

    status_code = 502


class EmbeddingRateLimitError(EmbeddingProviderError):
    status_code = 429


class EmbeddingTimeoutError(EmbeddingProviderError):
    status_code = 504


class EmbeddingResponseError(EmbeddingProviderError):
    """The provider returned a malformed, empty, or non-finite response."""


class EmbeddingDimensionMismatchError(EmbeddingConfigurationError):
    """Configured dimensions and returned/database dimensions differ."""


class EmbeddingProvider(Protocol):
    """Minimal provider interface, injectable for tests."""

    def embed(self, texts: list[str]) -> Sequence[Sequence[float]]: ...


@lru_cache(maxsize=4)
def _load_fastembed_model(
    model_name: str, cache_dir: str | None, threads: int | None
):
    """Load each local model once per process, not once per request."""
    from fastembed import TextEmbedding

    return TextEmbedding(
        model_name=model_name,
        cache_dir=cache_dir,
        threads=threads,
    )


class FastEmbedProvider:
    """Local ONNX embeddings via the optional ``fastembed`` dependency."""

    def __init__(
        self,
        model_name: str,
        cache_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threads = threads
        self._model: Any = None

    def _get_model(self):
        if self._model is None:
            try:
                self._model = _load_fastembed_model(
                    self.model_name, self.cache_dir, self.threads
                )
            except Exception as exc:
                raise EmbeddingProviderError(
                    "The local embedding model could not be loaded. Check that "
                    "the model name is supported and the model cache/network "
                    "is available."
                ) from exc
        return self._model

    def embed(self, texts: list[str]) -> Sequence[Sequence[float]]:
        model = self._get_model()
        try:
            return list(model.embed(texts))
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError(
                "The local embedding model failed to generate embeddings."
            ) from exc


class OpenAIEmbeddingProvider:
    """Synchronous OpenAI-compatible embeddings provider (no auto-retries)."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        if not self.settings.embedding_api_key or not (
            self.settings.embedding_api_key.strip()
        ):
            raise EmbeddingConfigurationError(
                "Embeddings are not configured: missing EMBEDDING_API_KEY. "
                "Set it, or use EMBEDDING_PROVIDER=fastembed."
            )
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        import openai

        self._client = openai.OpenAI(
            api_key=self.settings.embedding_api_key,
            base_url=self.settings.embedding_base_url,
            timeout=self.settings.embedding_timeout_seconds,
            max_retries=0,
        )
        return self._client

    def embed(self, texts: list[str]) -> Sequence[Sequence[float]]:
        import openai

        request: dict[str, Any] = {
            "model": self.settings.embedding_model,
            "input": texts,
        }
        if self.settings.embedding_model.startswith("text-embedding-3"):
            request["dimensions"] = self.settings.embedding_dimensions

        try:
            response = self._get_client().embeddings.create(**request)
        except openai.AuthenticationError as exc:
            raise EmbeddingConfigurationError(
                "The embedding provider rejected the configured credentials."
            ) from exc
        except openai.RateLimitError as exc:
            raise EmbeddingRateLimitError(
                "The embedding provider rate limit was exceeded. Retry later."
            ) from exc
        except (openai.APITimeoutError, TimeoutError) as exc:
            raise EmbeddingTimeoutError(
                "The embedding provider request timed out."
            ) from exc
        except openai.APIConnectionError as exc:
            raise EmbeddingProviderError(
                "The embedding provider is unreachable."
            ) from exc
        except openai.APIError as exc:
            raise EmbeddingProviderError(
                "The embedding provider returned an error."
            ) from exc
        except Exception as exc:
            raise EmbeddingProviderError(
                "Unexpected embedding provider failure."
            ) from exc

        items = list(getattr(response, "data", None) or [])
        if len(items) != len(texts):
            raise EmbeddingResponseError(
                "The embedding provider returned an unexpected number of vectors."
            )

        ordered: list[Sequence[float] | None] = [None] * len(texts)
        for item in items:
            try:
                index = int(item.index)
                vector = item.embedding
            except (AttributeError, TypeError, ValueError) as exc:
                raise EmbeddingResponseError(
                    "The embedding provider returned a malformed response."
                ) from exc
            if index < 0 or index >= len(ordered) or ordered[index] is not None:
                raise EmbeddingResponseError(
                    "The embedding provider returned invalid vector indexes."
                )
            ordered[index] = vector

        if any(vector is None for vector in ordered):
            raise EmbeddingResponseError(
                "The embedding provider returned an incomplete response."
            )
        return [vector for vector in ordered if vector is not None]


class EmbeddingService:
    """Validated, batched embedding generation with order preservation."""

    def __init__(
        self,
        settings: Settings | None = None,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if self.settings.embedding_dimensions <= 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_DIMENSIONS must be greater than zero."
            )
        self._provider = provider or self._build_provider()

    def _build_provider(self) -> EmbeddingProvider:
        provider = (self.settings.embedding_provider or "").strip().lower()
        if provider == "fastembed":
            return FastEmbedProvider(
                model_name=self.settings.embedding_model,
                cache_dir=self.settings.embedding_cache_dir,
            )
        if provider == "openai":
            return OpenAIEmbeddingProvider(self.settings)
        raise EmbeddingConfigurationError(
            "Unsupported embedding provider. Use 'fastembed' or 'openai'."
        )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in input order, batching provider calls."""
        if isinstance(texts, (str, bytes, bytearray)):
            raise EmbeddingInputError("Input must be a sequence of chunk texts.")
        items = list(texts)
        if not items:
            return []

        for index, value in enumerate(items):
            if not isinstance(value, str):
                raise EmbeddingInputError(
                    f"Chunk at position {index} is not text."
                )
            if not value.strip():
                raise EmbeddingInputError(
                    f"Chunk at position {index} is empty or whitespace-only."
                )

        batch_size = self.settings.embedding_batch_size
        results: list[list[float]] = []
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            try:
                raw_vectors = self._provider.embed(batch)
            except EmbeddingError:
                raise
            except Exception as exc:
                # A custom provider must not leak arbitrary internals.
                raise EmbeddingProviderError(
                    "Unexpected embedding provider failure."
                ) from exc
            results.extend(
                self._validate_batch(
                    raw_vectors,
                    expected_count=len(batch),
                    first_position=start,
                )
            )
        if len(results) != len(items):
            raise EmbeddingResponseError(
                "The embedding provider returned an incomplete set of vectors."
            )
        return results

    def embed_chunks(self, chunks: Sequence[DocumentChunk]) -> list[list[float]]:
        return self.embed_texts([chunk.text for chunk in chunks])

    def _validate_batch(
        self,
        raw_vectors: Sequence[Sequence[float]] | None,
        expected_count: int,
        first_position: int,
    ) -> list[list[float]]:
        if isinstance(raw_vectors, (str, bytes, bytearray)):
            raise EmbeddingResponseError(
                "The embedding provider returned a malformed response."
            )
        try:
            vectors = [] if raw_vectors is None else list(raw_vectors)
        except TypeError as exc:
            raise EmbeddingResponseError(
                "The embedding provider returned a malformed response."
            ) from exc

        if len(vectors) != expected_count:
            raise EmbeddingResponseError(
                "The embedding provider returned an unexpected number of vectors."
            )

        validated: list[list[float]] = []
        for offset, raw in enumerate(vectors):
            position = first_position + offset
            validated.append(
                self._normalize_vector(raw, position=position)
            )
        return validated

    def _normalize_vector(
        self, raw: Sequence[float], position: int
    ) -> list[float]:
        if isinstance(raw, (str, bytes, bytearray)) or raw is None:
            raise EmbeddingResponseError(
                f"Embedding at position {position} is not a vector."
            )
        try:
            values = list(raw)
        except TypeError as exc:
            raise EmbeddingResponseError(
                f"Embedding at position {position} is not a vector."
            ) from exc

        if not values:
            raise EmbeddingResponseError(
                f"Embedding at position {position} is empty."
            )
        if len(values) != self.settings.embedding_dimensions:
            raise EmbeddingDimensionMismatchError(
                "Embedding dimension mismatch: the model returned "
                f"{len(values)} dimensions at position {position}, but "
                f"EMBEDDING_DIMENSIONS is {self.settings.embedding_dimensions}."
            )

        numeric: list[float] = []
        for value in values:
            if isinstance(value, (str, bytes, bytearray, bool)):
                raise EmbeddingResponseError(
                    f"Embedding at position {position} contains a non-numeric value."
                )
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise EmbeddingResponseError(
                    f"Embedding at position {position} contains a non-numeric value."
                ) from exc
            if not math.isfinite(number):
                raise EmbeddingResponseError(
                    f"Embedding at position {position} contains a "
                    "non-finite value."
                )
            numeric.append(number)

        squared_norm = math.fsum(value * value for value in numeric)
        norm = math.sqrt(squared_norm)
        if norm == 0.0 or not math.isfinite(norm):
            raise EmbeddingResponseError(
                f"Embedding at position {position} has an invalid zero norm."
            )
        return [value / norm for value in numeric]
