"""User authentication, registration, password hashing, and token issuance service."""

from __future__ import annotations

import secrets
import threading
from datetime import timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import TokenResponse, UserResponse
from app.services.document_store import get_shared_engine
from app.services.storage_errors import DatabaseUnavailableError


class AuthError(Exception):
    """Base class for authentication errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthRegistrationError(AuthError):
    """Raised when user registration fails due to duplicate email or invalid state."""

    def __init__(self, message: str = "Email is already registered.") -> None:
        super().__init__(message, status_code=409)


class AuthCredentialsError(AuthError):
    """Raised on invalid email or password."""

    def __init__(self, message: str = "Invalid email or password.") -> None:
        super().__init__(message, status_code=401)


class AuthService:
    """Manages user registration, credential verification, and JWT session tokens."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: Engine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._engine = engine
        self._session_factory: sessionmaker[Session] | None = None
        self._lock = threading.RLock()

    def _get_engine(self) -> Engine:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = get_shared_engine(self.settings)
        return self._engine

    def _get_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            with self._lock:
                if self._session_factory is None:
                    self._session_factory = sessionmaker(
                        bind=self._get_engine(),
                        expire_on_commit=False,
                    )
        return self._session_factory

    def register(self, email: str, password: str) -> tuple[User, TokenResponse]:
        """Register a new user, hash the password, and return user with access token."""
        normalized_email = email.strip().lower()
        hashed = hash_password(password)
        user_id = f"usr_{secrets.token_hex(16)}"

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    existing = session.execute(
                        select(User).where(User.email == normalized_email)
                    ).scalar_one_or_none()
                    if existing is not None:
                        raise AuthRegistrationError("Email is already registered.")

                    user = User(
                        id=user_id,
                        email=normalized_email,
                        hashed_password=hashed,
                        is_active=True,
                    )
                    session.add(user)

            token_response = self.create_token(user_id=user.id, email=user.email)
            return user, token_response

        except IntegrityError as exc:
            raise AuthRegistrationError("Email is already registered.") from exc
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except (AuthError, DatabaseUnavailableError):
            raise
        except SQLAlchemyError as exc:
            raise AuthError("Failed to register user due to database error.", 500) from exc

    def authenticate(self, email: str, password: str) -> tuple[User, TokenResponse]:
        """Authenticate user credentials and issue a new JWT access token."""
        normalized_email = email.strip().lower()

        try:
            with self._get_session_factory()() as session:
                user = session.execute(
                    select(User).where(User.email == normalized_email)
                ).scalar_one_or_none()

                if user is None or not user.is_active:
                    raise AuthCredentialsError("Invalid email or password.")

                if not verify_password(password, user.hashed_password):
                    raise AuthCredentialsError("Invalid email or password.")

            token_response = self.create_token(user_id=user.id, email=user.email)
            return user, token_response

        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except (AuthError, DatabaseUnavailableError):
            raise
        except SQLAlchemyError as exc:
            raise AuthError("Failed to authenticate user due to database error.", 500) from exc

    def get_user_by_id(self, user_id: str) -> User | None:
        """Fetch a user record by ID."""
        try:
            with self._get_session_factory()() as session:
                return session.execute(
                    select(User).where(User.id == user_id)
                ).scalar_one_or_none()
        except Exception:
            return None

    def create_token(self, user_id: str, email: str) -> TokenResponse:
        """Generate a short-lived signed JWT access token for the given user."""
        expires_minutes = self.settings.access_token_expire_minutes
        expires_delta = timedelta(minutes=expires_minutes)
        token = create_access_token(
            payload={"sub": user_id, "email": email},
            secret_key=self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
            expires_delta=expires_delta,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
        )
