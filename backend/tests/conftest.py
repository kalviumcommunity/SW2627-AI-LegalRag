"""Shared fixtures: isolate settings cache and secrets for every test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
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
            text("DROP TABLE IF EXISTS chunks, documents, alembic_version CASCADE")
        )
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_database(migrated_database):
    with migrated_database.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE chunks, documents RESTART IDENTITY CASCADE")
        )
    yield migrated_database
