"""User registration, login, and profile authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER, get_client_ip
from app.db.models import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    AuthCredentialsError,
    AuthError,
    AuthRegistrationError,
    AuthService,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _check_auth_rate_limit(request: Request, settings: Settings) -> None:
    client_ip = get_client_ip(request)
    GLOBAL_RATE_LIMITER.check(
        key=f"auth:{client_ip}",
        max_requests=settings.rate_limit_auth_per_minute,
        window_seconds=60,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and receive a JWT access token",
    responses={
        201: {"description": "User created and access token issued."},
        400: {"description": "Validation error or invalid password format."},
        409: {"description": "Email is already registered."},
        429: {"description": "Too many registration attempts."},
        500: {"description": "Database write error."},
    },
)
async def register(
    request: Request,
    payload: UserRegisterRequest,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    _check_auth_rate_limit(request, settings)
    try:
        _, token_response = await run_in_threadpool(
            service.register, payload.email, payload.password
        )
        return token_response
    except AuthRegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from None
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from None


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password to receive a JWT access token",
    responses={
        200: {"description": "Successfully authenticated."},
        401: {"description": "Invalid email or password."},
        429: {"description": "Too many login attempts."},
        500: {"description": "Database error."},
    },
)
async def login(
    request: Request,
    payload: UserLoginRequest,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    _check_auth_rate_limit(request, settings)
    try:
        _, token_response = await run_in_threadpool(
            service.authenticate, payload.email, payload.password
        )
        return token_response
    except AuthCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from None
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from None


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve current authenticated user profile",
    responses={
        200: {"description": "Current user profile information."},
        401: {"description": "Missing, invalid, or expired authentication token."},
    },
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
