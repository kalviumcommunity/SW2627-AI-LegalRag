"""Tests for Neon PostgreSQL connection configuration and URL normalization."""

import pytest
from app.core.config import Settings, normalize_database_url
from app.services.storage_errors import DatabaseConfigurationError
from app.services.document_store import get_shared_engine


def test_normalize_database_url_postgresql_to_psycopg():
    raw = "postgresql://user:secret@ep-demo-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    normalized = normalize_database_url(raw, direct=False)
    assert normalized == "postgresql+psycopg://user:secret@ep-demo-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_normalize_database_url_postgres_scheme():
    raw = "postgres://user:secret@ep-demo-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    normalized = normalize_database_url(raw, direct=False)
    assert normalized.startswith("postgresql+psycopg://")


def test_normalize_database_url_direct_strips_pooler():
    raw_pooled = "postgresql://user:secret@ep-demo-12345-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    # Runtime pooled connection preserves -pooler
    pooled = normalize_database_url(raw_pooled, direct=False)
    assert "-pooler" in pooled

    # Direct migration connection strips -pooler
    direct = normalize_database_url(raw_pooled, direct=True)
    assert "-pooler" not in direct
    assert "ep-demo-12345.us-east-2.aws.neon.tech" in direct
    assert direct.startswith("postgresql+psycopg://")


def test_normalize_database_url_appends_sslmode_for_neon():
    raw_no_ssl = "postgresql://user:secret@ep-demo-12345.us-east-2.aws.neon.tech/neondb"
    normalized = normalize_database_url(raw_no_ssl, direct=False)
    assert "sslmode=require" in normalized


def test_normalize_database_url_preserves_local_and_custom_urls():
    local_url = "postgresql+psycopg://property:dev_pass@localhost:5433/property_intelligence"
    assert normalize_database_url(local_url, direct=False) == local_url
    assert normalize_database_url(local_url, direct=True) == local_url


def test_normalize_database_url_empty_or_none():
    assert normalize_database_url(None) is None
    assert normalize_database_url("") is None
    assert normalize_database_url("   ") is None


def test_settings_get_database_url_pooled_vs_direct():
    settings = Settings(
        database_url="postgresql://user:pass@ep-project-pooler.c-2.neon.tech/neondb?sslmode=require"
    )
    assert "-pooler" in settings.get_database_url(direct=False)
    assert "-pooler" not in settings.get_database_url(direct=True)
    assert settings.get_database_url(direct=False).startswith("postgresql+psycopg://")
    assert settings.get_database_url(direct=True).startswith("postgresql+psycopg://")


def test_settings_explicit_direct_database_url():
    settings = Settings(
        database_url="postgresql://user:pass@ep-project-pooler.c-2.neon.tech/neondb?sslmode=require",
        direct_database_url="postgresql://user:pass@ep-project-direct.c-2.neon.tech/neondb?sslmode=require",
    )
    direct = settings.get_database_url(direct=True)
    assert "ep-project-direct.c-2.neon.tech" in direct


def test_unconfigured_database_raises_configuration_error():
    empty_settings = Settings(database_url=None)
    with pytest.raises(DatabaseConfigurationError) as exc_info:
        get_shared_engine(empty_settings)
    assert "Persistence is not configured" in str(exc_info.value)
