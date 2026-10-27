"""Grounded RAG endpoint. Orchestration lives in the service layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.routes.retrieval import get_retrieval_service
from app.core.config import Settings, get_settings
from app.schemas.rag import RAGQuestionRequest, RAGResponse
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/rag", tags=["rag"])


def get_llm_service(
    settings: Settings = Depends(get_settings),
) -> LLMService:
    return LLMService(settings)


def get_rag_service(
    settings: Settings = Depends(get_settings),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> RAGService:
    return RAGService(
        settings,
        retrieval_service=retrieval_service,
        llm_service=llm_service,
    )


@router.post(
    "/ask",
    response_model=RAGResponse,
    summary="Grounded answer from retrieved document excerpts with citations",
    responses={
        422: {
            "description": (
                "Invalid question, top_k, filter, or retrieval mode; "
                "question above the configured limit."
            )
        },
        429: {"description": "Embedding or LLM provider rate limit exceeded."},
        500: {"description": "Safe RAG orchestration failure."},
        502: {
            "description": (
                "LLM provider failed or returned an unusable response; "
                "embedding provider failed."
            )
        },
        503: {
            "description": (
                "Database, retrieval, embedding, or LLM configuration "
                "unavailable."
            )
        },
        504: {"description": "Embedding or LLM provider request timed out."},
    },
)
async def ask_question(
    payload: RAGQuestionRequest,
    service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    return await service.ask(
        payload.question,
        top_k=payload.top_k,
        mode=payload.mode,
        document_id=payload.document_id,
        filters=payload.filters,
        min_score=payload.min_score,
    )
