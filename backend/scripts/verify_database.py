"""Safe database verification script for Neon PostgreSQL.

Verifies:
1. Connection to PostgreSQL via the normalized URL
2. Execution of a simple query (SELECT 1)
3. Availability and version of pgvector extension
4. Existence of documents and chunks tables
5. Existence of vector HNSW index and full-text search GIN index
6. Embedding dimension alignment (768)

Does NOT print or log credentials, connection strings, or sensitive data.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.document_store import verify_database_connectivity


def main() -> int:
    settings = get_settings()
    report = verify_database_connectivity(settings)

    print("=" * 60)
    print("NEON POSTGRESQL VERIFICATION REPORT")
    print("=" * 60)
    print(f"Provider: {'Neon Cloud PostgreSQL' if report.get('is_neon') else 'PostgreSQL'}")
    print(f"Connection mode: {'Pooled (-pooler)' if report.get('is_pooled') else 'Direct'}")
    print(f"Simple query (SELECT 1): {'PASS' if report.get('simple_query') else 'FAIL'}")
    print(f"pgvector extension: {'INSTALLED (' + str(report.get('pgvector_version')) + ')' if report.get('pgvector_installed') else 'MISSING'}")
    print(f"Tables exist (documents, chunks): {'PASS' if report.get('tables_exist') else 'FAIL'}")
    print(f"Tables present: {report.get('tables', [])}")
    print(f"Embedding dimensions: {report.get('embedding_dimensions')}")
    print(f"Indexes (HNSW + FTS GIN): {'PASS' if report.get('indexes_verified') else 'FAIL'}")
    print(f"Overall status: {report.get('status').upper()}")
    print(f"Summary: {report.get('message')}")
    print("=" * 60)

    if report.get("status") == "healthy":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
