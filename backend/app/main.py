"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import documents, health, llm, retrieval
from app.core.config import get_settings
from app.services.ingestion_errors import DocumentIngestionError
from app.services.llm_service import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.services.retrieval_errors import RetrievalError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Property Intelligence Platform: health checks, a general (non-RAG) "
            "LLM chat endpoint, document ingestion/chunking, persistent "
            "PostgreSQL/pgvector storage, and Phase 4 semantic/hybrid retrieval "
            "with metadata filters. Answers are not generated from retrieved "
            "chunks yet."
        ),
        version="0.4.0",
    )

    # Map service errors raised in dependencies (e.g. missing API key at
    # service-construction time) to safe HTTP responses. The health endpoint
    # itself never constructs the LLM service, so it stays up regardless.
    async def _llm_config_handler(_: Request, exc: LLMConfigurationError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    async def _llm_rate_limit_handler(_: Request, exc: LLMRateLimitError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    async def _llm_timeout_handler(_: Request, exc: LLMTimeoutError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    async def _llm_provider_handler(
        _: Request, exc: LLMProviderError | LLMAuthenticationError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    async def _document_ingestion_handler(
        _: Request, exc: DocumentIngestionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )

    async def _retrieval_handler(
        _: Request, exc: RetrievalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )

    app.add_exception_handler(LLMConfigurationError, _llm_config_handler)
    app.add_exception_handler(LLMRateLimitError, _llm_rate_limit_handler)
    app.add_exception_handler(LLMTimeoutError, _llm_timeout_handler)
    app.add_exception_handler(LLMProviderError, _llm_provider_handler)
    app.add_exception_handler(LLMAuthenticationError, _llm_provider_handler)
    app.add_exception_handler(DocumentIngestionError, _document_ingestion_handler)
    app.add_exception_handler(RetrievalError, _retrieval_handler)

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(llm.router, prefix=settings.api_prefix)
    app.include_router(documents.router, prefix=settings.api_prefix)
    app.include_router(retrieval.router, prefix=settings.api_prefix)
    return app


app = create_app()
