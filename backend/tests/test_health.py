"""Health endpoint tests. No LLM credentials or network calls required."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _client_with_settings(settings: Settings) -> TestClient:
    app = create_app()
    from app.api.routes.health import get_settings_dep as health_dep
    from app.api.routes.llm import get_settings_dep as llm_dep

    app.dependency_overrides[health_dep] = lambda: settings
    app.dependency_overrides[llm_dep] = lambda: settings
    return TestClient(app)


def test_health_returns_expected_response():
    settings = Settings(groq_api_key=None)
    client = _client_with_settings(settings)
    response = client.get(f"{settings.api_prefix}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": settings.app_name}


def test_health_works_without_llm_credentials():
    # Health must not require an API key and must not call the provider.
    settings = Settings(groq_api_key=None)
    assert settings.is_llm_configured is False
    client = _client_with_settings(settings)
    response = client.get(f"{settings.api_prefix}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_llm_configuration_state():
    unconfigured = Settings(groq_api_key=None)
    client = _client_with_settings(unconfigured)
    response = client.get(f"{unconfigured.api_prefix}/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_configured"] is False
    assert body["status"] == "degraded"
    assert body["retrieval_configured"] is False
    assert body["retrieval_default_top_k"] == 5
    assert body["retrieval_max_top_k"] == 50

    configured = Settings(groq_api_key="test-key-not-a-secret")
    client = _client_with_settings(configured)
    response = client.get(f"{configured.api_prefix}/ready")
    assert response.status_code == 200
    assert response.json()["llm_configured"] is True
