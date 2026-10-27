"""Deterministic, non-circular evaluation harness for Phase 5 RAG.

The harness exercises the real retrieval and RAG orchestration services with a
local lexical-hash embedding provider, an in-memory retrieval store, and an
extractive fake LLM. It never imports application test doubles and never seeds
the pipeline with expected statuses, documents, or markers.

This is an offline regression harness, not a measurement of live model quality.
Its outputs are limited to:
* retrieval recall against the labelled corpus,
* evidence-status agreement,
* structural citation integrity.

Claim-level entailment is explicitly not assessed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

from app.core.config import Settings
from app.schemas.retrieval import RetrievalMode
from app.services.embedding_service import EmbeddingService
from app.services.evidence_conflict import claims_materially_disagree
from app.services.rag_evaluation import (
    RAGEvaluationSummary,
    evaluate_rag_response,
    summarize_rag_evaluations,
)
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalOutcome, RetrievalService
from app.services.retrieval_store import (
    ChunkRecord,
    KeywordMatch,
    SearchFilters,
    SemanticMatch,
)

DATASET_PATH = Path(__file__).resolve().parent / "rag_dataset.json"

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_EVIDENCE_BLOCK_RE = re.compile(
    r"<<<EVIDENCE (?P<source_id>S[1-9][0-9]*) (?P<nonce>[0-9a-f]+)>>>\n"
    r"(?P<body>.*?)\n<<<END (?P=source_id) (?P=nonce)>>>",
    re.DOTALL,
)
_QUESTION_RE = re.compile(
    r"Question:\n(?P<question>.*?)\n\nRetrieved evidence:",
    re.DOTALL,
)
_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "does",
    "do",
    "did",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "those",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "whose",
    "with",
}
_ANSWER_GENERIC_TERMS = {
    "according",
    "available",
    "certificate",
    "complex",
    "document",
    "documents",
    "file",
    "files",
    "inr",
    "kilometre",
    "kilometer",
    "lakh",
    "metre",
    "meter",
    "month",
    "months",
    "notice",
    "percent",
    "percentage",
    "property",
    "record",
    "records",
    "report",
    "residential",
    "rupee",
    "rupees",
    "source",
    "sources",
    "square",
    "state",
    "states",
    "stated",
    "year",
    "years",
}
_CONFLICT_QUESTION_TERMS = {"encumbrance", "loan", "mortgage"}


def _stem_term(term: str) -> str:
    if len(term) > 4 and term.endswith("ies"):
        return f"{term[:-3]}y"
    if len(term) > 4 and term.endswith(("ses", "xes", "zes", "ches", "shes")):
        return term[:-2]
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        return term[:-1]
    return term


def _terms(text: str, *, exclude_generic: bool = False) -> set[str]:
    terms: set[str] = set()
    for raw in _WORD_RE.findall(text or ""):
        if raw.isdigit():
            continue
        term = _stem_term(raw.casefold())
        if len(term) < 3 or term in _STOP_WORDS:
            continue
        if exclude_generic and term in _ANSWER_GENERIC_TERMS:
            continue
        terms.add(term)
    return terms


def load_dataset(path: Path = DATASET_PATH) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class LexicalHashEmbeddingProvider:
    """Deterministic bag-of-words hashing; no network and no model download."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> Sequence[Sequence[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for term in _terms(text):
                digest = hashlib.sha256(term.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            if not any(vector):
                vector[0] = 1.0
            vectors.append(vector)
        return vectors


class InMemoryRetrievalStore:
    """Protocol-compatible store with cosine and lexical keyword search."""

    def __init__(
        self,
        records: list[ChunkRecord],
        vectors: list[list[float]],
    ) -> None:
        self.records = records
        self.vectors = vectors
        self.documents_by_chunk = {
            record.chunk_id: record.document_id for record in records
        }

    def ensure_ready(self) -> None:
        return None

    def search_semantic(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: SearchFilters,
        min_score: float | None = None,
    ) -> list[SemanticMatch]:
        matches: list[SemanticMatch] = []
        for record, vector in zip(self.records, self.vectors):
            if not _matches_filters(record, filters):
                continue
            similarity = math.fsum(
                left * right for left, right in zip(query_vector, vector)
            )
            if min_score is not None and similarity < min_score:
                continue
            matches.append(
                SemanticMatch(
                    record=record,
                    distance=1.0 - similarity,
                    similarity=similarity,
                )
            )
        matches.sort(key=lambda match: (-match.similarity, match.record.chunk_id))
        return matches[:limit]

    def search_keyword(
        self,
        query: str,
        *,
        limit: int,
        filters: SearchFilters,
    ) -> list[KeywordMatch]:
        query_terms = _terms(query)
        ranked: list[tuple[int, float, ChunkRecord]] = []
        for record in self.records:
            if not _matches_filters(record, filters):
                continue
            record_terms = _terms(record.text)
            overlap = query_terms & record_terms
            if not overlap:
                continue
            relevance = len(overlap) / max(1, len(query_terms))
            ranked.append((len(overlap), relevance, record))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2].chunk_id))
        return [
            KeywordMatch(record=record, rank=index + 1, relevance=relevance)
            for index, (_, relevance, record) in enumerate(ranked[:limit])
        ]


