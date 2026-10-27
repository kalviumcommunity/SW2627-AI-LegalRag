"""Conservative material-disagreement checks for grounded RAG.

This module deliberately does not claim natural-language inference. It verifies
only that two quoted claims are present in retrieved text and expose a narrow,
explainable signal of disagreement: opposite polarity on shared subject terms,
different numeric values for the same subjects, or a small set of explicit
antonym pairs. Anything else is treated as unverified and the caller must not
assert ``conflicting_evidence``.
"""

from __future__ import annotations

import re

_NEGATION_RE = re.compile(
    r"\b(?:no|not|none|never|without|absent|nil|zero|unencumbered|"
    r"free\s+from|clear\s+of|does\s+not|do\s+not|did\s+not|"
    r"is\s+not|are\s+not|was\s+not|were\s+not)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
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
    "with",
}
_NEGATION_SCOPE_PATTERNS = (
    re.compile(
        r"\b(?:no|none|without|absent|zero)\b"
        r"((?:\s+[A-Za-z][A-Za-z0-9-]*){1,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:free\s+from|clear\s+of)\b"
        r"((?:\s+[A-Za-z][A-Za-z0-9-]*){1,5})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are|was|were|does|do|did|has|have|had|will|would|"
        r"can|could)\s+not\b"
        r"((?:\s+[A-Za-z][A-Za-z0-9-]*){1,5})",
        re.IGNORECASE,
    ),
)

# Words that are too generic to establish a shared subject on their own.
_GENERIC_TERMS = {
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

_ANTONYM_PAIRS = (
    ("clear", "encumbered"),
    ("valid", "invalid"),
    ("approved", "rejected"),
    ("approved", "revoked"),
    ("owned", "leased"),
    ("owned", "rented"),
    ("occupied", "vacant"),
)


def normalize_claim_text(text: str) -> str:
    """Normalize whitespace, case, and terminal punctuation for containment."""
    return " ".join((text or "").split()).casefold().strip(" .,;:")


def claim_is_verbatim(claim: str, source_text: str) -> bool:
    """True when the claim is a normalized substring of the source text."""
    cleaned_claim = normalize_claim_text(claim)
    if not cleaned_claim:
        return False
    return cleaned_claim in normalize_claim_text(source_text)


def _stem_term(term: str) -> str:
    if len(term) > 4 and term.endswith("ies"):
        return f"{term[:-3]}y"
    if len(term) > 4 and term.endswith(("ses", "xes", "zes", "ches", "shes")):
        return term[:-2]
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        return term[:-1]
    return term


def _content_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _WORD_RE.findall(text or ""):
        if raw.isdigit():
            continue
        term = _stem_term(raw.casefold())
        if len(term) < 3 or term in _STOP_WORDS or term in _GENERIC_TERMS:
            continue
        terms.add(term)
    return terms


def _negated_terms(text: str) -> set[str]:
    targets: set[str] = set()
    for pattern in _NEGATION_SCOPE_PATTERNS:
        for match in pattern.finditer(text or ""):
            targets |= _content_terms(match.group(1))
    return targets


def _is_year(value: str) -> bool:
    try:
        number = int(value)
    except ValueError:
        return False
    return 1900 <= number <= 2100


def _numbers(text: str) -> set[str]:
    return {
        value.replace(",", "")
        for value in _NUMBER_RE.findall(text or "")
        if not _is_year(value.replace(",", ""))
    }


def claims_materially_disagree(
    left: str,
    right: str,
) -> tuple[bool, str]:
    """Return a conservative disagreement verdict and a short reason.

    The function is intentionally asymmetric about what it accepts. It can
    miss a real disagreement (false negative), which causes the caller to
    downgrade to a cautious status. It should not usually invent one.
    """
    left_terms = _content_terms(left)
    right_terms = _content_terms(right)
    shared = left_terms & right_terms
    if not shared:
        return False, "the claims do not share a specific subject term"

    left_negated = bool(_NEGATION_RE.search(left or ""))
    right_negated = bool(_NEGATION_RE.search(right or ""))
    if left_negated != right_negated:
        left_targets = _negated_terms(left)
        right_targets = _negated_terms(right)
        if (left_targets & right_terms) or (right_targets & left_terms):
            return True, "opposite polarity on a shared subject term"

    left_numbers = _numbers(left)
    right_numbers = _numbers(right)
    if (
        len(left_numbers) == 1
        and len(right_numbers) == 1
        and left_numbers != right_numbers
    ):
        return True, "different numeric values for shared subject terms"

    left_folded = (left or "").casefold()
    right_folded = (right or "").casefold()
    for first, second in _ANTONYM_PAIRS:
        if (
            first in left_folded
            and second in right_folded
        ) or (
            second in left_folded
            and first in right_folded
        ):
            return True, f"opposing terms '{first}' and '{second}'"

    if left_negated and right_negated:
        return False, "both claims are negated or qualified"
    return False, "no verifiable material disagreement"
