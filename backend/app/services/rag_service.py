"""Grounded RAG orchestration with a strict citation contract."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, cast

from app.core.config import Settings, get_settings
from app.core.rag_prompt import RAG_SYSTEM_PROMPT
from app.schemas.rag import (
    EvidenceStatus,
    RAGCitation,
    RAGResponse,
)
from app.schemas.retrieval import (
    RetrievalFilters,
    RetrievalMode,
    RetrievalResult,
)
from app.services.embedding_service import EmbeddingError
from app.services.evidence_conflict import (
    claim_is_verbatim,
    claims_materially_disagree,
)
from app.services.llm_service import LLMError, LLMService
from app.services.rag_context import EvidenceSource, RAGContext, RAGContextBuilder
from app.services.rag_errors import (
    RAGConfigurationError,
    RAGExecutionError,
    RAGGenerationError,
    RAGQueryError,
)
from app.services.retrieval_errors import RetrievalError
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[(S[1-9][0-9]*)\]")
_BRACKET_RE = re.compile(r"\[([^\[\]]{1,80})\]")
_CITATION_START_RE = re.compile(
    r"^\s*(?:[Ss]\s*[-_.:#]?\s*0*\d|(?:source|citation)\b)",
    re.IGNORECASE,
)
_CITATION_PART_RE = re.compile(
    r"^(?:source\s*[-_.:#]?\s*|citation\s*[-_.:#]?\s*|[Ss]\s*[-_.:#]?\s*)?0*([1-9][0-9]*)$",
    re.IGNORECASE,
)
_SOURCE_ID_PATTERN = re.compile(
    r"^(?:source\s*[-_.:#]?\s*|citation\s*[-_.:#]?\s*|[Ss]\s*[-_.:#]?\s*)?0*([1-9][0-9]*)$",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")
_MODEL_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
}
_BASE_LIMITATION = (
    "This answer is limited to the retrieved excerpts and is not legal advice "
    "or a property clearance."
)
_CITATION_LIMITATION = (
    "Citations confirm that a source was retrieved; they do not establish "
    "claim-level entailment or legal verification."
)


class RAGService:
    """Retrieve evidence, generate an answer, and validate its citations."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        retrieval_service: RetrievalService | None = None,
        llm_service: LLMService | None = None,
        context_builder: RAGContextBuilder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retrieval_service = retrieval_service or RetrievalService(
            self.settings
        )
        self.llm_service = llm_service or LLMService(self.settings)
        self.context_builder = context_builder or RAGContextBuilder(
            self.settings
        )

    async def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        mode: RetrievalMode = "semantic",
        document_id: str | None = None,
        filters: RetrievalFilters | None = None,
        min_score: float | None = None,
        owner_id: str | None = None,
    ) -> RAGResponse:
        started = time.perf_counter()
        normalized_question = self._normalize_question(question)
        selected_mode = self._validate_mode(mode)
        candidate_limit = self._validate_top_k(top_k)

        try:
            outcome = await asyncio.to_thread(
                self.retrieval_service.search,
                normalized_question,
                top_k=candidate_limit,
                mode=selected_mode,
                document_id=document_id,
                filters=filters,
                min_score=min_score,
                owner_id=owner_id,
            )
        except (RetrievalError, EmbeddingError):
            raise
        except Exception as exc:
            logger.warning(
                "rag_retrieval_failed error=%s", type(exc).__name__
            )
            raise RAGExecutionError(
                "Retrieval failed safely; no answer was generated."
            ) from exc

        raw_results = outcome.response.results
        results = self._filter_weak_results(raw_results, selected_mode)
        weak_filtered_count = len(raw_results) - len(results)
        if not results:
            return self._no_evidence_response(
                normalized_question,
                selected_mode,
                retrieved_count=len(raw_results),
                weak_filtered_count=weak_filtered_count,
            )

        context = self.context_builder.build(normalized_question, results)
        if (
            context.estimated_tokens + self.settings.rag_max_output_tokens
            > self.settings.rag_model_context_tokens
        ):
            raise RAGConfigurationError(
                "The assembled evidence prompt and reserved output exceed the "
                "configured model context window."
            )
        if not context.sources:
            return self._insufficient_response(
                normalized_question,
                selected_mode,
                context,
                "The retrieved chunks could not be included in the answer "
                "context within the configured budget.",
                retrieved_count=len(raw_results),
                weak_filtered_count=weak_filtered_count,
            )

        try:
            raw_generation = await self.llm_service.generate(
                system_prompt=RAG_SYSTEM_PROMPT,
                user_prompt=context.user_prompt,
                max_tokens=self.settings.rag_max_output_tokens,
                json_mode=True,
            )
        except LLMError as exc:
            logger.warning(
                "rag_generation_failed error=%s", type(exc).__name__
            )
            raise
        except Exception as exc:
            logger.warning(
                "rag_generation_failed error=%s", type(exc).__name__
            )
            raise RAGExecutionError(
                "The grounded answer could not be generated safely."
            ) from exc

        try:
            response = self._compose_response(
                normalized_question,
                selected_mode,
                context,
                raw_generation,
                retrieved_count=len(raw_results),
                weak_filtered_count=weak_filtered_count,
            )
        except RAGGenerationError as exc:
            logger.warning(
                "rag_output_invalid error=%s retrieved=%d used=%d",
                type(exc).__name__,
                len(raw_results),
                len(context.sources),
            )
            return self._insufficient_response(
                normalized_question,
                selected_mode,
                context,
                "The language model output did not satisfy the grounding "
                "contract, so it was not returned as a supported answer.",
                retrieved_count=len(raw_results),
                weak_filtered_count=weak_filtered_count,
            )

        logger.info(
            "rag_completed status=%s mode=%s retrieved=%d used=%d "
            "citations=%d omitted=%d truncated=%d total_ms=%.1f",
            response.evidence_status,
            selected_mode,
            len(raw_results),
            len(context.sources),
            len(response.citations),
            context.omitted_count,
            context.truncated_count,
            (time.perf_counter() - started) * 1000,
        )
        return response

    def _compose_response(
        self,
        question: str,
        mode: RetrievalMode,
        context: RAGContext,
        raw_generation: str,
        *,
        retrieved_count: int,
        weak_filtered_count: int,
    ) -> RAGResponse:
        (
            answer,
            status,
            used_ids,
            model_limitations,
            raw_conflict_claims,
        ) = _parse_model_output(raw_generation)
        sources_by_id = {
            source.source_id: source for source in context.sources
        }
        allowed_ids = set(sources_by_id)

        answer_was_truncated = len(answer) > self.settings.rag_max_answer_chars
        if answer_was_truncated:
            answer = answer[: self.settings.rag_max_answer_chars].rstrip()

        answer, malformed_citation_count = _normalize_citation_labels(answer)
        marker_ids = {
            match.group(1)
            for match in _CITATION_PATTERN.finditer(answer)
        }
        invalid_marker_ids = marker_ids - allowed_ids
        if invalid_marker_ids:
            answer = _CITATION_PATTERN.sub(
                lambda match: (
                    match.group(0)
                    if match.group(1) in allowed_ids
                    else ""
                ),
                answer,
            )
        marker_ids &= allowed_ids

        supported_downgrade_reason: str | None = None
        if status == "supported":
            if not marker_ids:
                status = "insufficient_evidence"
                supported_downgrade_reason = "missing_citation"
            elif _has_uncited_material_sentence(answer):
                status = "insufficient_evidence"
                supported_downgrade_reason = "uncited_sentences"

        valid_used_ids, invalid_used_count = _coerce_source_ids(
            used_ids, allowed_ids
        )
        evidence_ids = marker_ids | valid_used_ids
        conflict_failure_reason: str | None = None
        if status == "conflicting_evidence":
            conflict_failure_reason = _validate_conflict_claims(
                raw_conflict_claims,
                sources_by_id,
                marker_ids,
            )
            if conflict_failure_reason is not None:
                status = "insufficient_evidence"

        if supported_downgrade_reason is not None:
            citation_ids = set()
        elif status in {"supported", "conflicting_evidence"}:
            citation_ids = marker_ids
        else:
            citation_ids = evidence_ids

        answer = " ".join(answer.split())
        if not answer:
            raise RAGGenerationError(
                "The model did not return a usable answer."
            )

        limitations = _clean_limitations(model_limitations)
        if malformed_citation_count:
            limitations.append(
                "The model returned malformed citation labels; those labels "
                "were removed."
            )
        if invalid_marker_ids:
            limitations.append(
                "The model referenced citation labels that were not present "
                "in the retrieved evidence; those labels were removed."
            )
        if invalid_used_count:
            limitations.append(
                "The model listed source IDs outside the retrieved evidence; "
                "those IDs were ignored."
            )
        if supported_downgrade_reason == "missing_citation":
            limitations.append(
                "The model did not provide a citation for a supported answer, "
                "so the response was marked as insufficient evidence."
            )
        elif supported_downgrade_reason == "uncited_sentences":
            limitations.append(
                "One or more material sentences in the supported answer lacked "
                "a citation, so the response was marked as insufficient "
                "evidence."
            )
        if conflict_failure_reason is not None:
            limitations.append(
                "A conflict response requires at least two valid, verbatim "
                "claims from different cited source documents that materially "
                f"disagree ({conflict_failure_reason}); the response was "
                "marked as insufficient evidence."
            )
        if answer_was_truncated:
            limitations.append(
                "The generated answer exceeded the configured length and was "
                "truncated."
            )
        if weak_filtered_count:
            limitations.append(
                f"{weak_filtered_count} retrieved chunk(s) fell below the "
                "configured relevance policy and were not sent to the model."
            )
        if context.omitted_count:
            limitations.append(
                "Some retrieved chunks were omitted because of overlapping or "
                "duplicate content or the context budget."
            )
        if context.truncated_count:
            limitations.append(
                "One or more evidence excerpts were shortened to fit the "
                "context budget."
            )
        limitations = [
            limitation
            for limitation in _unique_limitations(limitations)
            if limitation not in {_BASE_LIMITATION, _CITATION_LIMITATION}
        ][:7]
        limitations.extend([_CITATION_LIMITATION, _BASE_LIMITATION])

        citations = self._build_citations(
            citation_ids,
            sources_by_id,
        )
        return RAGResponse(
            question=question,
            answer=answer,
            evidence_status=cast(EvidenceStatus, status),
            citations=citations,
            limitations=limitations,
            retrieved_count=retrieved_count,
            used_chunk_count=len(context.sources),
            mode=mode,
        )

    def _build_citations(
        self,
        citation_ids: set[str],
        sources_by_id: dict[str, EvidenceSource],
    ) -> list[RAGCitation]:
        ordered_ids = sorted(
            citation_ids,
            key=lambda source_id: int(source_id[1:]),
        )
        citations: list[RAGCitation] = []
        for source_id in ordered_ids:
            source = sources_by_id[source_id]
            result = source.result
            metadata = result.metadata
            citations.append(
                RAGCitation(
                    citation_id=source_id,
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    filename=metadata.filename,
                    source=metadata.filename,
                    source_type=metadata.source_type,
                    page_number=metadata.page_number,
                    page_numbers=list(metadata.page_numbers),
                    chunk_index=metadata.chunk_index,
                    excerpt=_excerpt(
                        result.text,
                        self.settings.rag_max_excerpt_chars,
                    ),
                    document_created_at=metadata.document_created_at,
                )
            )
        return citations

    def _filter_weak_results(
        self,
        results: list[RetrievalResult],
        mode: RetrievalMode,
    ) -> list[RetrievalResult]:
        floor = self.settings.rag_min_semantic_score
        if floor is None:
            return list(results)
        eligible: list[RetrievalResult] = []
        for result in results:
            score = (
                result.semantic_score
                if result.semantic_score is not None
                else (
                    result.score
                    if result.score_type == "cosine_similarity"
                    else None
                )
            )
            if score is not None and score >= floor:
                eligible.append(result)
                continue
            if (
                mode == "hybrid"
                and result.keyword_rank is not None
                and result.keyword_rank
                <= self.settings.rag_max_keyword_only_rank
            ):
                eligible.append(result)
        return eligible

    def _no_evidence_response(
        self,
        question: str,
        mode: RetrievalMode,
        *,
        retrieved_count: int = 0,
        weak_filtered_count: int = 0,
    ) -> RAGResponse:
        limitations: list[str] = []
        if weak_filtered_count:
            limitations.append(
                f"{weak_filtered_count} retrieved chunk(s) fell below the "
                "configured relevance policy, so no answer was generated."
            )
        else:
            limitations.append(
                "No retrieval results were available, so no answer was "
                "generated."
            )
        limitations.extend([_CITATION_LIMITATION, _BASE_LIMITATION])
        return RAGResponse(
            question=question,
            answer="No relevant document excerpts were found for this question.",
            evidence_status="no_relevant_sources",
            citations=[],
            limitations=limitations,
            retrieved_count=retrieved_count,
            used_chunk_count=0,
            mode=mode,
        )

    def _insufficient_response(
        self,
        question: str,
        mode: RetrievalMode,
        context: RAGContext | None,
        reason: str,
        *,
        retrieved_count: int | None = None,
        weak_filtered_count: int = 0,
    ) -> RAGResponse:
        if retrieved_count is None:
            retrieved_count = context.retrieved_count if context else 0
        used_count = len(context.sources) if context else 0
        limitations = [reason]
        if weak_filtered_count:
            limitations.append(
                f"{weak_filtered_count} retrieved chunk(s) fell below the "
                "configured relevance policy and were not sent to the model."
            )
        limitations.extend([_CITATION_LIMITATION, _BASE_LIMITATION])
        return RAGResponse(
            question=question,
            answer=(
                "The available evidence is not sufficient to produce a "
                "validated answer to this question."
            ),
            evidence_status="insufficient_evidence",
            citations=[],
            limitations=limitations,
            retrieved_count=retrieved_count,
            used_chunk_count=used_count,
            mode=mode,
        )

    def _normalize_question(self, question: str) -> str:
        if not isinstance(question, str):
            raise RAGQueryError("question must be text.")
        cleaned = " ".join(question.split())
        if not cleaned:
            raise RAGQueryError(
                "question must not be empty or whitespace-only."
            )
        limit = min(
            self.settings.rag_max_question_chars,
            self.settings.retrieval_max_query_chars,
        )
        if len(cleaned) > limit:
            raise RAGQueryError(
                "question exceeds the "
                f"{limit} character limit."
            )
        return cleaned

    def _validate_top_k(self, top_k: int | None) -> int:
        evidence_cap = min(
            self.settings.rag_max_evidence_chunks,
            self.settings.retrieval_max_top_k,
        )
        requested = evidence_cap if top_k is None else top_k
        if isinstance(requested, bool) or not isinstance(requested, int):
            raise RAGQueryError("top_k must be an integer.")
        if requested < 1:
            raise RAGQueryError("top_k must be at least 1.")
        if requested > self.settings.retrieval_max_top_k:
            raise RAGQueryError(
                "top_k exceeds the configured maximum of "
                f"{self.settings.retrieval_max_top_k}."
            )
        return min(requested, evidence_cap)

    @staticmethod
    def _validate_mode(mode: str) -> RetrievalMode:
        if mode not in {"semantic", "hybrid"}:
            raise RAGQueryError(
                "mode must be either 'semantic' or 'hybrid'."
            )
        return cast(RetrievalMode, mode)


