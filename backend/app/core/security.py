"""Cryptographic utilities: Argon2 password hashing and short-lived JWT access tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

# Argon2id password hasher with secure defaults
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


class SecurityError(Exception):
    """Base class for security and authentication exceptions."""


class TokenError(SecurityError):
    """Base class for JWT errors."""


class TokenExpiredError(TokenError):
    """Raised when an access token has expired."""


class TokenInvalidError(TokenError):
    """Raised when an access token signature or format is invalid."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.
    
    Never stores plaintext passwords or returns plain text.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    if len(password) > 128:
        raise ValueError("Password exceeds maximum allowed length.")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.
    
    Returns False safely on any mismatch, corruption, or invalid hash format.
    """
    if not plain_password or not hashed_password:
        return False
    if len(plain_password) > 128:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


def create_access_token(
    payload: dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a signed JWT access token with an explicit expiration timestamp."""
    if not secret_key:
        raise SecurityError("JWT secret key must be configured.")
    to_encode = dict(payload)
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=60))
    to_encode.update({
        "iat": now,
        "nbf": now,
        "exp": expire,
    })
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any]:
    """Decode and verify signature and expiry of a JWT access token.
    
    Raises TokenExpiredError on expired tokens, TokenInvalidError on invalid tokens.
    """
    if not token or not secret_key:
        raise TokenInvalidError("Token and secret key must be provided.")
    try:
        return jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"require": ["exp", "sub", "iat"]},
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired.") from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError("Invalid authentication token.") from exc
    except Exception as exc:
        raise TokenInvalidError("Failed to decode token.") from exc
