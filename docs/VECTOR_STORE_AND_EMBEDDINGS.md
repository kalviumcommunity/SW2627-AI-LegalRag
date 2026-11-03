# Vector Store & Embedding Infrastructure

## 1. Architectural Overview

The persistence layer uses PostgreSQL 16 equipped with the `pgvector` extension. This combines relational ACID transactions, metadata filtering, and dense vector similarity search into a single unified database engine.

---

## 2. Schema Specification (`backend/app/db/models.py`)

### Table: `chunks`
| Column Name | Type | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | `PRIMARY KEY` | Deterministic/UUID chunk identifier |
| `document_id` | `VARCHAR(64)` | `FK -> documents.id ON DELETE CASCADE` | Associated document foreign key |
| `chunk_index` | `INTEGER` | `NOT NULL, CHECK (chunk_index >= 0)` | 0-based sequence within document |
| `text` | `TEXT` | `NOT NULL` | Cleaned text content |
| `source_filename` | `VARCHAR(255)` | `NOT NULL` | Original file name |
| `source_type` | `VARCHAR(16)` | `NOT NULL` | `pdf`, `txt`, or `md` |
| `page_number` | `INTEGER` | `NULLABLE, CHECK (>= 1)` | 1-based source page number |
| `start_offset` | `INTEGER` | `NULLABLE, CHECK (>= 0)` | Start character offset |
| `end_offset` | `INTEGER` | `NULLABLE, CHECK (>= 0)` | End character offset |
| `metadata` | `JSONB` | `NOT NULL, DEFAULT '{}'` | Extensible metadata |
| `embedding` | `vector(768)` | `NOT NULL` | Dense embedding vector |

### Table Constraints
- `uq_chunks_document_id_chunk_index`: Unique constraint on `(document_id, chunk_index)`.

---

## 3. High-Performance Indexing Strategy

### 3.1 Approximate Nearest Neighbor (HNSW) Index
Dense semantic similarity uses Hierarchical Navigable Small World (HNSW) graphs:
```sql
CREATE INDEX ix_chunks_embedding_hnsw 
ON chunks 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);
```
- **Distance Metric**: Cosine distance (`vector_cosine_ops`).
- `m = 16`: Number of bidirectional links per node.
- `ef_construction = 64`: Size of the dynamic candidate list during graph construction.

### 3.2 Full-Text Search (GIN) Index
Keyword search uses PostgreSQL Generalized Inverted Indexes:
```sql
CREATE INDEX ix_chunks_text_fts 
ON chunks 
USING gin (to_tsvector('english', text));
```

---

## 4. Embedding Generation Service (`embedding_service.py`)

- **Model Dimensions**: 768 dimensions (defaults to local SentenceTransformers or Groq/FastAPI embedding providers).
- **Dimension Guard**: A runtime assertion verifies that the embedding output size matches `SCHEMA_VECTOR_DIMENSIONS` before committing to avoid silent truncation or driver crashes.
- **Normalization**: Vectors are $L_2$-normalized prior to storage:
  $$\hat{\mathbf{v}} = \frac{\mathbf{v}}{\|\mathbf{v}\|_2}$$
  This ensures cosine similarity aligns with the inner product.
- **Batch Processing**: Embedded in batches (default: 32 chunks per call) to maximize throughput and respect API rate limits.