class RecordingRetrievalService:
    """Delegate to the real service while retaining the inspected results."""

    def __init__(self, service: RetrievalService) -> None:
        self.service = service
        self.last_outcome: RetrievalOutcome | None = None

    def search(self, *args: Any, **kwargs: Any) -> RetrievalOutcome:
        outcome = self.service.search(*args, **kwargs)
        self.last_outcome = outcome
        return outcome


class ExtractiveLLMService:
    """Offline LLM substitute that only reads the supplied evidence prompt."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        prompt = kwargs.get("user_prompt", "")
        question, sources = _parse_prompt(prompt)
        answer, status, used_ids, claims = _extract_response(question, sources)
        return json.dumps(
            {
                "answer": answer,
                "evidence_status": status,
                "used_source_ids": used_ids,
                "conflict_claims": claims,
                "limitations": [
                    "Offline extractive harness answer; claim-level entailment "
                    "was not assessed."
                ],
            }
        )


def _parse_prompt(
    prompt: str,
) -> tuple[str, list[dict[str, str]]]:
    question_match = _QUESTION_RE.search(prompt)
    question = question_match.group("question") if question_match else ""
    sources: list[dict[str, str]] = []
    for match in _EVIDENCE_BLOCK_RE.finditer(prompt):
        body = match.group("body")
        content_match = re.search(r"^content: (.*)$", body, re.MULTILINE)
        document_match = re.search(r"^document_id: (.*)$", body, re.MULTILINE)
        if content_match is None:
            continue
        sources.append(
            {
                "source_id": match.group("source_id"),
                "document_id": (
                    document_match.group(1).strip()
                    if document_match is not None
                    else match.group("source_id")
                ),
                "text": content_match.group(1).strip(),
            }
        )
    return question, sources


def _sentences(text: str) -> list[str]:
    return [
        " ".join(sentence.split())
        for sentence in _SENTENCE_RE.split(text)
        if len(" ".join(sentence.split()).split()) >= 3
    ]


def _extract_response(
    question: str,
    sources: list[dict[str, str]],
) -> tuple[str, str, list[int], list[dict[str, str]]]:
    question_terms = _terms(question, exclude_generic=True)
    all_question_terms = _terms(question)
    selected: list[tuple[dict[str, str], int]] = []
    for source in sources:
        overlap = question_terms & _terms(source["text"], exclude_generic=True)
        if len(overlap) >= 2:
            selected.append((source, len(overlap)))
    selected.sort(key=lambda item: (-item[1], item[0]["source_id"]))

    if all_question_terms & _CONFLICT_QUESTION_TERMS:
        conflict = _find_conflict(sources)
        if conflict is not None:
            left, right = conflict
            answer = (
                f"Source {left['source_id']} states: \"{left['text']}\" "
                f"[{left['source_id']}]. "
                f"Source {right['source_id']} states: \"{right['text']}\" "
                f"[{right['source_id']}]."
            )
            return (
                answer,
                "conflicting_evidence",
                [_source_number(left["source_id"]), _source_number(right["source_id"])],
                [
                    {"source_id": left["source_id"], "claim": left["text"]},
                    {"source_id": right["source_id"], "claim": right["text"]},
                ],
            )

    picked_sentences: list[tuple[str, str]] = []
    covered_terms: set[str] = set()
    for source, _ in selected[:2]:
        candidates: list[tuple[int, str]] = []
        for sentence in _sentences(source["text"]):
            overlap = question_terms & _terms(sentence, exclude_generic=True)
            if overlap:
                candidates.append((len(overlap), sentence))
        candidates.sort(key=lambda item: -item[0])
        for _, sentence in candidates[:2]:
            picked_sentences.append((source["source_id"], sentence))
            covered_terms |= question_terms & _terms(
                sentence, exclude_generic=True
            )

    coverage = (
        len(covered_terms) / len(question_terms) if question_terms else 0.0
    )
    if picked_sentences and coverage >= 0.6:
        parts = []
        for source_id, sentence in picked_sentences:
            flattened = _flatten_for_answer(sentence)
            parts.append(
                f"According to {source_id} [{source_id}], the evidence "
                f"states: {flattened} [{source_id}]."
            )
        used_ids = sorted(
            {_source_number(source_id) for source_id, _ in picked_sentences}
        )
        return " ".join(parts), "supported", used_ids, []

    return (
        "The retrieved evidence does not establish a complete answer to the "
        "question.",
        "insufficient_evidence",
        [],
        [],
    )


def _find_conflict(
    sources: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, str]] | None:
    claims: list[tuple[dict[str, str], str]] = []
    for source in sources:
        for sentence in _sentences(source["text"]):
            claims.append((source, sentence))
    for index, (left_source, left_claim) in enumerate(claims):
        for right_source, right_claim in claims[index + 1:]:
            if left_source["document_id"] == right_source["document_id"]:
                continue
            disagrees, _ = claims_materially_disagree(
                left_claim,
                right_claim,
            )
            if disagrees:
                return (
                    {**left_source, "text": left_claim},
                    {**right_source, "text": right_claim},
                )
    return None


def _flatten_for_answer(sentence: str) -> str:
    text = " ".join(sentence.split()).rstrip(".")
    return re.sub(r"(?<=\b[A-Z])\.\s+", " ", text)


def _source_number(source_id: str) -> int:
    return int(source_id[1:])


def _matches_filters(record: ChunkRecord, filters: SearchFilters) -> bool:
    if filters.document_id is not None and record.document_id != filters.document_id:
        return False
    if (
        filters.source_filename is not None
        and record.source_filename != filters.source_filename
    ):
        return False
    if filters.source_type is not None and record.source_type != filters.source_type:
        return False
    if filters.page_number is not None and record.page_number != filters.page_number:
        return False
    return True


def _source_type(raw_format: str) -> str:
    if raw_format in {"md", "markdown"}:
        return "markdown"
    return raw_format


def build_harness(
    dataset: dict[str, Any],
    settings: Settings | None = None,
) -> tuple[RAGService, RecordingRetrievalService, ExtractiveLLMService]:
    resolved_settings = settings or Settings(
        groq_api_key="offline-evaluation",
        embedding_provider="fastembed",
        embedding_model="lexical-hash",
        embedding_dimensions=256,
        retrieval_default_top_k=5,
        retrieval_max_top_k=8,
        rag_max_evidence_chunks=5,
        rag_min_semantic_score=0.35,
    )
    records: list[ChunkRecord] = []
    for index, document in enumerate(dataset.get("documents", [])):
        text = document.get("content")
        if not text:
            text = "\n\n".join(document.get("pages", []))
        text = " ".join(text.split())
        raw_format = document.get("format", "txt")
        page_numbers = (
            list(range(1, len(document.get("pages", [])) + 1))
            if raw_format == "pdf"
            else [1]
        )
        records.append(
            ChunkRecord(
                chunk_id=f"chk_{index + 1}",
                document_id=f"doc_{document['key']}",
                chunk_index=0,
                text=text,
                source_filename=document["filename"],
                source_type=_source_type(raw_format),
                page_number=None if raw_format == "pdf" else 1,
                start_offset=0,
                end_offset=len(text),
                chunk_metadata={
                    "page_numbers": page_numbers,
                    "character_count": len(text),
                },
                document_created_at=None,
            )
        )

    embedding_service = EmbeddingService(
        resolved_settings,
        provider=LexicalHashEmbeddingProvider(
            dimensions=resolved_settings.embedding_dimensions
        ),
    )
    vectors = embedding_service.embed_texts([record.text for record in records])
    store = InMemoryRetrievalStore(records, vectors)
    real_retrieval = RetrievalService(
        resolved_settings,
        embedding_service=embedding_service,
        store=store,
    )
    retrieval = RecordingRetrievalService(real_retrieval)
    llm = ExtractiveLLMService()
    rag = RAGService(
        resolved_settings,
        retrieval_service=retrieval,  # type: ignore[arg-type]
        llm_service=llm,  # type: ignore[arg-type]
    )
    return rag, retrieval, llm


async def run_evaluation(
    dataset_path: Path = DATASET_PATH,
    *,
    mode: RetrievalMode = "hybrid",
) -> RAGEvaluationSummary:
    dataset = load_dataset(dataset_path)
    rag, retrieval, _ = build_harness(dataset)
    evaluations = []
    for item in dataset.get("queries", []):
        response = await rag.ask(item["query"], mode=mode)
        sources = []
        if retrieval.last_outcome is not None:
            outcome: RetrievalOutcome = retrieval.last_outcome
            context = rag.context_builder.build(
                item["query"],
                outcome.response.results,
            )
            sources = context.sources
        evaluations.append(
            evaluate_rag_response(item, response, sources)
        )
    return summarize_rag_evaluations(evaluations)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--mode", choices=("semantic", "hybrid"), default="hybrid")
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(f"Dataset not found at {args.dataset}", file=sys.stderr)
        return 1

    summary = asyncio.run(run_evaluation(args.dataset, mode=args.mode))
    print_summary(summary)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "mode": args.mode,
            "total_queries": summary.total_queries,
            "status_accuracy": summary.status_accuracy,
            "retrieval_success_rate": summary.retrieval_success_rate,
            "overall_citation_validity_rate": (
                summary.overall_citation_validity_rate
            ),
            "citation_integrity_rate": summary.citation_integrity_rate,
            "claim_support_assessed": summary.claim_support_assessed,
            "claim_support_verified_count": summary.claim_support_verified_count,
            "per_status_breakdown": summary.per_status_breakdown,
            "query_evaluations": [
                {
                    "query_id": q.query_id,
                    "question": q.question,
                    "expected_status": q.expected_status,
                    "actual_status": q.actual_status,
                    "status_match": q.status_match,
                    "retrieval_success": q.retrieval_success,
                    "total_citations": q.total_citations,
                    "valid_citations": q.valid_citations,
                    "citation_validity_rate": q.citation_validity_rate,
                    "citation_integrity_verified": (
                        q.citation_integrity_verified
                    ),
                    "claim_support_assessed": q.claim_support_assessed,
                    "claim_support_verified": q.claim_support_verified,
                    "notes": q.notes,
                }
                for q in summary.query_evaluations
            ],
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"Report saved to {args.output}")
    return 0


def print_summary(summary: RAGEvaluationSummary) -> None:
    print("\n" + "=" * 70)
    print("PHASE 5 OFFLINE RAG HARNESS (DETERMINISTIC, NOT LIVE QUALITY)")
    print("=" * 70)
    print(f"Total Queries Evaluated:       {summary.total_queries}")
    print(
        f"Status Accuracy:               {summary.status_accuracy:.1%} "
        f"({summary.status_match_count}/{summary.total_queries})"
    )
    print(
        f"Retrieval Success Rate:        {summary.retrieval_success_rate:.1%} "
        f"({summary.retrieval_success_count}/{summary.total_queries})"
    )
    print(
        f"Citation Validity Rate:        "
        f"{summary.overall_citation_validity_rate:.1%} "
        f"({summary.valid_citations_returned}/"
        f"{summary.total_citations_returned})"
    )
    print(
        f"Citation Integrity Rate:       {summary.citation_integrity_rate:.1%} "
        f"({summary.citation_integrity_verified_count}/"
        f"{summary.total_queries})"
    )
    print("Claim-Support Assessment:      NOT ASSESSED")
    print("\nPer-Status Breakdown:")
    for status, counts in summary.per_status_breakdown.items():
        total = counts["total"]
        correct = counts["correct"]
        pct = (correct / total * 100) if total > 0 else 0.0
        print(f"  - {status:<24}: {correct}/{total} ({pct:.0f}%)")
    print("\nDetailed Query Results:")
    for evaluation in summary.query_evaluations:
        mark = (
            "[PASS]"
            if evaluation.status_match
            and evaluation.citation_integrity_verified
            else "[FAIL]"
        )
        print(f"  {mark} [{evaluation.query_id}]")
        print(f"      Question: {evaluation.question}")
        print(
            f"      Status: Expected='{evaluation.expected_status}', "
            f"Actual='{evaluation.actual_status}'"
        )
        print(
            f"      Citations: {evaluation.valid_citations}/"
            f"{evaluation.total_citations} valid"
        )
        if evaluation.notes:
            print(f"      Notes: {', '.join(evaluation.notes)}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
