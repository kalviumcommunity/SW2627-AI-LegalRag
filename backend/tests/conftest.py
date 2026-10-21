"""Shared fixtures: isolate settings cache and secrets for every test."""

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
