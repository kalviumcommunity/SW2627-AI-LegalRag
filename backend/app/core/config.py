"""Centralized application configuration loaded from environment variables."""

from functools import lru_cache
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str | None, direct: bool = False) -> str | None:
    """Normalize a database connection URL for SQLAlchemy + psycopg (v3).

    - Converts 'postgres://', 'postgresql://', or 'postgresql+psycopg2://'
      to 'postgresql+psycopg://'.
    - If direct=True and hostname contains '-pooler' (Neon connection pooler),
      strips '-pooler' so migrations/DDL bypass transaction-mode PgBouncer.
    - Ensures 'sslmode=require' is present for Neon/remote databases.
    - Preserves existing credentials without exposing or logging them.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        return None

    parts = urlsplit(cleaned)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
        scheme = "postgresql+psycopg"

    hostname = parts.hostname or ""
    netloc = parts.netloc

    # Strip -pooler for direct connection if requested (e.g. for Alembic migrations)
    if direct and "-pooler" in hostname:
        direct_host = hostname.replace("-pooler", "")
        netloc = netloc.replace(hostname, direct_host)

    # Ensure sslmode=require for Neon endpoints if not already in query
    query = parts.query
    params = parse_qs(query)
    if "sslmode" not in params and (hostname.endswith("neon.tech") or "neon.tech" in hostname):
        params["sslmode"] = ["require"]
        query = urlencode(params, doseq=True)

    return urlunsplit((scheme, netloc, parts.path, query, parts.fragment))


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

    # PostgreSQL + pgvector connection string (Neon or self-hosted).
    # Normal traffic can use the pooled connection, while migrations
    # use direct connections.
    database_url: str | None = Field(default=None)
    direct_database_url: str | None = Field(default=None)
    database_echo: bool = Field(default=False)
    database_pool_size: int = Field(default=5, gt=0)
    database_connect_timeout_seconds: int = Field(default=10, ge=1)

    # ``fastembed`` runs a local ONNX model (no API key, no per-call cost).
    # ``openai`` calls an OpenAI-compatible embeddings endpoint.
    embedding_provider: str = Field(default="fastembed")
    embedding_model: str = Field(default="nomic-ai/nomic-embed-text-v1.5-Q")
    embedding_dimensions: int = Field(default=768, gt=0)
    embedding_batch_size: int = Field(default=32, gt=0)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_api_key: str | None = Field(default=None)
    embedding_base_url: str = Field(default="https://api.openai.com/v1")
    embedding_cache_dir: str | None = Field(default=None)

    # --- Phase 4: retrieval ----------------------------------------------
    retrieval_default_top_k: int = Field(default=5, ge=1)
    retrieval_max_top_k: int = Field(default=50, ge=1)
    retrieval_max_query_chars: int = Field(default=2000, gt=0)
    # Candidate pool per retriever before reciprocal rank fusion. The service
    # clamps this to at least the requested ``top_k``.
    retrieval_hybrid_candidate_limit: int = Field(default=50, ge=1)
    # RRF's rank-smoothing constant (the standard value is 60).
    retrieval_rrf_k: int = Field(default=60, gt=0)

    # --- Phase 5: grounded RAG --------------------------------------------
    # The context budget is a conservative estimate, not a tokenizer-exact
    # count. Output tokens are reserved separately so evidence cannot crowd
    # out the answer.
    rag_max_question_chars: int = Field(default=2000, gt=0)
    rag_context_max_tokens: int = Field(default=4000, gt=0)
    rag_max_output_tokens: int = Field(default=1024, gt=0)
    rag_max_evidence_chunks: int = Field(default=8, ge=1)
    rag_max_evidence_chars: int = Field(default=8000, gt=0)
    rag_max_evidence_chunk_chars: int = Field(default=1600, ge=50)
    rag_max_excerpt_chars: int = Field(default=280, ge=20)
    rag_max_answer_chars: int = Field(default=6000, ge=100)
    # Conservative tokenizer abstraction: estimated_tokens =
    # ceil(chars / chars_per_token * safety_factor).
    rag_chars_per_token: float = Field(default=4.0, gt=0)
    rag_token_safety_factor: float = Field(default=1.2, ge=1.0)
    # Weak-evidence policy. This is a floor, not proof of sufficiency: a score
    # above the floor still requires model grounding and citation validation.
    # Set to None to disable the semantic floor explicitly.
    rag_min_semantic_score: float | None = Field(default=0.35, ge=-1.0, le=1.0)
    # Hybrid keyword-only results have no comparable cosine score. Keep only
    # reasonably ranked keyword matches under this policy.
    rag_max_keyword_only_rank: int = Field(default=20, ge=1)
    # Overlap-aware context deduplication: omit a same-document chunk when this
    # fraction of the shorter chunk's character range is already covered.
    rag_overlap_dedup_ratio: float = Field(default=0.5, gt=0.0, le=1.0)
    # The provider/model context window used for a conservative prompt + output
    # fit check. This is deliberately separate from the prompt budget.
    rag_model_context_tokens: int = Field(default=32768, gt=0)

    # --- Phase 8: authentication & authorization --------------------------
    jwt_secret_key: str = Field(
        default="property-intel-dev-jwt-secret-key-change-in-production-min32chars"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, gt=0)
    rate_limit_auth_per_minute: int = Field(default=15, gt=0)
    rate_limit_upload_per_minute: int = Field(default=20, gt=0)
    rate_limit_rag_per_minute: int = Field(default=30, gt=0)
    cors_origins: str = Field(default="*")

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

    @model_validator(mode="after")
    def _validate_embedding(self) -> "Settings":
        provider = (self.embedding_provider or "").strip().lower()
        if provider not in {"fastembed", "openai"}:
            raise ValueError(
                "EMBEDDING_PROVIDER must be 'fastembed' or 'openai'"
            )
        if not (self.embedding_model or "").strip():
            raise ValueError("EMBEDDING_MODEL must not be empty")
        return self

    @model_validator(mode="after")
    def _validate_retrieval(self) -> "Settings":
        if self.retrieval_default_top_k > self.retrieval_max_top_k:
            raise ValueError(
                "RETRIEVAL_DEFAULT_TOP_K must not exceed RETRIEVAL_MAX_TOP_K"
            )
        return self

    @model_validator(mode="after")
    def _validate_rag(self) -> "Settings":
        if self.rag_max_excerpt_chars > self.rag_max_evidence_chars:
            raise ValueError(
                "RAG_MAX_EXCERPT_CHARS must not exceed RAG_MAX_EVIDENCE_CHARS"
            )
        if self.rag_max_evidence_chunk_chars > self.rag_max_evidence_chars:
            raise ValueError(
                "RAG_MAX_EVIDENCE_CHUNK_CHARS must not exceed "
                "RAG_MAX_EVIDENCE_CHARS"
            )
        if (
            self.rag_context_max_tokens + self.rag_max_output_tokens
            > self.rag_model_context_tokens
        ):
            raise ValueError(
                "RAG_CONTEXT_MAX_TOKENS plus RAG_MAX_OUTPUT_TOKENS must not "
                "exceed RAG_MODEL_CONTEXT_TOKENS"
            )
        return self

    @property
    def is_llm_configured(self) -> bool:
        """True when the selected provider has the credentials it needs."""
        if self.llm_provider.strip().lower() == "groq":
            return bool(self.groq_api_key and self.groq_api_key.strip())
        return False

    def get_database_url(self, direct: bool = False) -> str | None:
        """Return the normalized connection URL for application or migration use.

        - direct=False: Returns normalized application URL (using Neon pooler if configured).
        - direct=True: Returns normalized direct connection (stripping '-pooler' or using direct_database_url).
        """
        if direct and self.direct_database_url and self.direct_database_url.strip():
            return normalize_database_url(self.direct_database_url, direct=True)
        return normalize_database_url(self.database_url, direct=direct)

    @property
    def is_database_configured(self) -> bool:
        return bool(self.get_database_url())

    @property
    def is_embedding_configured(self) -> bool:
        provider = (self.embedding_provider or "").strip().lower()
        if provider == "fastembed":
            return True
        if provider == "openai":
            return bool(self.embedding_api_key and self.embedding_api_key.strip())
        return False

    @property
    def is_retrieval_configured(self) -> bool:
        """Retrieval needs both a vector database and an embedding provider."""
        return self.is_database_configured and self.is_embedding_configured

    @property
    def is_rag_configured(self) -> bool:
        """Grounded generation needs retrieval plus a configured LLM."""
        return self.is_retrieval_configured and self.is_llm_configured


@lru_cache
def get_settings() -> Settings:
    return Settings()
