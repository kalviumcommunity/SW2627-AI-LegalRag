# Configuration and Environment Variables Reference

This document provides a comprehensive reference for all configuration options defined in `app/core/config.py` and populated via `.env`.

## 1. Environment Variables Table

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | string | `Property Intelligence Platform` | Name displayed in OpenAPI documentation |
| `ENVIRONMENT` | string | `development` | Deployment environment (`development`, `staging`, `production`) |
| `DATABASE_URL` | string | (Required) | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `GROQ_API_KEY` | string | (Required) | API Key for Groq Cloud LLM inferencing |
| `LLM_MODEL` | string | `llama-3.3-70b-versatile` | Underlying LLM model for grounded generation |
| `EMBEDDING_PROVIDER` | string | `fastembed` | Embedding backend provider (`fastembed`, `huggingface`, `openai`) |
| `EMBEDDING_MODEL` | string | `BAAI/bge-small-en-v1.5` | Embedding model identifier |
| `EMBEDDING_DIMENSIONS`| integer | `384` | Dimensionality of stored vector representations |
| `CHUNK_SIZE` | integer | `500` | Target character size for text chunks |
| `CHUNK_OVERLAP` | integer | `50` | Overlap character size between adjacent chunks |
| `RETRIEVAL_TOP_K` | integer | `5` | Default number of candidate chunks retrieved |
| `SIMILARITY_THRESHOLD`| float | `0.65` | Minimum cosine similarity cut-off score |
| `HYBRID_SEARCH_ENABLED`| boolean| `true` | Toggle for combining semantic search with Postgres full-text search |
| `RRF_K` | integer | `60` | Dampening constant for Reciprocal Rank Fusion |
| `JWT_SECRET` | string | `changeme-secret` | Cryptographic secret for signing auth tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| integer | `60` | Session token validity duration in minutes |
