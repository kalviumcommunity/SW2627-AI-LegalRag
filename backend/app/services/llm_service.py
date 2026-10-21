"""Reusable LLM service. Phase 1 uses Groq via its OpenAI-compatible API.

The integration uses the OpenAI SDK against Groq's endpoint, keeping the same
``chat`` interface so another provider can be added later.
"""

from __future__ import annotations

import openai

from app.core.config import Settings, get_settings
from app.core.prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Base class for safe, application-level LLM errors."""


class LLMConfigurationError(LLMError):
    """Raised when credentials or provider configuration are missing/invalid."""


class LLMAuthenticationError(LLMError):
    """Raised when the provider rejects the configured credentials."""


class LLMRateLimitError(LLMError):
    """Raised when the provider reports rate limiting."""


class LLMTimeoutError(LLMError):
    """Raised when the provider request times out."""


class LLMProviderError(LLMError):
    """Raised for other provider-side or unexpected failures."""


class LLMService:
    """Thin wrapper around Groq's OpenAI-compatible chat-completions API."""

    def __init__(self, settings: Settings | None = None, client=None) -> None:
        self.settings = settings or get_settings()
        provider = (self.settings.llm_provider or "").strip().lower()
        if provider != "groq":
            raise LLMConfigurationError(
                f"Unsupported LLM provider '{self.settings.llm_provider}'. "
                "Phase 1 supports 'groq'."
            )
        if not (self.settings.llm_model or "").strip():
            raise LLMConfigurationError("LLM model name is not configured.")
        if not self.settings.groq_api_key or not self.settings.groq_api_key.strip():
            raise LLMConfigurationError(
                "LLM is not configured: missing GROQ_API_KEY. "
                "Set it in the environment to enable chat."
            )
        # ``client`` is injectable so tests can pass a mock without network calls.
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        return openai.AsyncOpenAI(
            api_key=self.settings.groq_api_key,
            base_url=self.settings.groq_base_url,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,  # No automatic retries: avoids uncontrolled costs.
        )

    async def chat(self, message: str) -> str:
        """Send a user message to the provider and return the generated text."""
        cleaned = (message or "").strip()
        if not cleaned:
            raise ValueError("message must not be empty or whitespace-only")
        if len(message) > self.settings.llm_max_request_chars:
            raise ValueError(
                f"message exceeds the {self.settings.llm_max_request_chars} character limit"
            )

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": cleaned},
                ],
                max_completion_tokens=self.settings.llm_max_tokens,
                reasoning_effort=self.settings.llm_reasoning_effort,
            )
        except LLMError:
            raise
        except ValueError:
            raise
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError(
                "LLM provider authentication failed. Check server configuration."
            ) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(
                "LLM provider rate limit exceeded. Please retry later."
            ) from exc
        except (openai.APITimeoutError, TimeoutError) as exc:
            raise LLMTimeoutError("LLM provider request timed out.") from exc
        except openai.APIConnectionError as exc:
            raise LLMProviderError("LLM provider is unreachable.") from exc
        except openai.APIError as exc:
            raise LLMProviderError("LLM provider returned an error.") from exc
        except Exception as exc:  # Never leak provider internals to callers.
            raise LLMProviderError("Unexpected LLM provider failure.") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError) as exc:
            raise LLMProviderError("LLM provider returned an unexpected response.") from exc
        if not content or not content.strip():
            raise LLMProviderError("LLM provider returned an empty response.")
        return content.strip()