def _parse_model_output(
    raw_generation: str,
) -> tuple[str, str, list[Any], Any, Any]:
    payload = _parse_json_object(raw_generation)
    answer = payload.get("answer")
    status = payload.get("evidence_status")
    used_source_ids = payload.get("used_source_ids", [])
    conflict_claims = payload.get("conflict_claims", [])
    limitations = payload.get("limitations", [])

    if not isinstance(answer, str) or not answer.strip():
        raise RAGGenerationError("The model did not return a usable answer.")
    if not isinstance(status, str):
        raise RAGGenerationError("The model did not return an evidence status.")
    normalized_status = status.strip().lower()
    if normalized_status not in _MODEL_STATUSES:
        raise RAGGenerationError(
            "The model returned an unsupported evidence status."
        )
    if not isinstance(used_source_ids, list):
        raise RAGGenerationError(
            "The model did not return a source ID list."
        )
    if conflict_claims is None:
        conflict_claims = []
    if not isinstance(conflict_claims, list):
        raise RAGGenerationError(
            "The model did not return a valid conflict claim list."
        )
    return (
        answer.strip(),
        normalized_status,
        used_source_ids,
        limitations,
        conflict_claims,
    )


def _parse_json_object(raw_generation: str) -> dict[str, Any]:
    text = (raw_generation or "").strip()
    start = text.find("{")
    if start < 0:
        raise RAGGenerationError("The model did not return a JSON object.")
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except (json.JSONDecodeError, ValueError) as exc:
        raise RAGGenerationError(
            "The model returned malformed JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise RAGGenerationError("The model did not return a JSON object.")
    return payload


def _coerce_source_ids(
    raw_ids: list[Any],
    allowed_ids: set[str],
) -> tuple[set[str], int]:
    valid: set[str] = set()
    invalid_count = 0
    for raw_id in raw_ids:
        normalized: str | None = None
        if isinstance(raw_id, bool):
            invalid_count += 1
            continue
        if isinstance(raw_id, int):
            if raw_id > 0:
                normalized = f"S{raw_id}"
        elif isinstance(raw_id, str):
            match = _SOURCE_ID_PATTERN.match(raw_id.strip())
            if match:
                normalized = f"S{int(match.group(1))}"
        if normalized is None:
            invalid_count += 1
            continue
        if normalized in allowed_ids:
            valid.add(normalized)
        else:
            invalid_count += 1
    return valid, invalid_count


def _normalize_citation_labels(text: str) -> tuple[str, int]:
    malformed_count = 0

    def replace_bracket(match: re.Match[str]) -> str:
        nonlocal malformed_count
        content = match.group(1)
        if not _CITATION_START_RE.match(content):
            return match.group(0)
        labels: list[str] = []
        for part in re.split(r"[,;/]", content):
            part_match = _CITATION_PART_RE.fullmatch(part.strip())
            if part_match is None:
                malformed_count += 1
                return ""
            labels.append(f"S{int(part_match.group(1))}")
        if not labels:
            malformed_count += 1
            return ""
        return "".join(f"[{label}]" for label in labels)

    return _BRACKET_RE.sub(replace_bracket, text), malformed_count


def _has_uncited_material_sentence(answer: str) -> bool:
    for sentence in _SENTENCE_SPLIT_RE.split(answer):
        cleaned = sentence.strip(" \t-*•")
        if not cleaned or _CITATION_PATTERN.search(cleaned):
            continue
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'./%-]*", cleaned)
        if len(words) >= 3:
            return True
    return False


def _coerce_single_source_id(raw_id: Any) -> str | None:
    if isinstance(raw_id, bool):
        return None
    if isinstance(raw_id, int):
        return f"S{raw_id}" if raw_id > 0 else None
    if not isinstance(raw_id, str):
        return None
    candidate = raw_id.strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1].strip()
    match = _SOURCE_ID_PATTERN.match(candidate)
    if match is None:
        return None
    return f"S{int(match.group(1))}"


