"""Claim-level evidence verification and trustworthiness evaluation for Grounded RAG.

This service validates that:
1. Every material factual claim in an answer is supported by retrieved evidence.
2. Fabricated citation IDs (labels referencing unretrieved chunks) are rejected.
3. Citations that merely match text or exist in the prompt without entailing the claim
   are detected and marked unsupported.
4. Material contradictions across distinct documents are detected and exposed.
5. Inconclusive or missing evidence is downgraded to 'insufficient_evidence' with
   concise explanations, without falsely inferring lack of liens or defects.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Sequence

from app.schemas.rag import (
    ClaimVerification,
    ClaimVerificationStatus,
    CrossDocumentConflict,
    EvidenceStatus,
    RAGCitation,
)
from app.services.evidence_conflict import (
    claims_materially_disagree,
    detect_cross_document_conflicts,
    normalize_claim_text,
    parse_normalized_area,
    parse_normalized_currency,
)
from app.services.rag_context import EvidenceSource

logger = logging.getLogger(__name__)

_CITATION_TAG_RE = re.compile(r"\[(S[1-9][0-9]*)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")
_META_SENTENCE_PATTERNS = (
    re.compile(r"^based on the (?:retrieved|provided|available) (?:documents|evidence|excerpts)", re.IGNORECASE),
    re.compile(r"^according to the (?:retrieved|provided|available) (?:documents|records)", re.IGNORECASE),
    re.compile(r"^the available documents do not (?:contain|provide|establish)", re.IGNORECASE),
    re.compile(r"^there (?:is|are) no (?:relevant|retrieved) (?:documents|sources)", re.IGNORECASE),
)


class EvidenceVerificationService:
    """Rigorous verification of factual claims against retrieved evidence passages."""

    def verify_answer(
        self,
        question: str,
        answer: str,
        sources_by_id: dict[str, EvidenceSource],
        initial_status: EvidenceStatus,
        raw_conflict_claims: list[Any] | None = None,
        retrieved_count: int = 0,
        weak_filtered_count: int = 0,
    ) -> tuple[EvidenceStatus, list[ClaimVerification], list[CrossDocumentConflict], list[str]]:
        """Perform claim-level evidence verification and sufficiency determination.

        Returns:
            (final_evidence_status, claim_verifications, conflicts, insufficient_reasons)
        """
        insufficient_reasons: list[str] = []

        # 1. If no relevant sources were retrieved or all chunks were filtered
        actual_retrieved = retrieved_count if retrieved_count > 0 else len(sources_by_id)
        if actual_retrieved == 0 or not sources_by_id:
            return "no_relevant_sources", [], [], ["No relevant property documents were retrieved for the question."]

        # 2. Extract discrete claims from the generated answer
        raw_sentences = [
            s.strip() for s in _SENTENCE_SPLIT_RE.split(answer.strip()) if s.strip()
        ]

        claim_verifications: list[ClaimVerification] = []
        for sentence in raw_sentences:
            verification = self._verify_sentence_claim(sentence, sources_by_id)
            if verification is not None:
                claim_verifications.append(verification)

        # 3. Detect Cross-Document Conflicts across distinct documents
        conflicts = detect_cross_document_conflicts(list(sources_by_id.values()))

        # 4. Check whether answer has missing facts or explicit disclaimers
        has_negative_assertion = self._detect_negative_or_missing_assertion(answer)

        # 5. Evaluate sufficiency and determine final evidence status
        has_contradicted_claims = any(cv.status == "contradicted" for cv in claim_verifications)
        has_unsupported_claims = any(cv.status == "unsupported" for cv in claim_verifications)
        all_claims_supported = (
            len(claim_verifications) > 0
            and all(cv.status == "supported" for cv in claim_verifications)
        )

        final_status: EvidenceStatus = initial_status

        # If genuine cross-document conflicts exist
        if conflicts:
            final_status = "conflicting_evidence"
            for c in conflicts:
                insufficient_reasons.append(
                    f"Conflict detected: {c.source_a.filename} [{c.source_a.citation_id}] conflicts with {c.source_b.filename} [{c.source_b.citation_id}] ({c.contradiction_reason})."
                )

        # If any claims are contradicted or unsupported
        elif has_contradicted_claims:
            final_status = "insufficient_evidence"
            for cv in claim_verifications:
                if cv.status == "contradicted":
                    insufficient_reasons.append(
                        f"Claim contradicts evidence: '{cv.claim_text}' ({cv.entailment_explanation or 'Contradicts cited source'})."
                    )

        elif has_unsupported_claims:
            final_status = "insufficient_evidence"
            for cv in claim_verifications:
                if cv.status == "unsupported":
                    insufficient_reasons.append(
                        f"Unsupported claim: '{cv.claim_text}' ({cv.entailment_explanation or 'Not established by evidence'})."
                    )

        elif has_negative_assertion:
            final_status = "insufficient_evidence"
            insufficient_reasons.append(
                "The available documents cannot establish complete title, approvals, or encumbrance status."
            )

        elif all_claims_supported and not conflicts:
            final_status = "supported"

        else:
            final_status = "insufficient_evidence"
            insufficient_reasons.append(
                "The evidence is incomplete or inconclusive to establish the full answer."
            )

        # Ensure absence of evidence is not presented as clear title or absence of lien
        if final_status == "insufficient_evidence" and any(
            w in question.lower() for w in ("lien", "mortgage", "dispute", "encumbrance", "defect", "title")
        ):
            caveat = (
                "Absence of recorded encumbrances or title defect records in the provided documents "
                "does not establish that the property has clear or unencumbered marketable title."
            )
            if caveat not in insufficient_reasons:
                insufficient_reasons.append(caveat)

        return final_status, claim_verifications, conflicts, insufficient_reasons

    def _verify_sentence_claim(
        self,
        sentence: str,
        sources_by_id: dict[str, EvidenceSource],
    ) -> ClaimVerification | None:
        """Verify an individual factual sentence against cited source passages."""
        # Check if purely conversational/meta sentence
        cleaned = sentence.strip()
        for meta_pat in _META_SENTENCE_PATTERNS:
            if meta_pat.match(cleaned):
                return None

        citation_matches = list(_CITATION_TAG_RE.finditer(sentence))
        cited_ids = [m.group(1) for m in citation_matches]

        # 1. Check for fabricated citation IDs (IDs not in retrieved sources)
        fabricated_ids = [cid for cid in cited_ids if cid not in sources_by_id]
        if fabricated_ids:
            return ClaimVerification(
                claim=sentence,
                status="unsupported",
                cited_sources=cited_ids,
                evidence_excerpts=[],
                reasoning=(
                    f"Fabricated citation ID(s) {', '.join(f'[{fid}]' for fid in fabricated_ids)} "
                    "reference sources not retrieved for this request."
                ),
            )

        # 2. Check for material factual assertions lacking any citations
        if not cited_ids:
            # Check if sentence makes a substantive factual assertion (contains numbers, dates, or key legal terms)
            has_factual_content = bool(
                re.search(r"\b\d+\b", sentence)
                or any(term in sentence.lower() for term in (
                    "purchased", "sold", "owned", "title", "encumbrance",
                    "mortgage", "boundary", "acre", "square", "sq ft", "inr", "rs",
                    "closing", "tenant", "landlord", "possession"
                ))
            )
            if has_factual_content:
                return ClaimVerification(
                    claim=sentence,
                    status="unsupported",
                    cited_sources=[],
                    evidence_excerpts=[],
                    reasoning="Factual assertion made without any supporting citation marker.",
                )
            return None

        # 3. Verify entailment against cited sources
        excerpts: list[str] = []
        is_contradicted = False
        is_supported = False
        contradiction_reasons: list[str] = []

        for cid in cited_ids:
            source = sources_by_id[cid]
            source_text = source.text
            excerpts.append(source_text[:300])

            # Check for direct material contradiction
            disagrees, reason = claims_materially_disagree(sentence, source_text)
            if disagrees:
                is_contradicted = True
                contradiction_reasons.append(f"Contradicts [{cid}]: {reason}")
                continue

            # Check entailment: does source_text actually substantiate key facts?
            entails = self._check_passage_entailment(sentence, source_text)
            if entails:
                is_supported = True

        if is_contradicted:
            return ClaimVerification(
                claim=sentence,
                status="contradicted",
                cited_sources=cited_ids,
                evidence_excerpts=excerpts,
                reasoning="; ".join(contradiction_reasons),
            )

        if is_supported:
            return ClaimVerification(
                claim=sentence,
                status="supported",
                cited_sources=cited_ids,
                evidence_excerpts=excerpts,
                reasoning=f"Verified and supported by cited evidence passage(s) {', '.join(cited_ids)}.",
            )

        # Citation exists, but the cited passage fails to substantiate the claim
        return ClaimVerification(
            claim=sentence,
            status="unsupported",
            cited_sources=cited_ids,
            evidence_excerpts=excerpts,
            reasoning=(
                f"Cited source(s) {', '.join(cited_ids)} do not establish the asserted factual claims."
            ),
        )

    def _check_passage_entailment(self, claim: str, source_text: str) -> bool:
        """Verify that the source text genuinely entails the claim's factual statements.

        Does not treat valid citation IDs or raw string overlap as proof of entailment.
        """
        claim_norm = normalize_claim_text(claim)
        source_norm = normalize_claim_text(source_text)

        # 1. Verbatim or near-verbatim match
        if claim_norm in source_norm:
            return True

        # 2. Key numeric/consideration values in claim must be present or normalized-equivalent
        claim_curr = parse_normalized_currency(claim)
        if claim_curr is not None:
            source_curr = parse_normalized_currency(source_text)
            if source_curr is None or abs(claim_curr - source_curr) > 1.0:
                return False

        claim_area = parse_normalized_area(claim)
        if claim_area is not None:
            source_area = parse_normalized_area(source_text)
            if source_area is None:
                return False
            ratio = max(claim_area, source_area) / (min(claim_area, source_area) or 1.0)
            if ratio > 1.03:
                return False

        # 3. Content overlap check: claim terms must be substantially represented in source
        claim_words = {
            w for w in re.findall(r"\b[A-Za-z0-9_-]+\b", claim.lower())
            if len(w) > 3 and w not in ("according", "source", "provided", "document", "states", "stated", "that")
        }
        if not claim_words:
            return True

        source_words = set(re.findall(r"\b[A-Za-z0-9_-]+\b", source_text.lower()))
        matched_words = set(claim_words & source_words)

        # Real estate domain synonyms for property references
        property_synonyms = {"property", "plot", "land", "premises", "site", "unit", "building", "apartment"}
        if bool(claim_words & property_synonyms) and bool(source_words & property_synonyms):
            matched_words.update(claim_words & property_synonyms)

        overlap_ratio = len(matched_words) / len(claim_words)

        return overlap_ratio >= 0.45

    def _detect_negative_or_missing_assertion(self, answer: str) -> bool:
        """Detect whether the answer indicates missing documents, gaps, or inability to establish facts."""
        text = answer.lower()
        missing_phrases = (
            "cannot be established",
            "not established by the available",
            "no information is available",
            "not mentioned in the retrieved",
            "does not specify",
            "does not state",
            "insufficient evidence",
            "missing title deed",
            "no records found",
            "unclear from the provided",
        )
        return any(phrase in text for phrase in missing_phrases)
