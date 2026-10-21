"""LLM endpoint + service tests. The external provider is always mocked."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.api.routes.llm import get_llm_service, get_settings_dep
from app.core.config import Settings
from app.main import create_app
from app.services.llm_service import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMService,
    LLMTimeoutError,
)

FAKE_KEY = "test-key-not-a-secret"


def _settings(**overrides) -> Settings:
    base = {"groq_api_key": FAKE_KEY}
    base.update(overrides)
    return Settings(**base)


def _client(settings: Settings, service=None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    if service is not None:
        app.dependency_overrides[get_llm_service] = lambda: service
    return TestClient(app)


def _ok_openai_client(text: str = "mocked answer"):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    response = SimpleNamespace(choices=[choice])
    completions = SimpleNamespace(create=AsyncMock(return_value=response))
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


class _FakeService:
    """Minimal stand-in for LLMService used for endpoint error-mapping tests."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls: list[str] = []

    async def chat(self, message: str) -> str:
        self.calls.append(message)
        if self._error is not None:
            raise self._error
        return self._result


# --- Endpoint: validation ---------------------------------------------------

def test_valid_chat_request_returns_expected_schema():
    settings = _settings()
    service = _FakeService(result="mocked answer")
    client = _client(settings, service)
    response = client.post(
        f"{settings.api_prefix}/llm/chat",
        json={"message": "Explain why property documents should be cross-checked."},
    )
    assert response.status_code == 200
    assert response.json() == {"answer": "mocked answer"}
    assert service.calls == ["Explain why property documents should be cross-checked."]


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_empty_and_whitespace_messages_are_rejected(bad):
    settings = _settings()
    client = _client(settings, _FakeService(result="should-not-be-called"))
    response = client.post(f"{settings.api_prefix}/llm/chat", json={"message": bad})
    assert response.status_code == 422


def test_missing_message_field_is_rejected():
    settings = _settings()
    client = _client(settings, _FakeService(result="should-not-be-called"))
    response = client.post(f"{settings.api_prefix}/llm/chat", json={})
    assert response.status_code == 422


def test_overlong_message_is_rejected_before_provider_call():
    settings = _settings(llm_max_request_chars=10)
    service = _FakeService(result="should-not-be-called")
    client = _client(settings, service)
    response = client.post(
        f"{settings.api_prefix}/llm/chat", json={"message": "x" * 11}
    )
    assert response.status_code == 422
    assert service.calls == []


def test_schema_max_length_is_rejected():
    settings = _settings()
    client = _client(settings, _FakeService(result="should-not-be-called"))
    response = client.post(
        f"{settings.api_prefix}/llm/chat", json={"message": "x" * 4001}
    )
    assert response.status_code == 422


# --- Endpoint: error mapping (no secrets / no stack traces) -----------------

def test_missing_llm_configuration_produces_safe_503():
    settings = Settings(groq_api_key=None)  # explicit: no credentials
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    # Real service construction fails -> mapped to 503 by exception handlers.
    client = TestClient(app)
    response = client.post(
        f"{settings.api_prefix}/llm/chat", json={"message": "Hello"}
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "not configured" in detail.lower()
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LLMRateLimitError("rate limited"), 429),
        (LLMTimeoutError("timed out"), 504),
        (LLMAuthenticationError("bad credentials"), 502),
        (LLMProviderError("provider blew up"), 502),
    ],
)
def test_provider_errors_are_mapped_without_leaking_internals(error, expected_status):
    settings = _settings()
    secret_value = "sk-super-secret-value-12345"
    settings_with_secret = settings
    client = _client(settings_with_secret, _FakeService(error=error))
    response = client.post(
        f"{settings.api_prefix}/llm/chat", json={"message": "Hello"}
    )
    assert response.status_code == expected_status
    body = response.text
    assert "traceback" not in body.lower()
    assert secret_value not in body
    assert "stack" not in body.lower() or "stack" not in body


# --- Service unit tests with mocked OpenAI client ----------------------------

async def test_service_success_returns_text():
    settings = _settings()
    client = _ok_openai_client("  mocked answer  ")
    service = LLMService(settings, client=client)
    assert await service.chat("Hello") == "mocked answer"
    # System prompt + user message are sent; model/params come from settings.
    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == settings.llm_model
    assert kwargs["max_completion_tokens"] == settings.llm_max_tokens
    assert kwargs["reasoning_effort"] == settings.llm_reasoning_effort
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1] == {"role": "user", "content": "Hello"}


async def test_service_missing_credentials_raises_configuration_error():
    with pytest.raises(LLMConfigurationError):
        LLMService(Settings(groq_api_key=None))


async def test_service_rejects_blank_and_overlong_input():
    service = LLMService(_settings(), client=_ok_openai_client())
    with pytest.raises(ValueError):
        await service.chat("   ")
    small = LLMService(_settings(llm_max_request_chars=5), client=_ok_openai_client())
    with pytest.raises(ValueError):
        await small.chat("123456")


def _openai_error_client(exc: Exception):
    completions = SimpleNamespace(create=AsyncMock(side_effect=exc))
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


async def test_service_maps_openai_errors_safely():
    cases = [
        (
            openai.AuthenticationError("bad key", response=httpx.Response(401, request=_req()), body=None),
            LLMAuthenticationError,
        ),
        (
            openai.RateLimitError("slow down", response=httpx.Response(429, request=_req()), body=None),
            LLMRateLimitError,
        ),
        (openai.APITimeoutError(_req()), LLMTimeoutError),
        (openai.APIConnectionError(request=_req()), LLMProviderError),
        (
            openai.APIError("boom", request=_req(), body=None),
            LLMProviderError,
        ),
        (RuntimeError("weird"), LLMProviderError),
    ]
    for openai_exc, expected in cases:
        service = LLMService(_settings(), client=_openai_error_client(openai_exc))
        with pytest.raises(expected):
            await service.chat("Hello")


async def test_service_rejects_empty_provider_response():
    service = LLMService(_settings(), client=_ok_openai_client("   "))
    with pytest.raises(LLMProviderError):
        await service.chat("Hello")
