"""Liveness and readiness endpoints. No paid LLM calls are made here."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


def get_settings_dep() -> Settings:
    return get_settings()


@router.get("/health", summary="Application liveness")
def health(settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready", summary="Application + LLM configuration readiness")
def ready(settings: Settings = Depends(get_settings_dep)) -> dict:
    configured = settings.is_llm_configured
    return {
        "status": "ok" if configured else "degraded",
        "service": settings.app_name,
        "llm_configured": configured,
        "llm_provider": settings.llm_provider,
    }
