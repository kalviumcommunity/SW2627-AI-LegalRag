# Property Intelligence Platform — Phases 1–4 (Sprint 2)

AI-powered Real Estate Property Intelligence Platform. Buyers currently cannot get
trustworthy, consolidated answers about a property without manually cross-checking
listings, legal documents, and locality reports. The full platform will add document
processing, embeddings, vector retrieval, and RAG-grounded reports.

**Phase 1:** a tested FastAPI foundation — centralized configuration, health/readiness
endpoints, and a general (non-RAG) LLM chat endpoint backed by Groq. Chat answers are
**general explanations only** and are **not** grounded in property documents.

**Phase 2:** safe document ingestion for PDF, TXT, and Markdown — validation,
page-aware text extraction, conservative cleaning, configurable overlapping chunking,
and traceable chunk metadata exposed through `POST /api/v1/documents/ingest`.

**Phase 3:** configurable embedding generation plus durable PostgreSQL/pgvector
storage. Chunks produced by Phase 2 are embedded and committed with their document,
text, ordering, page references, offsets, metadata, and vectors. A successful ingestion
response is returned only after the database transaction commits. Identical re-uploads
are idempotent and return the previously stored document.

**Phase 4 (this implementation):** semantic retrieval of stored chunks by natural-
language query, configurable top-K, metadata-filtered search, optional cosine-
similarity thresholds, and hybrid semantic + PostgreSQL full-text retrieval fused with
reciprocal rank fusion (RRF). `POST /api/v1/retrieval/search` returns ranked chunks
with source metadata for future citations. A reproducible synthetic evaluation corpus
and Hit@K / Recall@K / Precision@K / MRR metrics are included.

Phase 4 does **not** generate answers from retrieved chunks, build RAG context,
format citations, add conversational memory, stream responses, add a chat UI, run OCR,
rerank results, or deploy the application. Those belong to later phases.

## Repository layout

```text
.
├── Readme.md
├── .gitignore
└── backend/
    ├── alembic.ini                    # Alembic config (URL read from DATABASE_URL)
    ├── migrations/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    │       ├── 0001_create_documents_and_chunks.py
    │       └── 0002_add_retrieval_indexes.py   # GIN full-text index
    ├── app/
    │   ├── main.py                    # FastAPI entry point (create_app factory + app)
    │   ├── api/routes/
    │   │   ├── health.py              # GET /health, GET /ready
    │   │   ├── llm.py                 # POST /llm/chat
    │   │   ├── documents.py           # POST /documents/ingest
    │   │   └── retrieval.py           # POST /retrieval/search
    │   ├── core/
    │   │   ├── config.py              # Pydantic Settings (LLM, ingestion, retrieval)
    │   │   └── prompt.py              # Phase 1 system prompt
    │   ├── db/
    │   │   ├── base.py                # SQLAlchemy declarative base
    │   │   └── models.py              # documents / chunks / pgvector / FTS indexes
    │   ├── schemas/
    │   │   ├── llm.py                 # ChatRequest / ChatResponse
    │   │   ├── documents.py           # DocumentChunk / IngestResponse
    │   │   └── retrieval.py           # retrieval request/response/filter schemas
    │   └── services/
    │       ├── llm_service.py         # Groq (OpenAI-compatible) wrapper
    │       ├── document_validation.py # filename/MIME/signature/size checks
    │       ├── text_extraction.py     # PDF / TXT / Markdown extractors
    │       ├── text_cleaning.py       # conservative normalization
    │       ├── chunking.py            # character-based overlapping chunks
    │       ├── temp_storage.py        # secure temp files + guaranteed cleanup
    │       ├── ingestion_errors.py    # safe API-facing error types
    │       ├── storage_errors.py      # safe database/storage error types
    │       ├── embedding_service.py   # providers, batching, validation, normalization
    │       ├── document_store.py      # transactional PostgreSQL/pgvector storage
    │       ├── document_ingestion.py  # pipeline orchestration
    │       ├── retrieval_errors.py    # safe retrieval error types
    │       ├── retrieval_store.py     # pgvector cosine + PostgreSQL full-text SQL
    │       ├── retrieval_service.py   # validation, embedding, ranking, RRF fusion
    │       └── retrieval_evaluation.py # Hit@K / Recall@K / Precision@K / MRR
    ├── evaluation/
    │   ├── retrieval_dataset.json     # synthetic grounded corpus + questions
    │   └── dataset.py                 # load/validate/materialize evaluation corpus
    ├── scripts/
    │   └── evaluate_retrieval.py      # reproducible evaluation runner
    ├── tests/
    │   ├── conftest.py                # settings isolation + database fixtures
    │   ├── fakes.py                   # mocked providers + in-memory stores
    │   ├── pdf_factory.py             # synthetic PDF fixtures (no external services)
    │   ├── test_health.py
    │   ├── test_llm.py
    │   ├── test_chunking.py
    │   ├── test_documents.py          # Phase 2 API regression tests
    │   ├── test_embeddings.py
    │   ├── test_persistence.py        # requires TEST_DATABASE_URL
    │   ├── test_ingestion_integration.py  # requires TEST_DATABASE_URL
    │   ├── test_retrieval_service.py
    │   ├── test_retrieval_api.py
    │   ├── test_retrieval_integration.py  # requires TEST_DATABASE_URL
    │   └── test_retrieval_evaluation.py
    ├── requirements.txt
    ├── pytest.ini
    ├── .env.example                   # placeholder values only, never real secrets
    └── .gitignore
```

