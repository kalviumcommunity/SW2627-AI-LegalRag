# Testing Strategy and Test Suite Execution

This document details the automated testing strategy covering unit tests, integration tests, and mock testing across the backend and frontend.

## 1. Testing Pyramid

- **Unit Tests**: Test isolated pure functions (text cleaning, character offset chunking, token bounding, filename validation).
- **Integration Tests**: Test database transactions, pgvector cosine distance lookups, and Alembic migrations against a test database.
- **E2E / Mock API Tests**: Test FastAPI endpoints (`/documents/ingest`, `/retrieval/search`, `/rag/ask`) using `httpx.AsyncClient` with mocked LLM and embedding providers.

---

## 2. Backend Pytest Execution

The test configuration is anchored in `backend/pytest.ini` and `backend/tests/`.

### Commands:
```bash
cd backend

# Run entire test suite
pytest

# Run tests with coverage report
pytest --cov=app --cov-report=term-missing

# Run only unit tests
pytest tests/unit/

# Run integration tests against test PostgreSQL
pytest tests/integration/
```

---

## 3. Test Fixtures and Mocking

- **Database Rollback Fixture**: Every test executes within a nested database savepoint transaction that rolls back automatically, preventing test pollution.
- **Embedding Mock**: Replaces remote embedding API calls with a deterministic deterministic vector mock to ensure test speed and zero API consumption.
- **LLM Output Mocks**: Tests for `POST /api/v1/rag/ask` simulate both valid citations (`[S1]`) and failure cases (missing citations, halluncinations) to verify the post-generation validator.
