"""Chat endpoint. Thin layer over :class:`LLMService` with safe error mapping."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.llm import ChatRequest, ChatResponse
from app.services.llm_service import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMService,
    LLMTimeoutError,
)

router = APIRouter(prefix="/llm", tags=["llm"])

# Starlette renamed 422 in newer versions; fall back for older installs.
STATUS_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def get_settings_dep() -> Settings:
    return get_settings()


def get_llm_service(settings: Settings = Depends(get_settings_dep)) -> LLMService:
    # Construction validates credentials; app-level exception handlers map
    # LLMConfigurationError to 503 so startup/health are unaffected.
    return LLMService(settings)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the property-intelligence assistant (general answers only in Phase 1)",
    responses={
        422: {"description": "Invalid request (empty message or over length limit)"},
        429: {"description": "Provider rate limit exceeded"},
        502: {"description": "Provider authentication or upstream failure"},
        503: {"description": "LLM not configured (missing API key)"},
        504: {"description": "Provider request timed out"},
    },
)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings_dep),
    service: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    message = payload.message.strip()
    if len(payload.message) > settings.llm_max_request_chars:
        raise HTTPException(
            status_code=STATUS_UNPROCESSABLE,
            detail=f"message exceeds the {settings.llm_max_request_chars} character limit",
        )
    try:
        answer = await service.chat(message)
    except ValueError as exc:
        raise HTTPException(
            status_code=STATUS_UNPROCESSABLE, detail=str(exc)
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LLMRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        ) from exc
    except (LLMAuthenticationError, LLMProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive, never leak internals
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider returned an error.",
        ) from exc
    return ChatResponse(answer=answer)