## Prerequisites

- Python 3.11+ (verified on Python 3.13 on Windows).
- PostgreSQL with the **pgvector** extension. `pgvector/pgvector:pg17`
  (pgvector 0.8.7) was used for verification. A local PostgreSQL installation works
  too if the `vector` extension is installed.
- No paid embedding API is required with the default configuration. The first local
  embedding run downloads a ~130 MB quantized ONNX model from Hugging Face.

## Database setup (local development)

The simplest option is Docker. Only PostgreSQL/pgvector is needed; the application
itself runs directly with Python.

```bash
docker run -d --name property-intel-pg \
  -e POSTGRES_USER=property \
  -e POSTGRES_PASSWORD=property_dev_password \
  -e POSTGRES_DB=property_intelligence \
  -p 5433:5432 \
  -v property_intel_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg17
```

Port `5433` avoids clashing with a PostgreSQL server already using `5432`; change the
mapping if `5432` is free. The named volume keeps records across container restarts.

Create a separate database for tests once:

```bash
docker exec property-intel-pg psql -U property -d postgres \
  -c "CREATE DATABASE property_intelligence_test;"
```

Using a local PostgreSQL installation instead:

1. Create a database and user, for example `property_intelligence`.
2. Install pgvector for your PostgreSQL version.
3. Enable the extension (as a superuser or a user with the required privilege):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Run the migrations described below.

### Migrations

Alembic creates `documents` and `chunks`, enables pgvector, creates the HNSW cosine
index (`vector_cosine_ops`), and adds a GIN index for English full-text search used by
hybrid retrieval. Set `DATABASE_URL` (directly or in `backend/.env`) and run from
`backend/`:

```bash
alembic upgrade head
alembic current
```

Useful commands:

```bash
alembic downgrade base     # removes the tables (leaves the pgvector extension)
alembic history
alembic check              # verifies the models and applied schema agree
```

The application does **not** auto-run migrations at startup. If the schema is missing,
ingestion or retrieval returns HTTP `503` with a safe message asking you to run
`alembic upgrade head`.

## Configuration

