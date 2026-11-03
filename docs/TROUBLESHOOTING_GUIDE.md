# Troubleshooting and Operational Diagnostics

Common issues, root cause analyses, and solutions encountered when maintaining the Legal RAG Property Intelligence Platform.

## 1. Database & pgvector Issues

### `Extension "vector" does not exist`
- **Cause**: The PostgreSQL instance lacks the pgvector shared library.
- **Solution**:
  - In Neon / Cloud: Neon has `vector` enabled by default. Run `CREATE EXTENSION IF NOT EXISTS vector;`
  - In Local Docker: Ensure you are running `pgvector/pgvector:pg16` rather than plain `postgres:16`.

### `Dimensions mismatch error on embedding insert`
- **Cause**: The embedding model dimensions (e.g. 1536 from OpenAI) do not match the database column definition (`VECTOR(384)`).
- **Solution**: Update `EMBEDDING_DIMENSIONS` in `.env` and generate a migration adjusting the column type.

---

## 2. Ingestion Failures

### `Unrecognized file signature / MIME type rejected`
- **Cause**: Uploaded file extension does not match its internal magic bytes (e.g., an HTML file renamed to `.pdf`).
- **Solution**: The file validation service (`app/services/document_validation.py`) enforces magic byte checking to prevent security exploits. Ensure only genuine PDF, TXT, or MD files are submitted.

### `Empty text extracted from scanned PDF`
- **Cause**: The PDF consists solely of raster image scans without embedded text layers.
- **Solution**: Enable the OCR processing path (`ENABLE_OCR=true`) to invoke Tesseract OCR parsing.

---

## 3. RAG Generation Anomalies

### Response returns `insufficient_evidence`
- **Cause**: The cosine similarity between the question and document chunks fell below `SIMILARITY_THRESHOLD`.
- **Solution**: Lower `SIMILARITY_THRESHOLD` from `0.65` to `0.55` in `.env`, or re-chunk documents with smaller chunk size and higher overlap.
