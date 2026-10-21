"""Small, dependency-free retrieval metrics used by tests and the eval runner.

Definitions (K is the requested cutoff):

* Hit@K: 1 when at least one known-relevant chunk is in the top K, else 0.
* Recall@K: relevant chunks retrieved in the top K / all known relevant chunks.
* Precision@K: retrieved relevant chunks / chunks actually returned in the
  top K (0 when nothing was returned).
* MRR: 1 / rank of the first relevant result, or 0 when none is in the top K.

Queries with no known relevant evidence contribute 0 to Hit@K, Recall@K,
Precision@K, and MRR. This is explicit rather than silently excluding them, so
a retriever that always returns chunks is penalized for unanswerable queries.
Duplicate retrieved IDs are ignored after their first appearance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Collection, Sequence


@dataclass(frozen=True)
class RetrievalMetrics:
    hit_at_k: float
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    retrieved_count: int
    relevant_count: int


@dataclass(frozen=True)
class QueryEvaluation:
    query_id: str
    query: str
    retrieved_ids: list[str] = field(default_factory=list)
    relevant_ids: list[str] = field(default_factory=list)
    metrics: RetrievalMetrics | None = None


@dataclass(frozen=True)
class EvaluationSummary:
    name: str
    k: int
    query_count: int
    hit_at_k: float
    recall_at_k: float
    precision_at_k: float
    mrr: float
    queries: list[QueryEvaluation] = field(default_factory=list)


def _unique_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def evaluate_ranking(
    retrieved_ids: Sequence[str],
    relevant_ids: Collection[str],
    k: int,
) -> RetrievalMetrics:
    """Compute Hit@K, Recall@K, Precision@K, and MRR for one query."""
    if k < 1:
        raise ValueError("k must be at least 1")

    top_k = _unique_preserving_order(retrieved_ids)[:k]
    relevant = set(relevant_ids)
    relevant_retrieved = [chunk_id for chunk_id in top_k if chunk_id in relevant]

    if not relevant:
        return RetrievalMetrics(
            hit_at_k=0.0,
            recall_at_k=0.0,
            precision_at_k=0.0,
            reciprocal_rank=0.0,
            retrieved_count=len(top_k),
            relevant_count=0,
        )

    first_relevant_rank = next(
        (
            rank
            for rank, chunk_id in enumerate(top_k, start=1)
            if chunk_id in relevant
        ),
        None,
    )
    return RetrievalMetrics(
        hit_at_k=1.0 if first_relevant_rank is not None else 0.0,
        recall_at_k=len(relevant_retrieved) / len(relevant),
        precision_at_k=(
            len(relevant_retrieved) / len(top_k) if top_k else 0.0
        ),
        reciprocal_rank=(
            1.0 / first_relevant_rank
            if first_relevant_rank is not None
            else 0.0
        ),
        retrieved_count=len(top_k),
        relevant_count=len(relevant),
    )


def summarize(
    name: str,
    k: int,
    evaluations: Sequence[QueryEvaluation],
) -> EvaluationSummary:
    """Macro-average per-query metrics, including no-evidence queries as 0."""
    if not evaluations:
        raise ValueError("at least one query evaluation is required")
    for evaluation in evaluations:
        if evaluation.metrics is None:
            raise ValueError("every query evaluation must have metrics")
    count = len(evaluations)
    return EvaluationSummary(
        name=name,
        k=k,
        query_count=count,
        hit_at_k=sum(e.metrics.hit_at_k for e in evaluations) / count,
        recall_at_k=sum(e.metrics.recall_at_k for e in evaluations) / count,
        precision_at_k=(
            sum(e.metrics.precision_at_k for e in evaluations) / count
        ),
        mrr=sum(e.metrics.reciprocal_rank for e in evaluations) / count,
        queries=list(evaluations),
    )
