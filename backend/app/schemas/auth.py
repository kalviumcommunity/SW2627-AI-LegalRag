"""Schemas for user registration, authentication, and JWT tokens."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserRegisterRequest(BaseModel):
    """Payload for registering a new user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="User email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters, maximum 128 characters).",
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address format.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(value) > 128:
            raise ValueError("Password cannot exceed 128 characters.")
        return value


class UserLoginRequest(BaseModel):
    """Payload for authenticating an existing user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    """Bearer access token returned on successful registration or login."""

    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field(default="bearer", description="Token type.")
    expires_in: int = Field(..., description="Expiration lifetime in seconds.")


class UserResponse(BaseModel):
    """Public user profile information."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User identifier.")
    email: str = Field(..., description="User email address.")
    is_active: bool = Field(..., description="Whether user account is active.")
    created_at: datetime = Field(..., description="Account creation timestamp.")
