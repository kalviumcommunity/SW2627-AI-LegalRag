# System Architecture: AI Property & Legal RAG Platform

## 1. Executive Overview

The **Property Intelligence & Legal RAG Platform** is an enterprise-grade retrieval-augmented generation system designed to parse, index, search, and synthesize legal statutes, title deeds, environmental reports, and property agreements. 

Traditional language models suffer from hallucinations and lack domain-specific grounding when analyzing dense legal contracts. This platform resolves these issues through a strictly verified RAG architecture featuring:
- **Transactional Ingestion**: Multi-format document parsing with page-aware metadata.
- **Hybrid Retrieval**: Dense vector embeddings combined with PostgreSQL Full-Text Search (FTS) fused via Reciprocal Rank Fusion (RRF).
- **Grounded Generation**: Nonce-delimited context injection, strict system prompts, citation preservation (`[S1]`, `[S2]`), and automated evidence conflict resolution.
- **Granular Authorization & Auditability**: Property-level scoping and role-based document access controls.

---

## 2. High-Level System Architecture Diagram

```
                              ┌────────────────────────────────────────┐
                              │         React + Vite Frontend          │
                              │  (Dashboard, Intelligence, Due Diligence)│
                              └───────────────────┬────────────────────┘
                                                  │ HTTP / REST
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │           FastAPI Gateway              │
                              │ (CORS, Auth, Exception Handlers, DI)   │
                              └───────┬───────────────┬────────────────┘
                                      │               │
                 ┌────────────────────┴─────┐   ┌─────┴──────────────────┐
                 │ Ingestion & Pipeline Svc │   │  RAG & Retrieval Svc   │
                 └────────────┬─────────────┘   └─────────────┬──────────┘
                              │                               │
        ┌─────────────────────┼───────────────────────────────┼─────────────────────┐
        ▼                     ▼                               ▼                     ▼
┌──────────────┐     ┌────────────────┐              ┌────────────────┐     ┌──────────────┐
│ Text Extract │     │ Embedding Svc  │              │ Hybrid Ranker  │     │ Groq LLM Svc │
│  (PDF/TXT/MD)│     │(sentence-tf/API│              │ (pgvector+FTS) │     │ (Llama/Mixtr)│
└──────────────┘     └────────────────┘              └────────────────┘     └──────────────┘
        │                     │                               │                     ▲
        └──────────────┬──────┴───────────────────────────────┴─────────────────────┤
                       ▼                                                            │
         ┌─────────────────────────────────────────────────────────┐                │
         │             Neon / PostgreSQL 16 Database               │                │
         │  - documents (metadata, checksums, mime types)          │                │
         │  - chunks (text, tokens, offsets, page references)      │                │
         │  - pgvector HNSW index (cosine similarity search)       │                │
         │  - GIN tsvector index (full-text search)                │                │
         └─────────────────────────────────────────────────────────┘                │
                                      │                                             │
                                      └───────────── Context Chunks ────────────────┘
```

---

## 3. Core Subsystems

### 3.1 API & Application Gateway (`backend/app/main.py`)
- **FastAPI Core**: Asynchronous application factory pattern with centralized Pydantic settings.
- **Exception Handlers**: Maps domain errors (`LLMTimeoutError`, `RetrievalError`, `DocumentIngestionError`) to standardized, safe HTTP status codes (400, 401, 403, 404, 429, 502, 503, 504).
- **Middleware**: Configurable CORS handling supporting wildcards and explicit production origins.

### 3.2 Ingestion Engine (`backend/app/services/document_ingestion.py`)
- **Security & Validation**: Enforces MIME-type verification, byte signature (magic number) checking, file extension validation, and strict size boundaries (max 10MB per document).
- **Format Parsers**: Dedicated parsers for PDF (`pypdf`), UTF-8 TXT, and CommonMark Markdown.
- **Deterministic Checksumming**: SHA-256 content hashing guarantees idempotency. Re-uploading an existing identical document returns existing records without re-embedding.

### 3.3 Storage & Persistence (`backend/app/db/models.py`)
- **Relational Schema**: Relational models for `Document`, `DocumentChunk`, `Property`, and user authorization mappings.
- **Vector Indexing**: Integrated with `pgvector` storing 384/768/1536-dimensional embeddings with HNSW cosine distance indexes.
- **Full-Text Indexing**: GIN indexes over `tsvector` columns enabling lexical keyword search.

### 3.4 Hybrid Retrieval & Fusion (`backend/app/services/retrieval_service.py`)
- **Dual Retrieval Path**: Executes dense vector cosine similarity and sparse keyword FTS queries in parallel.
- **Reciprocal Rank Fusion (RRF)**: Merges disparate rank scores using standard RRF formula:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  where $k=60$ mitigates outlier bias across dense and sparse ranking models.

### 3.5 Grounded LLM & Synthesis (`backend/app/services/rag_service.py`)
- **Context Construction**: Assembles deduplicated, ordered chunks into a bounded token budget.
- **Nonce Delimiters**: Inserts dynamic UUID nonces around context blocks to eliminate prompt injection risks from untrusted document contents.
- **Citation Extraction**: Validates that all assertions in generated outputs correspond to exact retrieved source IDs (`[S1]`, `[S2]`).
- **Evidence Verification**: Categorizes results into `supported`, `insufficient_evidence`, `conflicting_evidence`, or `no_relevant_sources`.

---

## 4. Security & Compliance
1. **Zero Raw Leakage**: Chunk queries can suppress raw text payloads via `include_text=False` to protect PII.
2. **Cascading Deletion**: Deleting a document executes a transactional cascade removing chunks, vectors, and property associations.
3. **No Claim Hallucination**: Strict fallback directives trigger `insufficient_evidence` when retrieval similarity falls below confidence thresholds.
