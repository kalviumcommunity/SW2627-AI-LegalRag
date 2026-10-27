"""PostgreSQL/pgvector RAG integration tests.

These tests use real ingestion, persistence, retrieval, and RAG orchestration.
Only the embedding provider and LLM are deterministic test doubles. They are
skipped unless TEST_DATABASE_URL points at a dedicated pgvector database.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from app.core.config import Settings
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_store import SqlAlchemyDocumentStore
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_store import SqlAlchemyRetrievalStore
from app.services.rag_service import RAGService
from tests.fakes import FakeEmbeddingProvider, FakeLLMService

DIMENSIONS = 768


def _database_url(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def _settings(engine, **overrides) -> Settings:
    values = {
        "database_url": _database_url(engine),
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": DIMENSIONS,
        "document_chunk_size_chars": 10000,
        "document_chunk_overlap_chars": 0,
        "retrieval_default_top_k": 3,
        "retrieval_max_top_k": 5,
        "rag_max_evidence_chunks": 3,
    }
    values.update(overrides)
    return Settings(**values)


def _vector() -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[0] = 1.0
    return vector


def _embedding_service(settings: Settings) -> EmbeddingService:
    return EmbeddingService(
        settings,
        provider=FakeEmbeddingProvider(
            dimensions=DIMENSIONS,
            vectors=[_vector()],
        ),
    )


def _ingest(
    engine,
    settings: Settings,
    filename: str,
    content: str,
) -> str:
    document_store = SqlAlchemyDocumentStore(settings, engine=engine)
    ingestion = DocumentIngestionService(
        settings,
        embedding_service=_embedding_service(settings),
        store=document_store,
    )
    response = ingestion.ingest(
        content.encode("utf-8"),
        filename,
        "text/plain",
    )
    assert response.status == "processed"
    assert response.chunk_count == 1
    return response.document_id


def _retrieval_service(engine, settings: Settings) -> RetrievalService:
    return RetrievalService(
        settings,
        embedding_service=_embedding_service(settings),
        store=SqlAlchemyRetrievalStore(settings, engine=engine),
    )


def _assert_citation_is_stored(engine, citation) -> None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT document_id, text FROM chunks "
                "WHERE chunk_id = :chunk_id"
            ),
            {"chunk_id": citation.chunk_id},
        ).one()
    assert row.document_id == citation.document_id
    assert " ".join(row.text.split())


async def test_rag_citations_match_persisted_chunks_and_retrieval(clean_database):
    settings = _settings(clean_database)
    first_id = _ingest(
        clean_database,
        settings,
        "sale_deed.txt",
        "The sale deed records that the registered owner is Ananya Rao.",
    )
    second_id = _ingest(
        clean_database,
        settings,
        "locality_report.txt",
        "The metro station is two kilometres from the property.",
    )
    retrieval = _retrieval_service(clean_database, settings)
    expected = retrieval.search(
        "Who is the registered owner?",
        top_k=3,
    ).response.results
    assert len(expected) == 2

    llm = FakeLLMService(
        response=json.dumps(
            {
                "answer": "The registered owner is Ananya Rao [S1].",
                "evidence_status": "supported",
                "used_source_ids": [1],
                "limitations": [],
            }
        )
    )
    service = RAGService(
        settings,
        retrieval_service=retrieval,
        llm_service=llm,
    )

    response = await service.ask("Who is the registered owner?")

    assert response.evidence_status == "supported"
    assert len(response.citations) == 1
    citation = response.citations[0]
    assert citation.chunk_id == expected[0].chunk_id
    assert citation.document_id == expected[0].document_id
    assert citation.document_id in {first_id, second_id}
    assert citation.filename == expected[0].metadata.filename
    _assert_citation_is_stored(clean_database, citation)
    assert response.claim_support_verified is False


async def test_db_backed_conflict_requires_distinct_documents(clean_database):
    settings = _settings(clean_database)
    _ingest(
        clean_database,
        settings,
        "valuation_2023.txt",
        "The property has 3 floors.",
    )
    _ingest(
        clean_database,
        settings,
        "valuation_2024.txt",
        "The property has 4 floors.",
    )
    retrieval = _retrieval_service(clean_database, settings)
    results = retrieval.search("How many floors?", top_k=3).response.results
    assert len(results) == 2
    assert results[0].document_id != results[1].document_id

    first, second = results
    llm = FakeLLMService(
        response=json.dumps(
            {
                "answer": (
                    "The two documents report different floor counts "
                    "[S1][S2]."
                ),
                "evidence_status": "conflicting_evidence",
                "used_source_ids": [1, 2],
                "conflict_claims": [
                    {"source_id": "S1", "claim": first.text},
                    {"source_id": "S2", "claim": second.text},
                ],
                "limitations": [],
            }
        )
    )
    service = RAGService(
        settings,
        retrieval_service=retrieval,
        llm_service=llm,
    )

    response = await service.ask("How many floors?")

    assert response.evidence_status == "conflicting_evidence"
    assert [citation.citation_id for citation in response.citations] == [
        "S1",
        "S2",
    ]
    assert (
        response.citations[0].document_id
        != response.citations[1].document_id
    )
    for citation in response.citations:
        _assert_citation_is_stored(clean_database, citation)


async def test_db_backed_rag_weak_evidence_and_insufficient_handling(clean_database):
    """Database-backed test verifying weak-evidence refusal through real retrieval store."""
    settings = _settings(clean_database, rag_min_semantic_score=0.99)
    _ingest(
        clean_database,
        settings,
        "property_deed.txt",
        "The property is located in Bengaluru with residential zoning.",
    )
    retrieval = _retrieval_service(clean_database, settings)
    llm = FakeLLMService(response="Should not be called")
    service = RAGService(
        settings,
        retrieval_service=retrieval,
        llm_service=llm,
    )

    # Search with an orthogonal or low-similarity question that fails the 0.99 floor
    response = await service.ask("What is the commercial rental yield in Mumbai?")

    assert response.evidence_status == "no_relevant_sources"
    assert response.citations == []
    assert len(llm.calls) == 0
    assert any("relevance policy" in item for item in response.limitations)
