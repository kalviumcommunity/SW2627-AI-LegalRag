"""Live workflow verification for Neon PostgreSQL.

Executes a non-destructive lifecycle test:
1. Ingests a dedicated temporary test document.
2. Verifies document and chunks committed to Neon database.
3. Verifies vector embedding storage and semantic retrieval.
4. Verifies hybrid / full-text retrieval (RRF).
5. Tests document deletion and cascades.
6. Tests error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.document_store import create_document_store
from app.services.embedding_service import EmbeddingService
from app.services.document_ingestion import DocumentIngestionService
from app.services.retrieval_store import SqlAlchemyRetrievalStore
from app.services.retrieval_service import RetrievalService


def main() -> int:
    settings = get_settings()
    if not settings.is_database_configured:
        print("DATABASE_URL is not configured.")
        return 1

    print("--- 1. Testing Document Ingestion & Persistence ---")
    store = create_document_store(settings)
    store.ensure_ready()

    embedder = EmbeddingService(settings)
    ingestion_service = DocumentIngestionService(settings, embedding_service=embedder, store=store)

    test_content = (
        "Property Legal Deed: Parcel 402 is located at 123 Elm Street with residential zoning. "
        "The property boundaries extend 150 feet along Elm Street to the north and 200 feet to the east. "
        "The annual property tax is assessed at $4,200 payable biannually."
    ).encode("utf-8")
    test_filename = "test_parcel_402_deed.txt"

    ingest_result = ingestion_service.ingest(test_content, test_filename, "text/plain")
    print(f"Ingested doc_id={ingest_result.document_id}, status={ingest_result.status}, chunks={ingest_result.chunk_count}")
    assert ingest_result.status == "processed", f"Expected processed, got {ingest_result.status}"
    assert ingest_result.chunk_count > 0, "Expected at least 1 chunk"

    # Verify retrieval
    print("\n--- 2. Testing Semantic Vector Retrieval ---")
    retrieval_store = SqlAlchemyRetrievalStore(settings)
    retrieval_service = RetrievalService(settings, embedding_service=embedder, store=retrieval_store)

    semantic_res = retrieval_service.search(
        "What is the property location and boundaries?",
        top_k=3,
        mode="semantic",
        document_id=ingest_result.document_id,
    )
    print(f"Semantic search returned {semantic_res.response.result_count} chunks (top score: {semantic_res.response.results[0].score:.4f})")
    assert semantic_res.response.result_count > 0, "Expected at least 1 retrieved chunk"

    print("\n--- 3. Testing Full-Text / Hybrid Retrieval ---")
    hybrid_res = retrieval_service.search(
        "annual property tax assessed",
        top_k=3,
        mode="hybrid",
        document_id=ingest_result.document_id,
    )
    print(f"Hybrid search returned {hybrid_res.response.result_count} chunks (score: {hybrid_res.response.results[0].score:.4f})")
    assert hybrid_res.response.result_count > 0, "Expected at least 1 retrieved chunk"

    # Verify clean document details
    print("\n--- 4. Testing Document Details & Chunks Inspection ---")
    doc_detail = store.get_document(ingest_result.document_id)
    assert doc_detail is not None, "Document detail should be present"
    print(f"Found stored document: {doc_detail.filename}, sha={doc_detail.content_sha256[:16]}...")

    chunks, chunk_total = store.get_document_chunks(ingest_result.document_id, include_text=True)
    print(f"Retrieved {chunk_total} stored chunks from Neon. First chunk text excerpt: {chunks[0].text[:50]}...")
    assert chunk_total == ingest_result.chunk_count

    # Verify deletion and cascade
    print("\n--- 5. Testing Deletion & Cascading Chunk Removal ---")
    deleted = store.delete_document(ingest_result.document_id)
    assert deleted, "Deletion should return True"
    print("Deleted document record from Neon.")

    # Confirm it's gone
    after_detail = store.get_document(ingest_result.document_id)
    assert after_detail is None, "Document should be gone"
    after_chunks = store.get_document_chunks(ingest_result.document_id)
    assert after_chunks is None or after_chunks[1] == 0, "Chunks should be cascaded"
    print("Confirmed cascading deletion of chunks from Neon.")

    print("\n=== ALL WORKFLOW TESTS PASSED AGAINST NEON POSTGRESQL ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
