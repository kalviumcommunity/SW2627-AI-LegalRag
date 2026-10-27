"""Bounded, deduplicated evidence context for grounded RAG."""

from __future__ import annotations

import math
import re
import secrets
from dataclasses import dataclass

from app.core.config import Settings
from app.core.rag_prompt import RAG_SYSTEM_PROMPT, build_rag_user_prompt
from app.schemas.retrieval import RetrievalResult
from app.services.rag_errors import RAGConfigurationError

_CITATION_LIKE_RE = re.compile(
    r"\[\s*(?:(?:source|citation)\b|[Ss]\s*[-_.:#]?\s*0*\d)[^\]]{0,80}\]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceSource:
    """One retrieved chunk included in the prompt."""

    source_id: str
    result: RetrievalResult
    text: str


@dataclass(frozen=True)
class RAGContext:
    """The prompt plus an auditable record of what fit into it."""

    user_prompt: str
    sources: list[EvidenceSource]
    retrieved_count: int
    omitted_count: int
    truncated_count: int
    estimated_tokens: int
    boundary_nonce: str


class RAGContextBuilder:
    """Convert retrieval results into a bounded, citation-ready prompt."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(
        self,
        question: str,
        results: list[RetrievalResult],
    ) -> RAGContext:
        max_chars = int(
            self.settings.rag_context_max_tokens
            * self.settings.rag_chars_per_token
            / self.settings.rag_token_safety_factor
        )
        empty_prompt = build_rag_user_prompt(question, "")
        remaining_chars = max_chars - len(RAG_SYSTEM_PROMPT) - len(empty_prompt)
        if remaining_chars <= 0:
            raise RAGConfigurationError(
                "The configured RAG context budget is too small for the "
                "system prompt and question."
            )

        sources: list[EvidenceSource] = []
        blocks: list[str] = []
        evidence_chars = 0
        omitted_count = 0
        truncated_count = 0
        boundary_nonce = secrets.token_hex(8)

        for result in results[: self.settings.rag_max_evidence_chunks]:
            text = _normalize_evidence(result.text)
            if not text:
                omitted_count += 1
                continue
            if _is_overlapping_duplicate(
                result,
                sources,
                self.settings.rag_overlap_dedup_ratio,
            ):
                omitted_count += 1
                continue

            source_id = f"S{len(sources) + 1}"
            per_chunk_limit = self.settings.rag_max_evidence_chunk_chars
            safe_text = _neutralize_untrusted(text)
            was_truncated = len(safe_text) > per_chunk_limit
            prompt_text = safe_text[:per_chunk_limit].rstrip()
            if was_truncated:
                prompt_text = f"{prompt_text} [truncated]"

            block = _format_evidence_block(
                source_id,
                result,
                prompt_text,
                boundary_nonce,
            )
            separator_chars = 2 if blocks else 0
            if (
                separator_chars + len(block) > remaining_chars
                or evidence_chars + len(block)
                > self.settings.rag_max_evidence_chars
            ):
                omitted_count += 1
                continue

            blocks.append(block)
            evidence_chars += len(block)
            remaining_chars -= separator_chars + len(block)
            if was_truncated:
                truncated_count += 1
            sources.append(
                EvidenceSource(
                    source_id=source_id,
                    result=result,
                    text=prompt_text,
                )
            )

        user_prompt = (
            build_rag_user_prompt(question, "\n\n".join(blocks))
            if blocks
            else ""
        )
        estimated_tokens = _estimate_tokens(
            len(RAG_SYSTEM_PROMPT) + len(user_prompt),
            self.settings,
        )
        if (
            estimated_tokens + self.settings.rag_max_output_tokens
            > self.settings.rag_model_context_tokens
        ):
            raise RAGConfigurationError(
                "The assembled RAG prompt and reserved output exceed the "
                "configured model context window."
            )
        return RAGContext(
            user_prompt=user_prompt,
            sources=sources,
            retrieved_count=len(results),
            omitted_count=omitted_count,
            truncated_count=truncated_count,
            estimated_tokens=estimated_tokens,
            boundary_nonce=boundary_nonce,
        )


def _normalize_evidence(text: str) -> str:
    return " ".join((text or "").replace("\x00", " ").split())


def _neutralize_untrusted(text: str) -> str:
    """Disarm delimiter spoofing and citation-looking labels in evidence."""
    escaped = text.replace("<", "&lt;").replace(">", "&gt;")
    return _CITATION_LIKE_RE.sub(
        lambda match: f"(citation-like label {match.group(0)[1:-1]} neutralized)",
        escaped,
    )


def _is_overlapping_duplicate(
    candidate: RetrievalResult,
    accepted: list[EvidenceSource],
    overlap_ratio: float,
) -> bool:
    candidate_text = _normalize_evidence(candidate.text).casefold()
    for source in accepted:
        other = source.result
        other_text = _normalize_evidence(other.text).casefold()
        if other.chunk_id == candidate.chunk_id:
            return True
        if other.document_id != candidate.document_id:
            # Identical text in another document is corroboration or conflict;
            # only drop duplicates within the same source document.
            continue
        candidate_start = candidate.metadata.start_offset
        candidate_end = candidate.metadata.end_offset
        other_start = other.metadata.start_offset
        other_end = other.metadata.end_offset
        same_range = (
            candidate_start == other_start
            and candidate_end == other_end
        )
        # Different text with identical offsets means the offsets are not
        # trustworthy; do not drop distinct evidence based on placeholder data.
        if (
            candidate_start is not None
            and candidate_end is not None
            and other_start is not None
            and other_end is not None
            and not (same_range and candidate_text != other_text)
        ):
            overlap = min(candidate_end, other_end) - max(
                candidate_start,
                other_start,
            )
            shorter = min(
                candidate_end - candidate_start,
                other_end - other_start,
            )
            if shorter > 0 and overlap / shorter >= overlap_ratio:
                return True
        if candidate_text and candidate_text == other_text:
            return True
    return False


def _format_evidence_block(
    source_id: str,
    result: RetrievalResult,
    text: str,
    boundary_nonce: str,
) -> str:
    metadata = result.metadata
    page_label = (
        ", ".join(str(page) for page in metadata.page_numbers)
        if metadata.page_numbers
        else (str(metadata.page_number) if metadata.page_number else "unknown")
    )
    created_at = (
        metadata.document_created_at.isoformat()
        if metadata.document_created_at is not None
        else "unknown"
    )
    return (
        f"<<<EVIDENCE {source_id} {boundary_nonce}>>>\n"
        f"filename: {_safe_metadata(metadata.filename)}\n"
        f"source_type: {_safe_metadata(metadata.source_type)}\n"
        f"pages: {page_label}\n"
        f"chunk_index: {metadata.chunk_index}\n"
        f"ingested_at: {created_at}\n"
        f"chunk_id: {_safe_metadata(result.chunk_id)}\n"
        f"document_id: {_safe_metadata(result.document_id)}\n"
        f"content: {text}\n"
        f"<<<END {source_id} {boundary_nonce}>>>"
    )


def _safe_metadata(value: str) -> str:
    return _neutralize_untrusted(
        " ".join((value or "").replace("\x00", " ").split())
    )


def _estimate_tokens(char_count: int, settings: Settings) -> int:
    return math.ceil(
        (char_count / settings.rag_chars_per_token)
        * settings.rag_token_safety_factor
    )