All settings load from environment variables (optionally via a `backend/.env` file).
Copy `backend/.env.example` to `backend/.env` and set values:

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `property-intelligence-api` | Service name in health responses |
| `APP_ENV` | `development` | Environment label |
| `API_PREFIX` | `/api/v1` | Prefix for all API routes |
| `LLM_PROVIDER` | `groq` | Only `groq` is supported |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Chat model (free tier) |
| `GROQ_API_KEY` | _(none)_ | **Required only for live chat**; health/ingestion work without it |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq's OpenAI-compatible endpoint |
| `LLM_TIMEOUT_SECONDS` | `30` | Provider request timeout (no auto-retries) |
| `LLM_MAX_TOKENS` | `1024` | Max completion tokens per chat request |
| `LLM_MAX_REQUEST_CHARS` | `2000` | Max user-message length (longer → HTTP 422) |
| `LLM_REASONING_EFFORT` | `low` | GPT-OSS reasoning effort (`low`/`medium`/`high`) |
| `DOCUMENT_MAX_UPLOAD_BYTES` | `10485760` (10 MiB) | Maximum multipart upload size |
| `DOCUMENT_ALLOWED_EXTENSIONS` | `pdf,txt,md` | Comma-separated allowed extensions |
| `DOCUMENT_CHUNK_SIZE_CHARS` | `3200` | Target characters per chunk |
| `DOCUMENT_CHUNK_OVERLAP_CHARS` | `480` | Overlap characters between chunks |
| `DOCUMENT_CHUNK_MIN_SPLIT_RATIO` | `0.5` | Minimum fraction of chunk size before a preferred boundary is used |
| `DOCUMENT_TEMP_DIR` | _(OS temp)_ | Optional private temporary directory |
| `DATABASE_URL` | _(none)_ | **Required for ingestion.** Example: `postgresql+psycopg://property:property_dev_password@localhost:5433/property_intelligence` |
| `DATABASE_ECHO` | `false` | Log SQL (development only; may log chunk text) |
| `DATABASE_POOL_SIZE` | `5` | SQLAlchemy connection pool size |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5` | PostgreSQL connection timeout |
| `EMBEDDING_PROVIDER` | `fastembed` | `fastembed` (local, free) or `openai` |
| `EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5-Q` | Local model or API model name |
| `EMBEDDING_DIMENSIONS` | `768` | Must match the model and the database column |
| `EMBEDDING_BATCH_SIZE` | `32` | Texts sent to the provider per batch |
| `EMBEDDING_CACHE_DIR` | _(fastembed default)_ | Optional local model cache directory |
| `EMBEDDING_API_KEY` | _(none)_ | Required only for `EMBEDDING_PROVIDER=openai` |
| `EMBEDDING_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible embeddings endpoint |
| `EMBEDDING_TIMEOUT_SECONDS` | `30` | Remote embedding request timeout (no auto-retries) |
| `RETRIEVAL_DEFAULT_TOP_K` | `5` | Top-K used when a search request omits `top_k` |
| `RETRIEVAL_MAX_TOP_K` | `50` | Maximum accepted `top_k` |
| `RETRIEVAL_MAX_QUERY_CHARS` | `2000` | Maximum normalized query length |
| `RETRIEVAL_HYBRID_CANDIDATE_LIMIT` | `50` | Candidate pool per retriever before RRF fusion |
| `RETRIEVAL_RRF_K` | `60` | RRF rank-smoothing constant |

Secrets are never hardcoded, never logged, and `.env` files are git-ignored.

Get a free Groq API key at <https://console.groq.com/keys>. The default model
`openai/gpt-oss-120b` is on Groq's free tier (about 30 RPM / 1,000 RPD / 200K TPD,
subject to change) and has a 131K-token context, which suits property Q&A now and
RAG over documents later. `qwen/qwen3.8-27b` is a free-tier alternative if you need
longer daily token budgets.

### Embedding model and vectors

The default embedding configuration is:

| Property | Value |
|---|---|
| Provider | `fastembed` (local ONNX, no API key) |
| Model | `nomic-ai/nomic-embed-text-v1.5-Q` |
| Dimensions | `768` |
| Context | 8192 tokens |
| Normalization | L2-normalized by `EmbeddingService` before storage |
| Distance | Cosine (`vector_cosine_ops`) |
| Database column | `chunks.embedding vector(768)` |
| Batch size | 32 texts per provider call |

Chunk text is embedded exactly as chunked; no task prefix is added. The model is
downloaded once per process/cache on first use. Quantized local inference is
CPU-friendly, but the first request after a cold start is slower.

