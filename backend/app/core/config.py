"""Centralized application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, model_validator
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

    # --- Phase 2: document ingestion -------------------------------------
    # Character-based chunking is used deliberately: no tokenizer is assumed at
    # runtime. The defaults approximate 800 tokens / 120 tokens of overlap for
    # English text at roughly four characters per token.
    document_max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    document_allowed_extensions: str = Field(default="pdf,txt,md")
    document_chunk_size_chars: int = Field(default=3200, gt=0)
    document_chunk_overlap_chars: int = Field(default=480, ge=0)
    document_chunk_min_split_ratio: float = Field(default=0.5, gt=0, le=1)
    document_temp_dir: str | None = Field(default=None)

    @property
    def allowed_document_extensions(self) -> frozenset[str]:
        """Normalized, dot-free extensions allowed for ingestion."""
        values = {
            item.strip().lower().lstrip(".")
            for item in (self.document_allowed_extensions or "").split(",")
            if item.strip()
        }
        return frozenset(values)

    @model_validator(mode="after")
    def _validate_chunking(self) -> "Settings":
        if self.document_chunk_overlap_chars >= self.document_chunk_size_chars:
            raise ValueError(
                "DOCUMENT_CHUNK_OVERLAP_CHARS must be smaller than "
                "DOCUMENT_CHUNK_SIZE_CHARS"
            )
        return self

    @property
    def is_llm_configured(self) -> bool:
        """True when the selected provider has the credentials it needs."""
        if self.llm_provider.strip().lower() == "groq":
            return bool(self.groq_api_key and self.groq_api_key.strip())
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
