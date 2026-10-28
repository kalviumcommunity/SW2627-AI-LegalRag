"""Shared fixtures: isolate settings cache, secrets, and auth for test runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.db.models import User
import app.main

BACKEND_DIR = Path(__file__).resolve().parents[1]
_ORIGINAL_CREATE_APP = app.main.create_app

_DEFAULT_TEST_USER = User(
    id="usr_test_default",
    email="test_default@propertyintel.local",
    hashed_password="hash",
    is_active=True,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)


def _test_create_app(*args, **kwargs):
    test_app = _ORIGINAL_CREATE_APP(*args, **kwargs)
    test_app.dependency_overrides[get_current_user] = lambda: _DEFAULT_TEST_USER
    return test_app


app.main.create_app = _test_create_app


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DIRECT_DATABASE_URL", "")
    GLOBAL_RATE_LIMITER.reset()
    get_settings.cache_clear()
    yield
    GLOBAL_RATE_LIMITER.reset()
    get_settings.cache_clear()
    GLOBAL_RATE_LIMITER.reset()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Dedicated PostgreSQL/pgvector database for persistence tests.

    Set ``TEST_DATABASE_URL`` to opt in. Without it, database-backed tests are
    reported as skipped rather than silently passing against production data.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; PostgreSQL/pgvector tests were skipped."
        )
    from app.core.config import normalize_database_url
    return normalize_database_url(url, direct=True) or url


@pytest.fixture(scope="session")
def migrated_database(test_database_url):
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", test_database_url)

    engine = create_engine(test_database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(
            text("DROP TABLE IF EXISTS chunks, documents, users, alembic_version CASCADE")
        )
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_database(migrated_database):
    with migrated_database.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE chunks, documents, users RESTART IDENTITY CASCADE")
        )
    yield migrated_database