To use an OpenAI-compatible provider instead:

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=768
EMBEDDING_API_KEY=<your-key>
```

For `text-embedding-3-*` models the service requests the configured dimensions. Vectors
are validated (non-empty, numeric, finite, expected length) and normalized regardless of
provider. `GET /api/v1/ready` reports configuration flags only; it never downloads a
model or makes a paid call.

**Changing dimensions requires a new migration.** The migration fixes `vector(768)`;
the store compares the physical column dimension with `EMBEDDING_DIMENSIONS` and fails
with a clear configuration error instead of inserting incompatible data. Changing
`EMBEDDING_MODEL`/`EMBEDDING_DIMENSIONS` without a migration (and re-embedding existing
chunks) is not supported.

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

Copy the environment template and fill in `DATABASE_URL` (never commit `.env`):

```bash
cp backend/.env.example backend/.env
```

Apply migrations and run the API (from the `backend/` directory):

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Run the tests (from `backend/`). Tests never call a paid API: the LLM, embedding
provider, and database writes are mocked or use a dedicated test database.

```bash
cd backend
pytest -q
```

Database-backed tests are skipped unless `TEST_DATABASE_URL` points to a **separate**
PostgreSQL/pgvector database. The fixture drops and recreates its tables, so never point
it at production or development data:

```bash
# PowerShell
$env:TEST_DATABASE_URL='postgresql+psycopg://property:property_dev_password@127.0.0.1:5433/property_intelligence_test'
pytest -q
```

```bash
# bash
export TEST_DATABASE_URL='postgresql+psycopg://property:property_dev_password@127.0.0.1:5433/property_intelligence_test'
pytest -q
```

## API

Interactive docs (dev server): `http://127.0.0.1:8000/docs`

Endpoints (all under `API_PREFIX`, default `/api/v1`):

- `GET /api/v1/health` → liveness only; never calls the LLM, embedding provider, or DB.
- `GET /api/v1/ready` → configuration flags for the LLM, embedding provider/model/
  dimensions, database, and retrieval defaults. No paid calls or model downloads.
- `POST /api/v1/llm/chat` with `{"message": "..."}` → `{"answer": "..."}`.
  Empty/whitespace messages → 422; over-length → 422; missing API key → 503;
  rate limit → 429; timeout → 504; auth/upstream failure → 502.
  Error responses contain safe messages only (no stack traces, no secrets).
- `POST /api/v1/documents/ingest` → validate, extract, clean, chunk, embed, and persist
  a document (Phases 2–3; response below).
- `POST /api/v1/retrieval/search` → semantic or hybrid ranked chunk retrieval with
  optional metadata filters (Phase 4; details below).

## Retrieval (Phase 4)

### Behavior

- The query is trimmed and internal whitespace is collapsed; empty queries and queries
  longer than `RETRIEVAL_MAX_QUERY_CHARS` are rejected with HTTP 422.
- `semantic` mode embeds the query with the configured embedding provider and orders
  chunks by pgvector cosine distance (`<=>`), using the existing HNSW index. Returned
  `score` is cosine similarity (`1 - distance`), where higher is better.
- `hybrid` mode combines semantic candidates with PostgreSQL English full-text search
  (`to_tsvector` / `plainto_tsquery` / `ts_rank_cd`) using reciprocal rank fusion:
  `score = Σ 1 / (RETRIEVAL_RRF_K + rank)`, with one-based ranks. Hybrid `score` is an
  RRF score and is **not** comparable to cosine similarity.
- Ties are deterministic: score first, then semantic/keyword rank, then chunk ID.
- `top_k` defaults to `RETRIEVAL_DEFAULT_TOP_K` and is capped by
  `RETRIEVAL_MAX_TOP_K`.
- `min_score` is an optional cosine-similarity threshold in `[-1, 1]`. In hybrid mode it
  filters semantic candidates before fusion; keyword-only matches are not thresholded
  because their relevance scale is different.
- All filters are applied in SQL before ranking: `document_id`, exact
  `filters.source_filename`, `filters.source_type` (`pdf`/`txt`/`markdown`), and
  `filters.page_number`. Page filtering also matches multi-page chunks through
  `metadata.page_numbers`.
- Each result returns the chunk text plus source metadata needed by a future citation
  step: `filename`, `source_type`, `page_number`, `page_numbers`, `chunk_index`, offsets,
  and full Phase 2 `chunk_metadata`.
- No LLM call is made by retrieval, and query/chunk text is not written to logs.

### Request example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What legal documents are available for this property?",
    "top_k": 5,
    "mode": "hybrid",
    "filters": {"source_type": "pdf", "page_number": 1},
    "min_score": 0.2
  }'
```

```python
import httpx

