# Retrieval Strategy and Ranking Pipeline

This document outlines the hybrid retrieval architecture, similarity metrics, and ranking fusion implemented in the Real Estate Property Intelligence Platform.

## 1. Overview

The retrieval subsystem (`app/services/retrieval_service.py` and `app/services/retrieval_store.py`) provides relevant context retrieval from ingested legal property documents to support grounded question answering.

The engine supports two primary retrieval modes:
1. **Dense Vector Retrieval (Semantic)**: Utilizing cosine distance over pgvector representations.
2. **Hybrid Retrieval**: Combining dense semantic similarity with sparse lexical matching (PostgreSQL Full-Text Search) using Reciprocal Rank Fusion (RRF).

---

## 2. Dense Semantic Retrieval

- **Embedding Model**: Text chunks are embedded into high-dimensional vector spaces using configurable providers (e.g., FastEmbed, HuggingFace, OpenAI).
- **Distance Metric**: Cosine similarity (`<=>` operator in pgvector).
- **Filtering**: Queries can be scoped by:
  - `document_id`: Restricting retrieval to a specific document.
  - `property_id`: Restricting search across all documents linked to a particular property.
  - `similarity_threshold`: Discarding chunks below a confidence score (e.g., minimum 0.65 similarity).

```sql
SELECT 
    c.id, c.document_id, c.chunk_index, c.page_number, c.text,
    1 - (c.embedding <=> :query_embedding) AS similarity
FROM chunks c
WHERE (:document_id IS NULL OR c.document_id = :document_id)
  AND (1 - (c.embedding <=> :query_embedding)) >= :threshold
ORDER BY c.embedding <=> :query_embedding ASC
LIMIT :top_k;
```

---

## 3. Sparse Lexical Search (PostgreSQL FTS)

To prevent failures on domain-specific terminology, property registration numbers, survey numbers, and legal codes, PostgreSQL Full-Text Search (GIN indexed) is executed alongside dense search:

- Language dictionary: `english` tsvector configuration.
- Query parser: `plainto_tsquery` or `websearch_to_tsquery`.
- Relevance ranking: `ts_rank_cd` with term frequency normalization.

---

## 4. Reciprocal Rank Fusion (RRF)

When hybrid retrieval is enabled, results from semantic search ($R_{sem}$) and lexical search ($R_{lex}$) are unified without requiring score normalization:

$$RRF\_Score(d) = \sum_{m \in \{sem, lex\}} \frac{1}{k + rank_m(d)}$$

Where $k$ is a constant dampening factor (default: $60$).

### Selection Process:
1. Fetch top $2 \times K$ candidates from dense retrieval.
2. Fetch top $2 \times K$ candidates from lexical retrieval.
3. Compute combined RRF score for each unique chunk.
4. Sort by score descending and return the top $K$ chunks.
