# Database Schema and Migrations Guide

This document describes the relational and vector database schema managed via Neon PostgreSQL and SQLAlchemy/Alembic.

## 1. Tables Overview

The platform uses PostgreSQL with the `pgvector` extension for storing structured property records, document metadata, chunks, and embeddings.

### `properties`
Stores physical and legal entities representing real estate parcels.
- `id` (UUID, Primary Key)
- `title` (VARCHAR(255))
- `address` (TEXT)
- `locality` (VARCHAR(100))
- `city` (VARCHAR(100))
- `pincode` (VARCHAR(20))
- `created_at` (TIMESTAMP WITH TIME ZONE)
- `updated_at` (TIMESTAMP WITH TIME ZONE)

### `documents`
Stores metadata and ingestion status for uploaded documents.
- `id` (UUID, Primary Key)
- `property_id` (UUID, Foreign Key -> `properties.id`, Nullable)
- `filename` (VARCHAR(255))
- `file_type` (VARCHAR(50)) -- PDF, TXT, MD
- `file_hash` (VARCHAR(64), Unique SHA-256 for idempotency)
- `page_count` (INTEGER)
- `status` (VARCHAR(50)) -- PENDING, PROCESSED, FAILED
- `created_at` (TIMESTAMP WITH TIME ZONE)

### `chunks`
Contains decomposed document text fragments and their vector embeddings.
- `id` (UUID, Primary Key)
- `document_id` (UUID, Foreign Key -> `documents.id`, ON DELETE CASCADE)
- `chunk_index` (INTEGER)
- `page_number` (INTEGER)
- `start_char` (INTEGER)
- `end_char` (INTEGER)
- `text` (TEXT)
- `embedding` (VECTOR(384) or configurable dimensions)
- `search_vector` (TSVECTOR for PostgreSQL full-text search)

---

## 2. Indexes and Optimization

- **Vector Index**: IVFFlat or HNSW cosine index on `chunks.embedding`.
- **Full-Text Index**: GIN index on `chunks.search_vector` for lexical queries.
- **Foreign Key Indexes**: B-tree index on `chunks.document_id` and `documents.property_id`.

---

## 3. Running Migrations

Database migrations are managed using Alembic:
```bash
# Apply migrations to latest revision
alembic upgrade head

# Generate a new migration revision
alembic revision --autogenerate -m "add_table_or_column"
```