response = httpx.post(
    "http://127.0.0.1:8000/api/v1/retrieval/search",
    json={
        "query": "What legal documents are available for this property?",
        "top_k": 5,
        "mode": "semantic",
    },
    timeout=60,
)
print(response.status_code, response.json())
```

### Response example

```json
{
  "query": "What legal documents are available for this property?",
  "mode": "semantic",
  "results": [
    {
      "chunk_id": "chk_9a02…",
      "document_id": "doc_4f1c…",
      "text": "ENCUMBRANCE CERTIFICATE…",
      "score": 0.6744,
      "score_type": "cosine_similarity",
      "distance": 0.3256,
      "semantic_score": 0.6744,
      "keyword_rank": null,
      "metadata": {
        "filename": "encumbrance_certificate.txt",
        "source_type": "txt",
        "page_number": null,
        "page_numbers": [],
        "chunk_index": 0,
        "start_offset": 0,
        "end_offset": 812,
        "chunk_metadata": {
          "character_count": 812,
          "chunking": {
            "strategy": "character",
            "chunk_size_chars": 3200,
            "overlap_chars": 480
          },
          "warnings": []
        }
      }
    }
  ],
  "result_count": 1
}
```

An empty result set is a successful HTTP 200 with `results: []` and
`result_count: 0`; it does not mean the query was malformed.

### Retrieval errors

| Condition | HTTP status |
|---|---|
| Blank/whitespace-only query, `top_k` out of range, invalid mode/score/filter | `422` |
| `DATABASE_URL` missing, missing migrations, incompatible vector dimension | `503` |
| Embedding provider rate limit | `429` |
| Embedding provider unavailable or malformed response | `502` |
| Embedding provider timeout | `504` |
| Database unavailable or retrieval query failure | `503` / `500` with a safe message |

Error responses never include stack traces, credentials, SQL, query text, or chunk text.

### Evaluation

`backend/evaluation/retrieval_dataset.json` defines a small synthetic property corpus
(sale deed, encumbrance certificate, property details, locality report, cost breakdown,
and a two-page title-chain PDF) and ten grounded questions: eight answerable and two
with no supporting evidence. Expected chunk IDs are resolved from marker phrases at
evaluation time rather than hardcoded.

The runner ingests the corpus with the real configured embedding provider and reports
Hit@K, Recall@K, Precision@K, and MRR for four configurations: semantic, filtered
semantic, hybrid, and filtered hybrid. No-answer questions count as zero for those
metrics. Precision uses the number of unique results actually returned.

From `backend/`, against a **dedicated** evaluation database (the script can truncate
tables with `--reset`):

```bash
export DATABASE_URL='postgresql+psycopg://property:property_dev_password@127.0.0.1:5433/property_intelligence_test'
python scripts/evaluate_retrieval.py --reset --k 3 --output evaluation/last_run.json
```

Verified results with the default local fastembed model at `K=3` (6 chunks ingested):

| Configuration | Hit@3 | Recall@3 | Precision@3 | MRR | Mean total |
|---|---:|---:|---:|---:|---:|
| semantic | 0.800 | 0.800 | 0.367 | 0.800 | 64.3 ms |
| semantic + filters | 0.800 | 0.800 | 0.433 | 0.800 | 62.7 ms |
| hybrid | 0.800 | 0.800 | 0.367 | 0.800 | 68.6 ms |
| hybrid + filters | 0.800 | 0.800 | 0.433 | 0.800 | 68.6 ms |

`K=3` was chosen because the corpus has only six chunks; `K=5` would return nearly the
entire corpus and make Hit@K/Recall@K trivially high. Timings are from one local run
and are hardware-dependent, not benchmarks.

All eight answerable questions were ranked first in every configuration. Both
no-evidence questions scored zero because the metric intentionally treats unsupported
queries as misses. The corpus is intentionally small, so Hit@K and Recall@K saturate;
these numbers demonstrate a working evaluation pipeline, not production retrieval
quality. A real API call using the same database and model returned the sale deed as
the top result for an ownership question, and page filtering matched a two-page chunk
through `metadata.page_numbers`.

Query-plan checks on the populated evaluation database showed that the keyword query
uses `ix_chunks_text_fts` (`Bitmap Index Scan`), while the semantic query uses the HNSW
index when sequential scans are discouraged. At six rows PostgreSQL correctly prefers a
sequential scan for semantic ordering; the index is intended for larger corpora.

## Document ingestion (Phases 2–3)

### Supported formats and validation

| Format | Extensions | Extraction | `source_type` |
|---|---|---|---|
| PDF | `.pdf` | `pypdf`, one result per page | `pdf` |
| Plain text | `.txt` | UTF-8 / BOM-marked UTF-16 or UTF-32 | `txt` |
| Markdown | `.md` | same as text, headings/paragraphs preserved | `markdown` |

Every upload is checked for:

- non-empty content and the configurable maximum size;
- an allowed extension;
- a matching declared MIME type (generic `application/octet-stream` is allowed because
  browsers often omit the specific type);
- an actual PDF `%PDF-` signature, or text content that is not binary;
- a decodable text encoding.

Filenames are reduced to a safe basename, so paths such as `../../etc/passwd.txt` are
stored and reported as `passwd.txt`. Uploads are written only to an OS-created temporary
file with a randomized name and mode private to the server; the client filename is never
used as a filesystem path. Temporary files are deleted after success and after failure.

### Extraction behavior

- PDFs are read page by page and original page numbers are preserved.
- Encrypted/password-protected PDFs and structurally malformed PDFs return
  `status: "failed"` with a safe message (HTTP 422).
- A PDF with **no extractable text** (for example, a scanned document) returns
  `status: "ocr_required"` (HTTP 200) with zero chunks and an explanatory warning. The
  OCR-required document record is persisted with zero chunks. OCR itself is **not
  implemented**.
- If individual PDF pages fail but others are readable, the readable pages are processed
  and a warning is attached to the result metadata.
- Invalid UTF-8/UTF-16/UTF-32 text is rejected rather than silently guessed.

### Cleaning

Cleaning is deliberately conservative:

- line endings and Unicode are normalized consistently (NFC);
- NUL/control characters and zero-width markers are removed;
- runs of spaces/tabs and excess blank lines are collapsed;
- headings, single line breaks, paragraphs, punctuation, numbers, dates, identifiers,
  clause labels, and names are preserved;
- no lowercasing, punctuation stripping, or sentence rewriting occurs.

### Chunking

Chunking is **character-based**, because no tokenizer is assumed at runtime. Character
counts are never described as token counts. Defaults (`3200` characters with `480`
characters of overlap) approximate 800/120 English tokens at roughly four characters per
token.

- The splitter prefers paragraph boundaries, then sentence boundaries, then line breaks,
  then whitespace, and only hard-cuts unbroken passages.
- Chunks shorter than the configured size are returned as a single chunk.
- Overlap always advances forward; it cannot loop or produce chunks with no new content.
- Empty documents produce no chunks (and are rejected if they have no readable text).
- Offsets are 0-based character offsets into the cleaned concatenated text
  (`start_offset` inclusive, `end_offset` exclusive). PDF pages are joined by a blank
  line, so `extracted_characters` (sum of cleaned page lengths) can be slightly smaller
  than the final `end_offset`.

### Chunk metadata

Each chunk always includes:

| Field | Meaning |
|---|---|
| `chunk_id` | Generated (`chk_…`) identifier |
| `document_id` | Generated (`doc_…`) identifier shared by all chunks |
| `chunk_index` | Zero-based order within the document |
| `text` | Cleaned chunk text |
| `source_filename` | Sanitized upload filename |
| `source_type` | `pdf`, `txt`, or `markdown` |
| `page_number` | Set only when the chunk lies on exactly one PDF page; otherwise `null` |
| `start_offset` / `end_offset` | Character offsets in the cleaned text |
| `metadata` | JSON-serializable details (see below) |

`metadata` contains `character_count`, the chunking parameters, extraction warnings,
`total_pages` for PDFs, and `page_numbers` for PDF chunks. Multi-page chunks report all
applicable pages in `metadata.page_numbers` and keep `page_number` as `null` rather than
inventing a single page. Non-paginated formats omit page fields. The complete metadata
JSON is preserved in the `chunks.metadata` JSONB column.

### Embedding and persistence behavior

1. The upload is validated, extracted, cleaned, and chunked using the Phase 2 services.
2. Before embedding, the service checks whether the same bytes and sanitized filename
   were already committed. If so, the existing document/chunks are returned and no
   second embedding call is made.
3. Chunks are embedded in input order in batches. Every returned vector is checked for a
   non-empty, numeric, finite, expected-dimension response, then L2-normalized.
4. The document row and all chunk rows (including vectors and metadata) are written in a
   single database transaction. A failure rolls back the whole document; no orphaned
   chunks or misleading `processed` status remain.
5. The API returns success only after the transaction commits. Database, embedding, and
   transaction failures return safe errors and never claim that indexing succeeded.

### Request example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents/ingest \
  -F "file=@property_report.pdf;type=application/pdf"
```

