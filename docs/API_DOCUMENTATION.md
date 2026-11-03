# REST API Specification Reference

This document provides complete documentation of the REST endpoints exposed by the FastAPI application.

## 1. Health and System Endpoints

### `GET /health`
Liveness check returning process status.
- **Response**: `{"status": "ok", "version": "1.0.0"}`

### `GET /ready`
Readiness check verifying database and embedding provider connectivity.
- **Response**: `{"status": "ready", "database": "connected", "embeddings": "ready"}`

---

## 2. Ingestion Endpoints

### `POST /api/v1/documents/ingest`
Uploads and processes legal documents (PDF, TXT, MD).
- **Multipart Form Data**:
  - `file`: UploadFile (required)
  - `property_id`: UUID (optional)
- **Response**:
```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "deed_of_sale.pdf",
  "chunk_count": 14,
  "status": "PROCESSED"
}
```

---

## 3. Retrieval Endpoints

### `POST /api/v1/retrieval/search`
Executes semantic or hybrid retrieval over ingested documents.
- **Request Body**:
```json
{
  "query": "Who is the registered owner in the encumbrance certificate?",
  "top_k": 5,
  "document_id": null,
  "property_id": "b719468e-4a6f-47dc-9d41-356a88b8cc78",
  "similarity_threshold": 0.65
}
```
- **Response**: Array of ranked chunk objects with metadata and score.

---

## 4. Grounded RAG Endpoints

### `POST /api/v1/rag/ask`
Asks a question grounded strictly in property documents.
- **Request Body**:
```json
{
  "query": "Is there any outstanding legal dispute mentioned?",
  "property_id": "b719468e-4a6f-47dc-9d41-356a88b8cc78"
}
```
- **Response**:
```json
{
  "answer": "According to the encumbrance report, no court stay or dispute is recorded [S1].",
  "evidence_status": "supported",
  "citations": [
    {
      "citation_id": "S1",
      "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "page_number": 3,
      "text": "..."
    }
  ]
}
```
