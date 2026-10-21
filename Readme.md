# Property Intelligence Platform — Phases 1–2 (Sprint 2)

AI-powered Real Estate Property Intelligence Platform. Buyers currently cannot get
trustworthy, consolidated answers about a property without manually cross-checking
listings, legal documents, and locality reports. The full platform will add document
processing, embeddings, vector retrieval, and RAG-grounded reports.

**Phase 1:** a tested FastAPI foundation — centralized configuration, health/readiness
endpoints, and a general (non-RAG) LLM chat endpoint backed by Groq. Chat answers are
**general explanations only** and are **not** grounded in property documents.

**Phase 2 (this implementation):** safe document ingestion for PDF, TXT, and Markdown —
validation, page-aware text extraction, conservative cleaning, configurable overlapping
chunking, and traceable chunk metadata exposed through `POST /api/v1/documents/ingest`.

Phase 2 explicitly does **not** implement embeddings, vector databases, semantic search,
hybrid retrieval, RAG answer generation, discrepancy detection, a frontend, or deployment.
Uploaded documents and generated chunks are **not persisted**: chunks are returned in the
HTTP response and are lost when the request completes.

## Repository layout

```text
.
├── Readme.md
├── .gitignore
└── backend/
    ├── app/
    │   ├── main.py                    # FastAPI entry point (create_app factory + app)
    │   ├── api/routes/
    │   │   ├── health.py              # GET /health, GET /ready
    │   │   ├── llm.py                 # POST /llm/chat
    │   │   └── documents.py           # POST /documents/ingest
    │   ├── core/
    │   │   ├── config.py              # Pydantic Settings (LLM + ingestion)
    │   │   └── prompt.py              # Phase 1 system prompt
    │   ├── schemas/
    │   │   ├── llm.py                 # ChatRequest / ChatResponse
    │   │   └── documents.py           # DocumentChunk / IngestResponse
    │   └── services/
    │       ├── llm_service.py         # Groq (OpenAI-compatible) wrapper
    │       ├── document_validation.py # filename/MIME/signature/size checks
    │       ├── text_extraction.py     # PDF / TXT / Markdown extractors
    │       ├── text_cleaning.py       # conservative normalization
    │       ├── chunking.py            # character-based overlapping chunks
    │       ├── temp_storage.py        # secure temp files + guaranteed cleanup
    │       ├── ingestion_errors.py    # safe API-facing error types
    │       └── document_ingestion.py  # pipeline orchestration
    ├── tests/
    │   ├── conftest.py
    │   ├── pdf_factory.py             # synthetic PDF fixtures (no external services)
    │   ├── test_health.py
    │   ├── test_llm.py
    │   ├── test_chunking.py
    │   └── test_documents.py
    ├── requirements.txt
    ├── pytest.ini
    ├── .env.example                   # placeholder values only, never real secrets
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

Run the tests (from the `backend/` directory; the LLM provider is mocked, so no API key
or paid calls are needed):

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
- `POST /api/v1/documents/ingest` → structured ingestion result (below).

## Document ingestion (Phase 2)

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
  `status: "ocr_required"` (HTTP 200) with zero chunks and an explanatory warning.
  OCR itself is **not implemented** in Phase 2.
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
inventing a single page. Non-paginated formats omit page fields.

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

- `processed` — text extracted, cleaned, and chunked (HTTP 200).
- `ocr_required` — a PDF was accepted but has no extractable text (HTTP 200, zero chunks).
- `failed` — extraction failed, e.g. encrypted or malformed PDF (HTTP 422 with the same
  structured response schema and a safe `detail`).

Validation errors use the standard FastAPI `{"detail": "..."}` shape:

| Condition | HTTP status |
|---|---|
| Empty upload, invalid signature/binary content, invalid encoding, no readable text | `400` |
| Upload exceeds `DOCUMENT_MAX_UPLOAD_BYTES` | `413` |
| Unsupported extension or mismatched MIME type | `415` |
| Missing multipart `file` field | `422` |
| Encrypted/malformed PDF or other extraction failure | `422` (`status: "failed"`) |
| Temporary storage/internal failure | `500` with a safe message |

Responses never include stack traces, filesystem paths, or document contents in error
messages. The server does not log complete document text.

### Persistence limitation

There is no database or durable document store in Phases 1–2. The ingestion response is
the only copy of the chunks; a server restart loses them. Phase 3 is expected to consume
the chunk objects/service directly for embedding and indexing; a durable store can be
added then using the project's conventions.

## Verification

The test suite covers TXT/Markdown/PDF ingestion, page-number preservation, identifiers,
chunk size/overlap, empty and whitespace-only inputs, invalid extensions/content/MIME/
encoding, upload limits, encrypted and malformed PDFs, OCR-required PDFs, filename
sanitization/path traversal, temp-file cleanup after success and failure, response schema
stability, and the Phase 1 health/LLM regressions.

```bash
cd backend
pytest -q
```

Phase 1 functionality is unchanged: `GET /health`, `GET /ready`, and `POST /llm/chat`
retain their contracts, and the LLM is still mocked in tests.