```python
import httpx

with open("property_report.pdf", "rb") as handle:
    response = httpx.post(
        "http://127.0.0.1:8000/api/v1/documents/ingest",
        files={"file": ("property_report.pdf", handle, "application/pdf")},
        timeout=60,
    )
print(response.status_code, response.json())
```

### Response example

```json
{
  "document_id": "doc_4f1c…",
  "filename": "property_report.pdf",
  "status": "processed",
  "extracted_characters": 12500,
  "chunk_count": 1,
  "chunks": [
    {
      "chunk_id": "chk_9a02…",
      "document_id": "doc_4f1c…",
      "chunk_index": 0,
      "text": "Example extracted property information…",
      "source_filename": "property_report.pdf",
      "source_type": "pdf",
      "page_number": 1,
      "start_offset": 0,
      "end_offset": 3200,
      "metadata": {
        "character_count": 3200,
        "page_numbers": [1],
        "total_pages": 3,
        "chunking": {
          "strategy": "character",
          "chunk_size_chars": 3200,
          "overlap_chars": 480
        },
        "warnings": []
      }
    }
  ],
  "page_count": 3,
  "warnings": [],
  "detail": null
}
```

### Status and error responses

`status` is one of:

- `processed` — text extracted, chunked, embedded, and committed (HTTP 200).
- `ocr_required` — a PDF was accepted but has no extractable text; the document record is
  committed with zero chunks (HTTP 200).
