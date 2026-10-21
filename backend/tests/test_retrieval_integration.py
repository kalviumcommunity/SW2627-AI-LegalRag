"""PostgreSQL/pgvector retrieval integration tests.

Requires TEST_DATABASE_URL. Embedding calls are mocked with deterministic
vectors; no external provider is contacted.
"""

from __future__ import annotations

import hashlib
import math

import pytest

from app.core.config import Settings
from app.schemas.documents import DocumentChunk, IngestResponse
from app.services.document_store import SqlAlchemyDocumentStore
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_errors import RetrievalConfigurationError
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_store import SqlAlchemyRetrievalStore
from tests.fakes import FakeEmbeddingProvider

DIMENSIONS = 768


def _database_url(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def _settings(engine, **overrides) -> Settings:
    values = {
        "database_url": _database_url(engine),
        "embedding_provider": "fastembed",
        "embedding_model": "fake-model",
        "embedding_dimensions": DIMENSIONS,
        "retrieval_default_top_k": 3,
        "retrieval_max_top_k": 10,
        "retrieval_hybrid_candidate_limit": 10,
    }
    values.update(overrides)
    return Settings(**values)


def _vector(dimension: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[dimension] = 1.0
    return vector


def _blend(first: int, second: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[first] = 1.0
    vector[second] = 1.0
    norm = math.sqrt(2.0)
    return [value / norm for value in vector]


def _chunk(
    document_id: str,
    index: int,
    text: str,
    filename: str,
    source_type: str,
    *,
    page_number: int | None = None,
    page_numbers: list[int] | None = None,
) -> DocumentChunk:
    metadata = {"character_count": len(text)}
    if page_numbers:
        metadata["page_numbers"] = page_numbers
    return DocumentChunk(
        chunk_id=f"chk_{document_id}_{index}",
        document_id=document_id,
        chunk_index=index,
        text=text,
        source_filename=filename,
        source_type=source_type,
        page_number=page_number,
        start_offset=index * 100,
        end_offset=index * 100 + len(text),
        metadata=metadata,
    )


def _save_document(
    store: SqlAlchemyDocumentStore,
    *,
    document_id: str,
    filename: str,
    source_type: str,
    chunks: list[tuple[DocumentChunk, list[float]]],
) -> None:
    response = IngestResponse(
        document_id=document_id,
        filename=filename,
        status="processed",
        extracted_characters=sum(len(chunk.text) for chunk, _ in chunks),
        chunk_count=len(chunks),
        chunks=[chunk for chunk, _ in chunks],
        page_count=2 if source_type == "pdf" else None,
    )
    content_hash = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    store.save(response, content_hash, [vector for _, vector in chunks])


def _seed_corpus(engine):
    settings = _settings(engine)
    store = SqlAlchemyDocumentStore(settings, engine=engine)
    _save_document(
        store,
        document_id="doc_deed",
        filename="sale_deed.pdf",
        source_type="pdf",
        chunks=[
            (
                _chunk(
                    "doc_deed",
                    0,
                    "The sale deed identifies the property owner and title.",
                    "sale_deed.pdf",
                    "pdf",
                    page_number=1,
                ),
                _vector(0),
            ),
            (
                _chunk(
                    "doc_deed",
                    1,
                    "The encumbrance certificate confirms no outstanding loans.",
                    "sale_deed.pdf",
                    "pdf",
                    page_number=None,
                    page_numbers=[1, 2],
                ),
                _blend(0, 1),
            ),
        ],
    )
    _save_document(
        store,
        document_id="doc_locality",
        filename="locality_report.md",
        source_type="markdown",
        chunks=[
            (
                _chunk(
                    "doc_locality",
                    0,
                    "The metro station is two kilometres from the property.",
                    "locality_report.md",
                    "markdown",
                ),
                _vector(1),
            )
        ],
    )
    _save_document(
        store,
        document_id="doc_cost",
        filename="cost_breakdown.txt",
        source_type="txt",
        chunks=[
            (
                _chunk(
                    "doc_cost",
                    0,
                    "Registration charges and stamp duty total five percent.",
                    "cost_breakdown.txt",
                    "txt",
                ),
                _vector(2),
            )
        ],
    )
    return settings


def _service(settings: Settings, query_vector: list[float]) -> RetrievalService:
    provider = FakeEmbeddingProvider(
        dimensions=DIMENSIONS, vectors=[query_vector]
    )
    store = SqlAlchemyRetrievalStore(settings)
    return RetrievalService(
        settings,
        embedding_service=EmbeddingService(settings, provider=provider),
        store=store,
    )


def test_semantic_search_orders_by_cosine_distance_and_limits_top_k(
    clean_database,
):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search("who owns the property", top_k=2)
    results = outcome.response.results

    assert [result.chunk_id for result in results] == [
        "chk_doc_deed_0",
        "chk_doc_deed_1",
    ]
    assert results[0].score == pytest.approx(1.0, abs=1e-6)
    assert results[1].score == pytest.approx(1 / math.sqrt(2), abs=1e-6)
    assert results[1].distance == pytest.approx(
        1.0 - 1 / math.sqrt(2), abs=1e-6
    )
    assert results[0].score > results[1].score
    assert results[0].score_type == "cosine_similarity"
    assert results[0].distance == pytest.approx(0.0, abs=1e-6)
    assert results[0].metadata.filename == "sale_deed.pdf"


def test_top_k_larger_than_corpus_returns_every_match(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search("property", top_k=10)

    assert outcome.response.result_count == 4
    assert [result.chunk_id for result in outcome.response.results] == [
        "chk_doc_deed_0",
        "chk_doc_deed_1",
        "chk_doc_cost_0",
        "chk_doc_locality_0",
    ]


def test_empty_database_returns_no_results(clean_database):
    settings = _settings(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search("nothing here")

    assert outcome.response.results == []
    assert outcome.response.result_count == 0


def test_min_score_threshold_filters_low_similarity_results(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search("property", top_k=10, min_score=0.5)

    assert [result.chunk_id for result in outcome.response.results] == [
        "chk_doc_deed_0",
        "chk_doc_deed_1",
    ]
    assert all(result.score >= 0.5 for result in outcome.response.results)


# --- Metadata filters --------------------------------------------------------


def test_document_id_filter(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search(
        "property", top_k=10, document_id="doc_deed"
    )

    assert {result.document_id for result in outcome.response.results} == {
        "doc_deed"
    }
    assert outcome.response.result_count == 2


def test_filename_and_source_type_filters(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))
    from app.schemas.retrieval import RetrievalFilters

    by_filename = service.search(
        "property",
        top_k=10,
        filters=RetrievalFilters(source_filename="locality_report.md"),
    )
    by_type = service.search(
        "property",
        top_k=10,
        filters=RetrievalFilters(source_type="txt"),
    )

    assert [r.chunk_id for r in by_filename.response.results] == [
        "chk_doc_locality_0"
    ]
    assert [r.chunk_id for r in by_type.response.results] == [
        "chk_doc_cost_0"
    ]


def test_page_number_filter_matches_single_and_multi_page_chunks(
    clean_database,
):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))
    from app.schemas.retrieval import RetrievalFilters

    page_two = service.search(
        "property",
        top_k=10,
        filters=RetrievalFilters(page_number=2),
    )
    page_one = service.search(
        "property",
        top_k=10,
        filters=RetrievalFilters(page_number=1),
    )

    assert [r.chunk_id for r in page_two.response.results] == [
        "chk_doc_deed_1"
    ]
    assert [r.chunk_id for r in page_one.response.results] == [
        "chk_doc_deed_0",
        "chk_doc_deed_1",
    ]


def test_combined_filters(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))
    from app.schemas.retrieval import RetrievalFilters

    outcome = service.search(
        "property",
        top_k=10,
        document_id="doc_deed",
        filters=RetrievalFilters(
            source_filename="sale_deed.pdf",
            source_type="pdf",
            page_number=1,
        ),
    )

    assert outcome.response.result_count == 2


def test_filters_with_no_matches_return_empty_results(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))
    from app.schemas.retrieval import RetrievalFilters

    outcome = service.search(
        "property",
        document_id="doc_missing",
        filters=RetrievalFilters(source_filename="missing.pdf"),
    )

    assert outcome.response.results == []


# --- Hybrid ------------------------------------------------------------------


def test_hybrid_retrieval_uses_full_text_and_semantic_rankings(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))

    outcome = service.search(
        "encumbrance certificate outstanding loans", mode="hybrid", top_k=4
    )
    results = outcome.response.results

    assert results[0].chunk_id == "chk_doc_deed_1"
    assert results[0].keyword_rank == 1
    assert results[0].score_type == "reciprocal_rank_fusion"
    assert len({result.chunk_id for result in results}) == len(results)
    assert "chk_doc_deed_1" in {
        result.chunk_id for result in results
    }
    assert all(
        result.metadata.filename for result in results
    )


def test_hybrid_filters_are_applied_to_both_retrievers(clean_database):
    settings = _seed_corpus(clean_database)
    service = _service(settings, _vector(0))
    from app.schemas.retrieval import RetrievalFilters

    outcome = service.search(
        "registration charges stamp duty",
        mode="hybrid",
        top_k=10,
        filters=RetrievalFilters(source_type="txt"),
    )

    assert [result.chunk_id for result in outcome.response.results] == [
        "chk_doc_cost_0"
    ]


# --- Configuration safety ----------------------------------------------------


def test_dimension_mismatch_is_a_safe_configuration_error(clean_database):
    settings = _settings(clean_database, embedding_dimensions=4)
    service = _service(settings, [1.0, 0.0, 0.0, 0.0])

    with pytest.raises(RetrievalConfigurationError) as raised:
        service.search("title")

    assert "dimension mismatch" in raised.value.message.lower()
    assert "postgresql" not in raised.value.message.lower()
