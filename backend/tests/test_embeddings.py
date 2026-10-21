"""Phase 3 embedding service tests. No network or paid API calls."""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import openai
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingService,
    EmbeddingTimeoutError,
    OpenAIEmbeddingProvider,
)
from tests.fakes import FakeEmbeddingProvider

FAKE_KEY = "test-key-not-a-secret"


def _settings(**overrides) -> Settings:
    values = {
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": 2,
        "embedding_batch_size": 2,
    }
    values.update(overrides)
    return Settings(**values)


def _service(provider, **overrides) -> EmbeddingService:
    return EmbeddingService(_settings(**overrides), provider=provider)


# --- Batching, order, normalization -----------------------------------------


def test_vectors_are_normalized_and_order_is_preserved():
    provider = FakeEmbeddingProvider(
        vectors=[[3.0, 4.0], [0.0, 5.0]]
    )
    vectors = _service(provider).embed_texts(["first chunk", "second chunk"])

    assert vectors == [[0.6, 0.8], [0.0, 1.0]]
    assert provider.calls == [["first chunk", "second chunk"]]


def test_large_inputs_are_split_into_configured_batches():
    provider = FakeEmbeddingProvider(dimensions=2)
    vectors = _service(provider, embedding_batch_size=2).embed_texts(
        ["a", "b", "c", "d", "e"]
    )

    assert [len(call) for call in provider.calls] == [2, 2, 1]
    assert len(vectors) == 5
    assert all(len(vector) == 2 for vector in vectors)
    assert all(
        math.isclose(sum(value * value for value in vector), 1.0)
        for vector in vectors
    )


def test_embed_chunks_preserves_chunk_order(monkeypatch):
    from app.schemas.documents import DocumentChunk

    chunks = [
        DocumentChunk(
            chunk_id=f"chk_{index}",
            document_id="doc_1",
            chunk_index=index,
            text=text,
            source_filename="notes.txt",
            source_type="txt",
            metadata={},
        )
        for index, text in enumerate(["alpha", "beta", "gamma"])
    ]
    provider = FakeEmbeddingProvider(dimensions=2)
    vectors = _service(provider, embedding_batch_size=10).embed_chunks(chunks)

    assert provider.calls == [["alpha", "beta", "gamma"]]
    assert len(vectors) == 3


def test_empty_input_returns_empty_without_provider_calls():
    provider = FakeEmbeddingProvider(dimensions=2)
    assert _service(provider).embed_texts([]) == []
    assert provider.calls == []


# --- Input validation --------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_blank_chunks_are_rejected(bad):
    provider = FakeEmbeddingProvider(dimensions=2)
    with pytest.raises(EmbeddingInputError):
        _service(provider).embed_texts([bad])
    assert provider.calls == []


def test_non_string_chunk_is_rejected():
    provider = FakeEmbeddingProvider(dimensions=2)
    with pytest.raises(EmbeddingInputError):
        _service(provider).embed_texts(["ok", 123])  # type: ignore[list-item]


def test_passing_a_bare_string_is_rejected():
    provider = FakeEmbeddingProvider(dimensions=2)
    with pytest.raises(EmbeddingInputError):
        _service(provider).embed_texts("one text")  # type: ignore[arg-type]


# --- Malformed / invalid provider output ------------------------------------


def test_provider_returning_too_few_vectors_is_rejected():
    provider = FakeEmbeddingProvider(vectors=[[1.0, 0.0]])
    with pytest.raises(EmbeddingResponseError):
        _service(provider).embed_texts(["one", "two"])


def test_empty_vector_is_rejected():
    provider = FakeEmbeddingProvider(vectors=[[]])
    with pytest.raises(EmbeddingResponseError):
        _service(provider).embed_texts(["one"])


def test_wrong_dimensions_are_rejected_as_configuration_error():
    provider = FakeEmbeddingProvider(vectors=[[1.0, 0.0, 0.0]])
    service = _service(provider, embedding_dimensions=2)
    with pytest.raises(EmbeddingDimensionMismatchError):
        service.embed_texts(["one"])


