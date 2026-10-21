"""Run the Phase 4 retrieval evaluation against PostgreSQL/pgvector.

Example (from backend/, with DATABASE_URL configured for a dedicated eval DB):

    python scripts/evaluate_retrieval.py --reset --k 5 --output evaluation/last_run.json

The script ingests the synthetic corpus with the configured embedding provider,
resolves every expected relevant chunk from grounded phrases, and reports
Hit@K, Recall@K, Precision@K, and MRR for semantic, filtered semantic, hybrid,
and filtered hybrid retrieval. It does not call an LLM and does not generate
answers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.schemas.retrieval import RetrievalFilters, RetrievalMode  # noqa: E402
from app.services.document_ingestion import DocumentIngestionService  # noqa: E402
from app.services.document_store import get_shared_engine  # noqa: E402
from app.services.retrieval_errors import RetrievalError  # noqa: E402
from app.services.retrieval_evaluation import (  # noqa: E402
    QueryEvaluation,
    evaluate_ranking,
    summarize,
)
from app.services.retrieval_service import RetrievalService  # noqa: E402
from evaluation.dataset import (  # noqa: E402
    DATASET_PATH,
    document_bytes,
    load_dataset,
    validate_dataset,
)

CONFIGURATIONS: list[tuple[str, RetrievalMode, bool]] = [
    ("semantic", "semantic", False),
    ("semantic_filtered", "semantic", True),
    ("hybrid", "hybrid", False),
    ("hybrid_filtered", "hybrid", True),
]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this evaluation run.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to the retrieval evaluation JSON dataset.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Cutoff K. Defaults to RETRIEVAL_DEFAULT_TOP_K.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file for machine-readable results.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "TRUNCATE documents/chunks before ingesting. Only use this against "
            "a dedicated evaluation database."
        ),
    )
    return parser.parse_args(argv)


def _settings(args: argparse.Namespace) -> Settings:
    settings = get_settings()
    if args.database_url:
        settings = settings.model_copy(
            update={"database_url": args.database_url}
        )
    if not settings.is_database_configured:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it or pass --database-url."
        )
    return settings


def _reset_database(settings: Settings) -> None:
    engine = get_shared_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE chunks, documents RESTART IDENTITY CASCADE")
        )


def _ingest_corpus(
    settings: Settings, documents: list[dict[str, Any]]
) -> None:
    ingestion = DocumentIngestionService(settings)
    for document in documents:
        data, content_type = document_bytes(document)
        response = ingestion.ingest(
            data, document["filename"], content_type
        )
        if response.status != "processed":
            raise RuntimeError(
                f"Evaluation document {document['filename']} was not "
                f"processed (status={response.status})."
            )
        print(
            f"ingested {document['filename']}: "
            f"{response.chunk_count} chunk(s), document_id={response.document_id}"
        )


def _load_chunks(settings: Settings) -> list[dict[str, Any]]:
    engine = get_shared_engine(settings)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, document_id, source_filename, text "
                "FROM chunks ORDER BY document_id, chunk_index"
            )
        ).mappings().all()
    return [dict(row) for row in rows]


def _resolve_relevant_ids(
    queries: list[dict[str, Any]], chunks: list[dict[str, Any]]
) -> dict[str, list[str]]:
    resolved: dict[str, list[str]] = {}
    for query in queries:
        relevant: list[str] = []
        for marker in query.get("relevant_markers", []):
            matches = [
                chunk["id"]
                for chunk in chunks
                if marker.lower() in (chunk["text"] or "").lower()
            ]
            if not matches:
                raise RuntimeError(
                    f"Query {query['id']} marker was not found in stored "
                    f"chunks: {marker!r}"
                )
            for chunk_id in matches:
                if chunk_id not in relevant:
                    relevant.append(chunk_id)
        resolved[query["id"]] = relevant
    return resolved


def _evaluate_configuration(
    name: str,
    mode: RetrievalMode,
    apply_filters: bool,
    queries: list[dict[str, Any]],
    relevant_by_query: dict[str, list[str]],
    k: int,
    service: RetrievalService,
) -> dict[str, Any]:
    evaluations: list[QueryEvaluation] = []
    embedding_ms: list[float] = []
    database_ms: list[float] = []
    total_ms: list[float] = []

    for query in queries:
        filters = (
            RetrievalFilters(**query.get("filters", {}))
            if apply_filters
            else None
        )
        outcome = service.search(
            query["query"],
            top_k=k,
            mode=mode,
            filters=filters,
        )
        retrieved_ids = [
            result.chunk_id for result in outcome.response.results
        ]
        metrics = evaluate_ranking(
            retrieved_ids, relevant_by_query[query["id"]], k
        )
        evaluations.append(
            QueryEvaluation(
                query_id=query["id"],
                query=query["query"],
                retrieved_ids=retrieved_ids,
                relevant_ids=relevant_by_query[query["id"]],
                metrics=metrics,
            )
        )
        embedding_ms.append(outcome.embedding_duration_ms)
        database_ms.append(outcome.database_duration_ms)
        total_ms.append(outcome.total_duration_ms)

    summary = summarize(name, k, evaluations)
    return {
        "mode": mode,
        "filters_applied": apply_filters,
        "hit_at_k": summary.hit_at_k,
        "recall_at_k": summary.recall_at_k,
        "precision_at_k": summary.precision_at_k,
        "mrr": summary.mrr,
        "query_count": summary.query_count,
        "mean_embedding_ms": sum(embedding_ms) / len(embedding_ms),
        "mean_database_ms": sum(database_ms) / len(database_ms),
        "mean_total_ms": sum(total_ms) / len(total_ms),
        "queries": [
            {
                "query_id": evaluation.query_id,
                "query": evaluation.query,
                "retrieved_ids": evaluation.retrieved_ids,
                "relevant_ids": evaluation.relevant_ids,
                "hit_at_k": evaluation.metrics.hit_at_k,
                "recall_at_k": evaluation.metrics.recall_at_k,
                "precision_at_k": evaluation.metrics.precision_at_k,
                "mrr": evaluation.metrics.reciprocal_rank,
            }
            for evaluation in evaluations
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        settings = _settings(args)
        dataset = load_dataset(args.dataset)
        errors = validate_dataset(dataset)
        if errors:
            print("Evaluation dataset is invalid:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 2

        k = args.k if args.k is not None else settings.retrieval_default_top_k
        if k < 1 or k > settings.retrieval_max_top_k:
            print(
                f"K must be between 1 and {settings.retrieval_max_top_k}.",
                file=sys.stderr,
            )
            return 2

        if args.reset:
            _reset_database(settings)
        _ingest_corpus(settings, dataset["documents"])

        chunks = _load_chunks(settings)
        relevant_by_query = _resolve_relevant_ids(dataset["queries"], chunks)
        service = RetrievalService(settings)

        configurations: dict[str, Any] = {}
        for name, mode, apply_filters in CONFIGURATIONS:
            configurations[name] = _evaluate_configuration(
                name,
                mode,
                apply_filters,
                dataset["queries"],
                relevant_by_query,
                k,
                service,
            )

        report = {
            "dataset": str(args.dataset),
            "k": k,
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "corpus_documents": len(dataset["documents"]),
            "queries": len(dataset["queries"]),
            "configurations": configurations,
        }

        print()
        print(
            f"{'configuration':<22} {'hit@k':>8} {'recall@k':>10} "
            f"{'precision@k':>12} {'mrr':>8} {'mean_ms':>9}"
        )
        for name, result in configurations.items():
            print(
                f"{name:<22} {result['hit_at_k']:>8.3f} "
                f"{result['recall_at_k']:>10.3f} "
                f"{result['precision_at_k']:>12.3f} "
                f"{result['mrr']:>8.3f} "
                f"{result['mean_total_ms']:>9.1f}"
            )

        print()
        print("Per-query results:")
        for name, result in configurations.items():
            print(f"\n[{name}]")
            for query in result["queries"]:
                print(
                    f"  {query['query_id']:<34} "
                    f"hit={query['hit_at_k']:.0f} "
                    f"recall={query['recall_at_k']:.3f} "
                    f"precision={query['precision_at_k']:.3f} "
                    f"rr={query['mrr']:.3f}"
                )

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print(f"\nWrote {args.output}")
        return 0
    except Exception as exc:
        detail = (
            str(exc)
            if isinstance(exc, (RetrievalError, RuntimeError))
            else "unexpected error; see the backend logs"
        )
        print(
            f"Evaluation failed: {type(exc).__name__}: {detail}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