- `failed` — extraction failed, e.g. encrypted or malformed PDF (HTTP 422 with the same
  structured response schema and a safe `detail`). Failed extraction attempts are not
  persisted.

Validation and service errors use the standard FastAPI `{"detail": "..."}` shape:

| Condition | HTTP status |
|---|---|
| Empty upload, invalid signature/binary content, invalid encoding, no readable text | `400` |
| Upload exceeds `DOCUMENT_MAX_UPLOAD_BYTES` | `413` |
| Unsupported extension or mismatched MIME type | `415` |
| Missing multipart `file` field | `422` |
| Encrypted/malformed PDF or other extraction failure | `422` (`status: "failed"`) |
| Embedding provider rate limit | `429` |
| Database or embedding configuration unavailable; missing migrations; dimension mismatch | `503` |
| Embedding provider unavailable or invalid/malformed embedding response | `502` |
| Embedding provider timeout | `504` |
| Database transaction or other storage failure | `500` (nothing committed) |
| Temporary storage/internal failure | `500` with a safe message |

Responses never include stack traces, filesystem paths, database credentials, API keys,
or document contents in error messages. The server does not log complete document text.

### Database schema

`documents`:

- `id` (`doc_…`, primary key), `filename`, `source_type`, `status`;
- `content_sha256` plus a unique `(content_sha256, filename)` constraint for idempotent
  re-ingestion;
- `extracted_characters`, `chunk_count`, `page_count`;
- `warnings`/`detail` (JSONB/text), `created_at`, `updated_at`.

`chunks`:

- `id` (`chk_…`, primary key), `document_id` (foreign key, `ON DELETE CASCADE`);
- `chunk_index` (unique per document), `text`, `source_filename`, `source_type`;
- `page_number`, `start_offset`, `end_offset`, `metadata` (JSONB);
- `embedding vector(768)` (not null), with an HNSW index using `vector_cosine_ops`;
- `ix_chunks_text_fts`, a GIN expression index on `to_tsvector('english', text)` for
  hybrid keyword retrieval.

Duplicate behavior: identical bytes **and** sanitized filename return the existing
document (same `document_id`) without adding rows or re-embedding. The same bytes under a
different filename are treated as a new document. New content under an existing filename
creates a new document; there is no in-place replacement or version history yet.

### Manual verification