@pytest.mark.parametrize(
    "bad_vector",
    [
        [1.0, "not-a-number"],
        [1.0, None],
        [1.0, True],
        [float("nan"), 1.0],
        [float("inf"), 1.0],
        [0.0, 0.0],
    ],
)
def test_invalid_vector_values_are_rejected(bad_vector):
    provider = FakeEmbeddingProvider(vectors=[bad_vector])
    with pytest.raises(EmbeddingResponseError):
        _service(provider).embed_texts(["one"])


def test_non_sequence_provider_response_is_rejected():
    provider = Mock()
    provider.embed.return_value = 123
    with pytest.raises(EmbeddingResponseError):
        _service(provider).embed_texts(["one"])


# --- Provider failure and timeout behavior ----------------------------------


@pytest.mark.parametrize(
    "error",
    [
        EmbeddingProviderError("provider unavailable"),
        EmbeddingTimeoutError("provider timed out"),
        EmbeddingRateLimitError("provider rate limited"),
    ],
)
def test_provider_errors_propagate_unchanged(error):
    provider = FakeEmbeddingProvider(error=error)
    with pytest.raises(type(error), match=str(error)):
        _service(provider).embed_texts(["one"])


# --- OpenAI-compatible provider (mocked client) -----------------------------


def _openai_settings(**overrides) -> Settings:
    values = {
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 3,
        "embedding_api_key": FAKE_KEY,
        "embedding_batch_size": 10,
    }
    values.update(overrides)
    return Settings(**values)


def _fake_openai_client(data=None, error: Exception | None = None):
    embeddings = SimpleNamespace(
        create=Mock(
            side_effect=error
            if error is not None
            else None,
            return_value=SimpleNamespace(data=data)
            if error is None
            else None,
        )
    )
    return SimpleNamespace(embeddings=embeddings)


def test_openai_provider_sorts_vectors_by_response_index():
    data = [
        SimpleNamespace(index=1, embedding=[0.0, 3.0, 4.0]),
        SimpleNamespace(index=0, embedding=[3.0, 4.0, 0.0]),
    ]
    client = _fake_openai_client(data=data)
    provider = OpenAIEmbeddingProvider(_openai_settings(), client=client)
    vectors = EmbeddingService(_openai_settings(), provider=provider).embed_texts(
        ["first", "second"]
    )

    assert vectors == [[0.6, 0.8, 0.0], [0.0, 0.6, 0.8]]
    _, kwargs = client.embeddings.create.call_args
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["dimensions"] == 3
    assert kwargs["input"] == ["first", "second"]


def test_openai_provider_rejects_malformed_indexes():
    data = [
        SimpleNamespace(index=5, embedding=[1.0, 0.0, 0.0]),
    ]
    provider = OpenAIEmbeddingProvider(
        _openai_settings(), client=_fake_openai_client(data=data)
    )
    with pytest.raises(EmbeddingResponseError):
        EmbeddingService(_openai_settings(), provider=provider).embed_texts(["one"])


def test_openai_provider_requires_api_key():
    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingProvider(
            _openai_settings(embedding_api_key=None)
        )


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/embeddings")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            openai.AuthenticationError(
                "bad key",
                response=httpx.Response(401, request=_request()),
                body=None,
            ),
            EmbeddingConfigurationError,
        ),
        (
            openai.RateLimitError(
                "slow down",
                response=httpx.Response(429, request=_request()),
                body=None,
            ),
            EmbeddingRateLimitError,
        ),
        (openai.APITimeoutError(_request()), EmbeddingTimeoutError),
        (openai.APIConnectionError(request=_request()), EmbeddingProviderError),
        (
            openai.APIError("boom", request=_request(), body=None),
            EmbeddingProviderError,
        ),
        (RuntimeError("weird"), EmbeddingProviderError),
    ],
)
def test_openai_provider_maps_errors_without_leaking_details(error, expected):
    client = _fake_openai_client(error=error)
    provider = OpenAIEmbeddingProvider(_openai_settings(), client=client)
    with pytest.raises(expected) as raised:
        provider.embed(["one"])
    assert "weird" not in str(raised.value)
    assert "bad key" not in str(raised.value)


def test_invalid_embedding_provider_configuration_is_rejected():
    with pytest.raises(ValidationError):
        Settings(embedding_provider="unknown-provider")
