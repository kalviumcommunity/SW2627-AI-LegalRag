"""Tests for user authentication, password hashing, JWTs, and auth endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.services.auth_service import AuthService


from sqlalchemy.pool import StaticPool


@pytest.fixture
def auth_sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    yield engine
    engine.dispose()


@pytest.fixture
def auth_service(auth_sqlite_engine):
    settings = Settings(
        jwt_secret_key="test-secret-key-1234567890-test-key",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        rate_limit_auth_per_minute=5,
    )
    return AuthService(settings=settings, engine=auth_sqlite_engine)


@pytest.fixture
def auth_client(auth_service):
    app = create_app()
    # Remove the default test user override so we test real authentication
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: auth_service.settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_password_hashing_and_verification():
    raw_password = "SecurePassword123!"
    hashed = hash_password(raw_password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

    # Unique salts produce different hashes for the same password
    hashed_again = hash_password(raw_password)
    assert hashed != hashed_again
    assert verify_password(raw_password, hashed_again) is True


def test_jwt_token_lifecycle():
    secret = "my-secret-key-that-is-long-enough-32-chars"
    user_id = "usr_test_123"
    token = create_access_token(
        subject=user_id,
        secret_key=secret,
        algorithm="HS256",
        expires_delta=timedelta(minutes=15),
    )

    claims = decode_access_token(token, secret_key=secret, algorithm="HS256")
    assert claims["sub"] == user_id
    assert "exp" in claims
    assert "jti" in claims

    # Expired token raises TokenExpiredError
    expired_token = create_access_token(
        subject=user_id,
        secret_key=secret,
        algorithm="HS256",
        expires_delta=timedelta(minutes=-5),
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(expired_token, secret_key=secret, algorithm="HS256")

    # Invalid secret raises TokenInvalidError
    with pytest.raises(TokenInvalidError):
        decode_access_token(token, secret_key="wrong-secret", algorithm="HS256")


def test_register_success_returns_jwt_and_user(auth_client):
    response = auth_client.post(
        "/auth/register",
        json={"email": "agent@propertyintel.com", "password": "StrongPassword123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "agent@propertyintel.com"
    assert data["user"]["is_active"] is True
    assert data["user"]["id"].startswith("usr_")


def test_register_duplicate_email_fails(auth_client):
    payload = {"email": "duplicate@propertyintel.com", "password": "Password123!"}
    resp1 = auth_client.post("/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = auth_client.post("/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"].lower()


def test_register_validation_short_password(auth_client):
    response = auth_client.post(
        "/auth/register",
        json={"email": "short@propertyintel.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_success(auth_client):
    # Register user first
    auth_client.post(
        "/auth/register",
        json={"email": "analyst@propertyintel.com", "password": "Password123!"},
    )

    login_resp = auth_client.post(
        "/auth/login",
        json={"email": "analyst@propertyintel.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "analyst@propertyintel.com"


def test_login_invalid_password(auth_client):
    auth_client.post(
        "/auth/register",
        json={"email": "user1@propertyintel.com", "password": "CorrectPassword123!"},
    )

    login_resp = auth_client.post(
        "/auth/login",
        json={"email": "user1@propertyintel.com", "password": "WrongPassword123!"},
    )
    assert login_resp.status_code == 401
    assert "invalid email or password" in login_resp.json()["detail"].lower()


def test_login_nonexistent_user(auth_client):
    login_resp = auth_client.post(
        "/auth/login",
        json={"email": "nonexistent@propertyintel.com", "password": "AnyPassword123!"},
    )
    assert login_resp.status_code == 401
    assert "invalid email or password" in login_resp.json()["detail"].lower()


def test_auth_me_workflow(auth_client):
    # Unauthenticated
    resp_unauth = auth_client.get("/auth/me")
    assert resp_unauth.status_code == 401

    # Register & get token
    reg_resp = auth_client.post(
        "/auth/register",
        json={"email": "me@propertyintel.com", "password": "Password123!"},
    )
    token = reg_resp.json()["access_token"]

    # Authenticated
    resp_auth = auth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["email"] == "me@propertyintel.com"
    assert data["is_active"] is True


def test_rate_limiting_auth_endpoints(auth_client):
    GLOBAL_RATE_LIMITER.reset()
    # Setting limit is 5 per minute in auth_service fixture
    payload = {"email": "ratelimit@propertyintel.com", "password": "BadPassword123!"}
    
    responses = [auth_client.post("/auth/login", json=payload) for _ in range(7)]
    status_codes = [r.status_code for r in responses]

    assert 429 in status_codes
    ratelimited_resp = [r for r in responses if r.status_code == 429][0]
    assert "Retry-After" in ratelimited_resp.headers
    GLOBAL_RATE_LIMITER.reset()
