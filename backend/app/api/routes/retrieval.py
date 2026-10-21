"""Retrieval endpoint. Validation, embedding, and SQL live in the service layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.schemas.retrieval import RetrievalSearchRequest, RetrievalSearchResponse
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_store import (
    RetrievalStore,
    create_retrieval_store,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


def get_settings_dep() -> Settings:
    return get_settings()


def get_embedding_service(
    settings: Settings = Depends(get_settings_dep),
) -> EmbeddingService:
    return EmbeddingService(settings)


def get_retrieval_store(
    settings: Settings = Depends(get_settings_dep),
) -> RetrievalStore:
    return create_retrieval_store(settings)


def get_retrieval_service(
    settings: Settings = Depends(get_settings_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    store: RetrievalStore = Depends(get_retrieval_store),
) -> RetrievalService:
    return RetrievalService(
        settings,
        embedding_service=embedding_service,
        store=store,
    )


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    summary="Retrieve stored document chunks relevant to a natural-language query",
    responses={
        422: {
            "description": (
                "Invalid query, top_k above the configured maximum, or "
                "unsupported filter/mode values."
            )
        },
        429: {"description": "Embedding provider rate limit exceeded."},
        500: {"description": "Safe retrieval/database failure."},
        502: {"description": "Embedding provider failed or returned invalid data."},
        503: {
            "description": (
                "Database or embedding configuration unavailable, missing "
                "migrations, or incompatible vector dimensions."
            )
        },
        504: {"description": "Embedding provider request timed out."},
    },
)
async def search_documents(
    payload: RetrievalSearchRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalSearchResponse:
    # Query embedding and synchronous SQL must not block the event loop.
    outcome = await run_in_threadpool(
        service.search,
        payload.query,
        top_k=payload.top_k,
        mode=payload.mode,
        document_id=payload.document_id,
        filters=payload.filters,
        min_score=payload.min_score,
    )
    return outcome.response
