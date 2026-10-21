# Property Intelligence Platform — Phase 1 (Sprint 2)

AI-powered Real Estate Property Intelligence Platform. Buyers currently cannot get
trustworthy, consolidated answers about a property without manually cross-checking
listings, legal documents, and locality reports. The full platform will add document
processing, embeddings, vector retrieval, and RAG-grounded reports.

**Phase 1 scope (this implementation):** a small, tested FastAPI foundation — centralized
configuration, health/readiness endpoints, and a general (non-RAG) LLM chat endpoint
backed by Groq. Answers in Phase 1 are **general explanations only** and are **not**
grounded in property documents.

Out of scope for Phase 1: PostgreSQL, vector DB, embeddings, document upload/parsing,
chunking, retrieval, RAG orchestration, discrepancy detection, frontend, deployment.

## Repository layout

```text
.
├── Readme.md
├── .gitignore
└── backend/
    ├── app/
    │   ├── main.py               # FastAPI entry point (create_app factory + app)
    │   ├── api/routes/
    │   │   ├── health.py         # GET /health (liveness), GET /ready (readiness)
    │   │   └── llm.py            # POST /llm/chat (thin, delegates to service)
    │   ├── core/
    │   │   ├── config.py         # Pydantic Settings from environment variables
    │   │   └── prompt.py         # Phase 1 system prompt (RAG-ready foundation)
    │   ├── schemas/llm.py        # ChatRequest / ChatResponse validation
    │   └── services/llm_service.py  # Groq (OpenAI-compatible) wrapper + safe errors
    ├── tests/
    │   ├── conftest.py
    │   ├── test_health.py
    │   └── test_llm.py           # mocked provider; no paid calls, no real key
    ├── requirements.txt
    ├── pytest.ini
    ├── .env.example              # placeholder values only, never real secrets
    └── .gitignore
```

## Configuration

All settings load from environment variables (optionally via a `backend/.env` file).
Copy `backend/.env.example` to `backend/.env` and set values:

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `property-intelligence-api` | Service name in health responses |
| `APP_ENV` | `development` | Environment label |
| `API_PREFIX` | `/api/v1` | Prefix for all API routes |
| `LLM_PROVIDER` | `groq` | Only `groq` is supported in Phase 1 |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Chat model (free tier) |
| `GROQ_API_KEY` | _(none)_ | **Required only for live chat**; health works without it |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq's OpenAI-compatible endpoint |
| `LLM_TIMEOUT_SECONDS` | `30` | Provider request timeout (no auto-retries) |
| `LLM_MAX_TOKENS` | `1024` | Max completion tokens per chat request |
| `LLM_MAX_REQUEST_CHARS` | `2000` | Max user-message length (longer → HTTP 422) |
| `LLM_REASONING_EFFORT` | `low` | GPT-OSS reasoning effort (`low`/`medium`/`high`) |

Secrets are never hardcoded, never logged, and `.env` files are git-ignored.

Get a free Groq API key at <https://console.groq.com/keys>. The default model
`openai/gpt-oss-120b` is on Groq's free tier (about 30 RPM / 1,000 RPD / 200K TPD,
subject to change) and has a 131K-token context, which suits property Q&A now and
RAG over documents later. `qwen/qwen3.8-27b` is a free-tier alternative if you need
longer daily token budgets.

## Development commands

Create and activate a virtual environment, then install dependencies:

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run the API (from the `backend/` directory):

```bash
cd backend
uvicorn app.main:app --reload
```

Run the tests (from the `backend/` directory; mocked provider, no API key needed):

```bash
cd backend
pytest -q
```

## API

Interactive docs (dev server): `http://127.0.0.1:8000/docs`

Endpoints (all under `API_PREFIX`, default `/api/v1`):

- `GET /api/v1/health` → `{"status": "ok", "service": "property-intelligence-api"}`
  Liveness only; never calls the LLM provider.
- `GET /api/v1/ready` → readiness incl. `llm_configured` flag; no paid calls.
- `POST /api/v1/llm/chat` with `{"message": "..."}` → `{"answer": "..."}`.
  Empty/whitespace messages → 422; over-length → 422; missing API key → 503;
  rate limit → 429; timeout → 504; auth/upstream failure → 502.
  Error responses contain safe messages only (no stack traces, no secrets).

Verified with the installed environment (`openai` SDK pointed at Groq, FastAPI 0.143):
`pytest -q` → **20 passed**; live server checks confirmed `health`, `ready`
(`degraded` without a key), `openapi.json` paths, `/docs` (HTTP 200), chat
without a key → 503, and over-config validation paths via the mocked tests.
Live chat with a real answer requires setting `GROQ_API_KEY` and was not
exercised (no credentials in this environment).
