# Property Intelligence Platform — Phases 1–6 (Sprint 2)

AI-powered Real Estate Property Intelligence Platform. Buyers currently cannot get
trustworthy, consolidated answers about a property without manually cross-checking
listings, legal documents, and locality reports. The platform integrates document
ingestion, chunking, embeddings, vector retrieval, grounded RAG answer generation,
and document lifecycle management.

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

**Phase 4:** semantic retrieval of stored chunks by natural-language query,
configurable top-K, metadata-filtered search, optional cosine-similarity thresholds,
and hybrid semantic + PostgreSQL full-text retrieval fused with reciprocal rank fusion
(RRF). `POST /api/v1/retrieval/search` returns ranked chunks with source metadata.

**Phase 5:** end-to-end grounded RAG pipeline exposed through `POST /api/v1/rag/ask`.
Connects Phase 4 retrieval with weak-evidence filtering, overlap-aware bounded context
construction, nonce-delimited evidence blocks, strict grounded system prompting,
post-generation citation validation, and explicit evidence-status reporting (`supported`,
`insufficient_evidence`, `conflicting_evidence`, `no_relevant_sources`). Answers
reference verifiable citations (`[S1]`, `[S2]`) tied directly to retrieved chunks and
stored document records. The citation guarantee covers retrieved-source integrity only;
claim-level entailment is explicitly **not** verified.

**Phase 6 (this implementation):** document management APIs and lifecycle workflows
built on the validated Phase 2–5 foundations:
- `POST /api/v1/documents/ingest`: upload, extract, chunk, embed, and persist property documents.
- `GET /api/v1/documents`: paginated document listing with status and source format filtering.
- `GET /api/v1/documents/{document_id}`: document metadata and processing status retrieval.
- `GET /api/v1/documents/{document_id}/chunks`: paginated chunk metadata inspection with
  content protection (`include_text` parameter).
- `DELETE /api/v1/documents/{document_id}`: transactional document deletion with cascading
  removal of associated chunks and embeddings.
- Grounded RAG integration (`POST /api/v1/rag/ask`) supporting document-level filtering
  (`document_id`), citation preservation, and safe empty/unindexed handling.

Phase 6 single-question RAG and document APIs do **not** include conversational memory,
streaming, a frontend UI, OCR, or autonomous legal verification.

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
    │   │   ├── retrieval.py           # POST /retrieval/search
    │   │   └── rag.py                 # POST /rag/ask
    │   ├── core/
    │   │   ├── config.py              # Pydantic Settings (LLM, ingestion, retrieval, RAG)
    │   │   ├── prompt.py              # Phase 1 chat system prompt
    │   │   └── rag_prompt.py          # Phase 5 grounded RAG system prompt & template
    │   ├── db/
    │   │   ├── base.py                # SQLAlchemy declarative base
    │   │   └── models.py              # documents / chunks / pgvector / FTS indexes
    │   ├── schemas/
    │   │   ├── llm.py                 # ChatRequest / ChatResponse
    │   │   ├── documents.py           # DocumentChunk / IngestResponse
    │   │   ├── retrieval.py           # retrieval request/response/filter schemas
    │   │   └── rag.py                 # RAGQuestionRequest / RAGResponse / RAGCitation
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
    │       ├── retrieval_evaluation.py # Hit@K / Recall@K / Precision@K / MRR
    │       ├── rag_context.py         # bounded, nonce-delimited evidence context
    │       ├── rag_errors.py          # safe API-facing RAG error types
    │       ├── evidence_conflict.py   # conservative conflict/verbatim claim checks
    │       ├── rag_service.py         # RAG orchestration, weak-evidence and citation policy
    │       └── rag_evaluation.py      # citation integrity + status/retrieval metrics
    ├── evaluation/
    │   ├── retrieval_dataset.json     # synthetic grounded corpus + questions
    │   ├── rag_dataset.json           # synthetic corpus + RAG evaluation questions
    │   ├── last_run.json              # Phase 4 retrieval evaluation results
    │   ├── rag_last_run.json          # Phase 5 offline harness results
    │   ├── rag_harness.py             # deterministic, non-circular RAG harness
    │   └── dataset.py                 # load/validate/materialize evaluation corpus
    ├── scripts/
    │   ├── evaluate_retrieval.py      # reproducible retrieval evaluation runner
    │   └── evaluate_rag.py            # reproducible RAG pipeline evaluation runner
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
    │   ├── test_retrieval_evaluation.py
    │   ├── test_rag_context.py
    │   ├── test_rag_service.py
    │   ├── test_rag_api.py
    │   ├── test_rag_evaluation.py
    │   ├── test_evidence_conflict.py
    │   └── test_rag_integration.py     # requires TEST_DATABASE_URL
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