```bash
# 1. Start PostgreSQL/pgvector (see Database setup) and apply migrations.
cd backend
export DATABASE_URL='postgresql+psycopg://property:property_dev_password@127.0.0.1:5433/property_intelligence'
alembic upgrade head

# 2. Start the API.
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. In another terminal, ingest a document (the first run may download the model).
curl -X POST http://127.0.0.1:8000/api/v1/documents/ingest \
  -F "file=@property_report.pdf;type=application/pdf"

# 4. Verify committed rows directly in PostgreSQL.
docker exec property-intel-pg psql -U property -d property_intelligence \
  -c "SELECT id, filename, status, chunk_count FROM documents;" \
  -c "SELECT document_id, chunk_index, page_number, vector_dims(embedding) FROM chunks;"

# 5. Search the stored chunks.
curl -X POST http://127.0.0.1:8000/api/v1/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What property documents are available?", "top_k": 3, "mode": "semantic"}'
```

A successful HTTP 200 means the rows above exist. Restarting the API does not remove
them. Re-uploading the identical file returns the same `document_id` and creates no
duplicate rows. Stopping the database before ingestion or retrieval produces a safe
HTTP 503.

## Verification

The suite covers Phase 1 health/LLM contracts, Phase 2 validation/extraction/cleaning/
chunking, Phase 3 embedding/persistence, and Phase 4 retrieval:

- embedding order, batching, empty input, normalization, malformed/non-finite/wrong-
  dimension vectors, provider failures, timeouts, rate limits, and mocked OpenAI errors;
- document/chunk/vector persistence, metadata and page preservation, new-store reads,
  idempotent re-ingestion, transaction rollback, cascade deletion, constraints,
  dimension mismatch, missing migrations, and unreachable databases;
- retrieval query validation, default/max top-K, cosine score mapping, deterministic
  ordering, duplicate-free RRF fusion, metadata/page filters, min-score thresholds,
  provider/database failure mappings, and response metadata;
- evaluation formulas including missing evidence, duplicate results, partial recall,
  empty result sets, and invalid cutoffs;
- end-to-end ingestion and retrieval through the API with mocked providers and a real
  PostgreSQL/pgvector test database.

```bash
cd backend
pytest -q                     # 162 passed, 25 skipped (no TEST_DATABASE_URL)
```

With a dedicated pgvector test database:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://property:property_dev_password@127.0.0.1:5433/property_intelligence_test'
pytest -q                     # 187 passed
```

Verified results for this implementation: **162 passed / 25 skipped** without a test
database and **187 passed** with PostgreSQL/pgvector. A real HTTP retrieval call using
the default local model returned the expected sale-deed chunk first, and page filtering
matched a two-page chunk through `metadata.page_numbers`. The evaluation runner was also
executed against a real pgvector database with the local embedding model. No automated
test calls a paid embedding or LLM API.

## Current limitations and deferred work

- RAG context construction, grounded answer generation, citations/quotations,
  hallucination guardrails, conversational memory, streaming, and a chat UI are **not
  implemented** (Phase 5+).
- Retrieval filters are document/chunk-level only. There is no property entity or
  `property_id` association yet, so property-level filtering requires a schema change.
- No reranking or relevance optimization beyond optional similarity thresholds and
  hybrid RRF; no learned fusion weights.
- Hybrid keyword search is English-only (`to_tsvector('english', text)`).
- No pagination/cursor API; responses are capped by `RETRIEVAL_MAX_TOP_K`.
- No frontend/dashboard, authentication/authorization, deployment configuration, or
  background job queue.
- No OCR: image-only PDFs are persisted as `ocr_required` with zero chunks.
- Failed extraction attempts are not persisted; only `processed` and `ocr_required`
  document records exist.
- Re-ingestion is idempotent for identical bytes + filename only. There is no update/
  replacement API, version history, or deletion endpoint.
- The vector dimension is fixed at 768 by the initial migration. A different model
  dimension requires a new migration and re-embedding existing chunks.
- The local model downloads on first use; a network/cache failure returns HTTP 502.
  Very long texts may be truncated by the model's own token limit.
- No task prefix is added for the default Nomic model; retrieval still works, but
  document/query prefixes may improve quality.
- HNSW parameters (`m`, `ef_construction`, query-time `hnsw.ef_search`) and RRF weights
  have not been tuned or benchmarked. The evaluation corpus has only six chunks, so
  Hit@K/Recall@K saturate and precision is depressed; the numbers validate the pipeline,
  not production quality.
- Database writes, embeddings, and retrieval run synchronously in a worker thread;
  throughput is adequate for development but no load/performance testing was performed.
- The OpenAI-compatible embedding provider is covered by mocked unit tests but was not
  exercised against a live paid API.