def _validate_conflict_claims(
    raw_claims: list[Any],
    sources_by_id: dict[str, EvidenceSource],
    cited_ids: set[str],
) -> str | None:
    if len(raw_claims) < 2:
        return "fewer than two conflict claims were supplied"

    validated: list[tuple[str, str, str]] = []
    for raw_claim in raw_claims:
        if not isinstance(raw_claim, dict):
            return "a conflict claim was not a structured object"
        source_id = _coerce_single_source_id(raw_claim.get("source_id"))
        claim = raw_claim.get("claim")
        if source_id is None or not isinstance(claim, str) or not claim.strip():
            return "a conflict claim had no valid source ID or text"
        if source_id not in sources_by_id:
            return "a conflict claim referenced a source that was not provided"
        if source_id not in cited_ids:
            return "a conflict claim source was not cited in the answer"
        source = sources_by_id[source_id]
        if not claim_is_verbatim(claim, source.result.text):
            return "a conflict claim was not verbatim from its cited source"
        doc_id = (source.result.document_id or "").strip()
        filename = (
            (source.result.metadata.filename or "").strip()
            if source.result.metadata
            else ""
        )
        if not doc_id or not filename:
            return "source metadata is missing or ambiguous"
        validated.append(
            (source_id, claim, doc_id)
        )

    if len({document_id for _, _, document_id in validated}) < 2:
        return "the conflict claims did not come from distinct documents"

    for index, (left_id, left_claim, left_doc) in enumerate(validated):
        for right_id, right_claim, right_doc in validated[index + 1:]:
            if left_id == right_id or left_doc == right_doc:
                continue
            disagrees, _ = claims_materially_disagree(
                left_claim,
                right_claim,
            )
            if disagrees:
                return None
    return "the claims did not contain a verifiable material disagreement"


def _clean_limitations(raw_limitations: Any) -> list[str]:
    if isinstance(raw_limitations, str):
        values = [raw_limitations]
    elif isinstance(raw_limitations, list):
        values = raw_limitations
    else:
        return []
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split())
        if not text:
            continue
        if len(text) > 300:
            text = f"{text[:297].rstrip()}..."
        cleaned.append(text)
    return cleaned


def _unique_limitations(limitations: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for limitation in limitations:
        if limitation in seen:
            continue
        seen.add(limitation)
        unique.append(limitation)
    return unique[:8]


def _excerpt(text: str, max_chars: int) -> str:
    normalized = " ".join((text or "").replace("\x00", " ").split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3].rstrip()}..."