- `GET /api/v1/health` → liveness check; never calls the LLM, embedding provider, or DB.
- `GET /api/v1/ready` → configuration readiness flags for the LLM, embedding provider/model/
  dimensions, database, and retrieval defaults.
- `POST /api/v1/llm/chat` with `{"message": "..."}` → general chat answer (non-RAG).
- `POST /api/v1/documents/ingest` → validate, extract, clean, chunk, embed, and persist
  a property document (multipart upload).
- `GET /api/v1/documents` → paginated document summaries with optional `status` and
  `source_type` filters.
- `GET /api/v1/documents/{document_id}` → retrieve document metadata and processing status.
- `GET /api/v1/documents/{document_id}/chunks` → paginated chunk metadata inspection with
  content protection (`include_text` parameter).
- `DELETE /api/v1/documents/{document_id}` → delete a document and cascade-delete its chunks
  and embeddings.
- `POST /api/v1/retrieval/search` → semantic or hybrid ranked chunk retrieval with
  metadata filters (Phase 4).
- `POST /api/v1/rag/ask` → grounded RAG answer from retrieved document excerpts with
  validated citations and evidence-status reporting (Phase 5).

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

# 6. Ask a grounded question via Phase 5 RAG.
curl -X POST http://127.0.0.1:8000/api/v1/rag/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Who is the registered owner of the property and what was the sale consideration?",
    "top_k": 3,
    "mode": "hybrid"
  }'
