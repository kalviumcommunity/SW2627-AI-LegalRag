"""Centralized application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are only read from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="property-intelligence-api")
    app_env: str = Field(default="development")
    api_prefix: str = Field(default="/api/v1")

    llm_provider: str = Field(default="groq")
    llm_model: str = Field(default="openai/gpt-oss-120b")
    groq_api_key: str | None = Field(default=None)
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")
    llm_reasoning_effort: str = Field(default="low")

    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_max_tokens: int = Field(default=1024, gt=0)
    llm_max_request_chars: int = Field(default=2000, gt=0)

    @property
    def is_llm_configured(self) -> bool:
        """True when the selected provider has the credentials it needs."""
        if self.llm_provider.strip().lower() == "groq":
            return bool(self.groq_api_key and self.groq_api_key.strip())
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