```

A successful HTTP 200 means the rows above exist. Restarting the API does not remove
them. Re-uploading the identical file returns the same `document_id` and creates no
duplicate rows. Stopping the database before ingestion or retrieval produces a safe
HTTP 503.

## Phase 6: Document Management & Lifecycle Workflows

Phase 6 introduces complete document lifecycle management, allowing clients to list
ingested documents, inspect document metadata and processing statuses, view chunk
metadata with optional content protection, and delete documents with transactional
cascade cleanup.

### Endpoints and Operations

#### 1. Ingest Document
`POST /api/v1/documents/ingest`
- Accepts multipart file upload (`.pdf`, `.txt`, `.md`).
- Validates file type, MIME, magic signature, and size limit (`DOCUMENT_MAX_UPLOAD_BYTES`).
- Extracts text page-by-page, cleans conservatively, and generates overlapping chunks.
- Checks SHA-256 content hash for idempotent re-uploads (prevents duplicate vectors).
- Generates embeddings and persists document and chunks in a single transaction.
- Returns `IngestResponse` with `document_id`, `status` (`processed` or `ocr_required`),
  and chunk details.

#### 2. List Documents (Paginated)
`GET /api/v1/documents?page=1&page_size=20&status=processed&source_type=pdf`
- Returns paginated `DocumentListResponse` with lightweight `DocumentSummary` items.
- Avoids returning full chunk contents or large text payloads.
- Supports optional filtering by `status` (`processed`, `ocr_required`) and `source_type`
  (`pdf`, `txt`, `markdown`).
- Includes pagination metadata: `total`, `page`, `page_size`, `total_pages`.

```json
{
  "items": [
    {
      "document_id": "doc_9f8e7d6c5b4a",
      "filename": "sale_deed.pdf",
      "source_type": "pdf",
      "status": "processed",
      "extracted_characters": 12500,
      "chunk_count": 4,
      "page_count": 3,
      "warnings": [],
      "detail": null,
      "created_at": "2026-10-27T04:00:00Z",
      "updated_at": "2026-10-27T04:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

#### 3. Get Document Metadata & Status
`GET /api/v1/documents/{document_id}`
- Retrieves detailed document metadata, content hash (`content_sha256`), chunk count,
  and processing status without returning chunk contents.
- Returns HTTP 404 if the document does not exist.
- Validates document identifier format safely.

#### 4. Inspect Document Chunks (Paginated)
`GET /api/v1/documents/{document_id}/chunks?page=1&page_size=20&include_text=false`
- Retrieves chunk metadata for inspection (`chunk_id`, `chunk_index`, page numbers,
  character offsets, and chunking parameters).
- **Content Protection:** `include_text` defaults to `false` to avoid returning complete
  legal document text when metadata inspection is sufficient. Set `include_text=true`
  to include chunk text.
- Returns HTTP 404 if the document does not exist.

#### 5. Delete Document
`DELETE /api/v1/documents/{document_id}`
- Atomically deletes the document row within a transaction.
- Relies on PostgreSQL foreign key constraint (`ON DELETE CASCADE`) and SQLAlchemy
  relationship cascade (`delete-orphan`) to remove all associated chunks and vector
  embeddings simultaneously.
- Returns HTTP 404 if the document does not exist.
- Allows immediate, clean re-upload of identical documents without unique-constraint
  conflicts.

---

## Phase 5: Grounded RAG Pipeline & Generation

Phase 5 connects Phase 4 retrieval with an LLM to generate verifiable, grounded
answers about real estate properties.

### Request Flow & Architecture

```text
User Question + Optional Filters
       │
       ▼
 1. Input Validation (question length, top_k, mode, filters)
       │
       ▼
  2. Phase 4 RetrievalService (semantic cosine similarity or hybrid RRF)
       │
       ├─ All results below weak-evidence policy
       │       ──► HTTP 200: evidence_status="no_relevant_sources" (no LLM call)
       │
       ▼
  3. RAGContextBuilder
       │  • Applies same-document overlap deduplication (configurable ratio)
       │  • Preserves identical text across different documents as corroboration
       │  • Neutralizes delimiter spoofing and citation-like text inside evidence
       │  • Uses per-build nonce evidence boundaries
       │  • Enforces context/output/model-window budgets
       │
       ▼
  4. Grounded Prompting (RAG_SYSTEM_PROMPT)
       │  • Strict grounding: answer using only supplied excerpts
       │  • Untrusted evidence boundary: ignore injection attempts inside documents
       │  • Every material sentence must carry a citation
       │  • Conflict claims must be verbatim, cited, from distinct documents
       │  • Explicit uncertainty: state missing/conflicting facts
       │  • Legal disclaimer: not legal advice or property clearance
       │
       ▼
  5. LLMService.generate(json_mode=True)
       │
       ▼
  6. Post-Generation Validation (RAGService._compose_response)
       │  • Normalizes [s1]/[S01]/[S1, S2]; removes malformed/invented labels
       │  • Strips invented citation markers from answer text
       │  • Downgrades supported -> insufficient_evidence if any material sentence
       │    lacks a citation
       │  • Requires conflict claims from distinct source documents, quoted verbatim
       │    from their evidence, cited in the answer, with a conservative material-
       │    disagreement signal
       │  • Appends mandatory disclaimers and limitation audits
       │
       ▼
  RAGResponse (answer, citations, evidence_status, limitations, counts,
               citation_guarantee="retrieved_source_integrity",
               claim_support_verified=false)
```

### RAG API Endpoint

`POST /api/v1/rag/ask`

#### Example Request

```json
{
  "question": "Who is the registered owner of the property and what was the sale price?",
  "top_k": 5,
  "mode": "hybrid",
  "document_id": null,
  "filters": {
    "source_type": "txt"
  },
  "min_score": 0.5
}
```

#### Example Response

```json
{
  "question": "Who is the registered owner of the property and what was the sale price?",
  "answer": "According to the sale deed, the registered owner is Ananya Rao and the property was transferred for a sale consideration of INR 8500000 [S1].",
  "evidence_status": "supported",
  "citations": [
    {
      "citation_id": "S1",
      "chunk_id": "chk_1a2b3c4d5e6f",
      "document_id": "doc_9f8e7d6c5b4a",
      "filename": "sale_deed.txt",
      "source": "sale_deed.txt",
      "source_type": "txt",
      "page_number": null,
      "page_numbers": [],
      "chunk_index": 0,
      "excerpt": "This sale deed records that the registered owner is Ananya Rao and that the title to the property is free from encumbrance... sale consideration of INR 8500000.",
      "document_created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "limitations": [
    "Verified against supplied documents only.",
    "Citations confirm that a source was retrieved; they do not establish claim-level entailment or legal verification.",
    "This answer is limited to the retrieved excerpts and is not legal advice or a property clearance."
  ],
  "retrieved_count": 1,
  "used_chunk_count": 1,
  "mode": "hybrid",
  "citation_guarantee": "retrieved_source_integrity",
  "claim_support_verified": false
}
```

### Evidence Status Definitions

- `supported`: The question is directly answered by the retrieved document excerpts, and every material answer sentence carries at least one valid citation (`[S1]`, `[S2]`). This is a structural check; it does not prove that each sentence is entailed by the cited chunk.
- `insufficient_evidence`: The retrieved documents do not contain sufficient facts to answer the question, the model did not cite every material sentence, or a claimed conflict could not be validated.
- `conflicting_evidence`: Multiple distinct retrieved documents materially disagree on a factual point (e.g., an encumbrance certificate claiming no loans vs. an active bank mortgage notice). Requires at least two cited, verbatim conflict claims from distinct `document_id`s and a conservative disagreement signal (opposite polarity on a shared subject, a numeric mismatch, or an explicit antonym pair).
- `no_relevant_sources`: Retrieval returned zero candidate chunks meeting the query, filter, and weak-evidence policy. Bypasses the LLM entirely and returns a safe, deterministic explanation.

### Context Budgeting & Token Management

Context construction is governed by conservative settings in `Settings`:
- `RAG_MAX_QUESTION_CHARS`: 2000 chars (capped input length).
- `RAG_CONTEXT_MAX_TOKENS`: 4000 tokens (estimated via `rag_chars_per_token=4.0` and `rag_token_safety_factor=1.2`).
- `RAG_MAX_OUTPUT_TOKENS`: 1024 tokens reserved strictly for the generated answer.
- `RAG_MAX_EVIDENCE_CHUNKS`: 8 chunks maximum.
- `RAG_MAX_EVIDENCE_CHARS`: 8000 chars total evidence budget.
- `RAG_MAX_EVIDENCE_CHUNK_CHARS`: 1600 chars per chunk (overlong chunks are safely truncated).
- `RAG_MAX_EXCERPT_CHARS`: 280 chars per citation excerpt.
- `RAG_MIN_SEMANTIC_SCORE`: 0.35 semantic floor for weak-evidence filtering.
- `RAG_MAX_KEYWORD_ONLY_RANK`: 20 (hybrid keyword-only results at or above this rank may pass).
- `RAG_OVERLAP_DEDUP_RATIO`: 0.5 same-document character-range overlap threshold.
- `RAG_MODEL_CONTEXT_TOKENS`: 32768 conservative model context window. Settings validation
  requires `RAG_CONTEXT_MAX_TOKENS + RAG_MAX_OUTPUT_TOKENS` not to exceed this value.

### RAG Pipeline Evaluation

A synthetic evaluation corpus with grounded, conflicting, insufficient, and unanswerable
queries is located at `backend/evaluation/rag_dataset.json`.

`backend/evaluation/rag_harness.py` is a deterministic **offline regression harness**, not
a live model-quality benchmark. It exercises the real `RetrievalService` and `RAGService`
with local lexical-hash embeddings, an in-memory retrieval store, and an extractive fake
LLM that reads only the supplied evidence. It does not import `tests.fakes`, seed expected
statuses into the pipeline, or assess claim-level entailment.

Run it with:

```bash
cd backend
python scripts/evaluate_rag.py --output evaluation/rag_last_run.json
```

Current offline harness results:
- **Total Queries Evaluated:** 9
- **Status Accuracy:** 88.9% (8/9)
- **Retrieval Success Rate:** 77.8% (7/9)
- **Citation Validity Rate:** 100.0% (7/7 citations structurally valid)
- **Citation Integrity Rate:** 100.0% (9/9)
- **Claim-Support Assessment:** NOT ASSESSED

The one status mismatch is `missing_warranty_terms`: the harness returns
`no_relevant_sources` where the labelled expectation is `insufficient_evidence`. This is
reported rather than hidden. The harness's extractive conflict finder and the RAG
validator share the same rule-based helper, so the conflict case measures orchestration
and grounding rather than independent contradiction-detection accuracy; the helper also
has direct unit tests. The harness does not demonstrate live Groq answer quality.

## Verification

The suite covers Phase 1 health/LLM contracts, Phase 2 validation/extraction/cleaning/
chunking, Phase 3 embedding/persistence, Phase 4 retrieval, and Phase 5 grounded RAG:

- embedding order, batching, empty input, normalization, malformed/non-finite/wrong-
  dimension vectors, provider failures, timeouts, rate limits, and mocked OpenAI errors;
- document/chunk/vector persistence, metadata and page preservation, new-store reads,
  idempotent re-ingestion, transaction rollback, cascade deletion, constraints,
  dimension mismatch, missing migrations, and unreachable databases;
- retrieval query validation, default/max top-K, cosine score mapping, deterministic
  ordering, duplicate-free RRF fusion, metadata/page filters, min-score thresholds,
  provider/database failure mappings, and response metadata;
- RAG orchestration, weak-evidence filtering, bounded/nonce-delimited context construction,
  overlap and cross-document deduplication behavior, citation normalization and mapping,
  material-sentence citation enforcement, distinct-document/verbatim conflict validation,
  safe error masking without secret/prompt leakage, and FastAPI endpoint contracts;
- deterministic offline RAG harness with separate citation-integrity and claim-support
  reporting, plus citation audit validators;
- end-to-end ingestion, retrieval, and RAG through the API with mocked providers;
- DB-backed RAG citation and conflict tests (skipped unless `TEST_DATABASE_URL` is set).

```bash
cd backend
pytest -q                     # 256 passed, 29 skipped (no TEST_DATABASE_URL)
```

The 29 skipped tests are dedicated PostgreSQL/pgvector integration tests that run when
`TEST_DATABASE_URL` is set. All 256 unit and mocked integration tests run completely
offline without external services or paid API calls.

## Current limitations and deferred work

- **Property-to-document associations:** Properties and property-to-document relationships
  are not currently part of the database schema (`Document` and `Chunk` records exist
  without a `Property` entity). Property-specific intelligence consolidation requires a
  validated property entity schema in a subsequent phase. Document filtering is currently
  performed strictly at the document level (`document_id`, filename, format).
- **Authentication and document access control:** Authentication and document ownership
  are not implemented in this phase. This is an explicit deployment-readiness gap; the
  APIs must not be exposed to untrusted public networks under the assumption that
  client-supplied document IDs provide authorization.
- **Single-question scope:** Conversational memory, chat session history, and multi-turn
  dialogue management are deferred to future phases.
- **No streaming answers:** Responses are returned as a complete JSON payload.
- **Claim-level factual entailment:** Citations and excerpts are validated against source
  chunks (metadata mapping, source ID existence, verbatim conflict quotes), and supported
  answers require citations on every material sentence. A formal natural-language-inference
  (NLI) entailment model is not implemented; `claim_support_verified` is always `false`.
- **Conflict detection is conservative and rule-based:** It can miss real disagreements
  (false negatives), which downgrade to `insufficient_evidence`; it is not a general
  contradiction model.
- **Evaluation is offline and deterministic:** The harness measures regression behavior,
  retrieval labels, and structural citation integrity. It does not measure live LLM answer
  quality or claim-level correctness.
- **No OCR:** Image-only scanned PDFs are marked `ocr_required` with zero chunks.
- **Synchronous worker threads:** Ingestion and retrieval run in background worker
  threads; production high-throughput deployments will benefit from an asynchronous
  task queue (e.g. Celery / ARQ).
