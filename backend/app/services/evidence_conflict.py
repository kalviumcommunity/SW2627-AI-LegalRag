"""Conservative material-disagreement checks and cross-document conflict detection.

This module provides explainable verification and conflict detection across
property documents. It explicitly handles:
- Cross-document enforcement (only distinct document IDs count as conflicts).
- Unit conversion (e.g. sq. meters vs sq. feet, Crores vs Lakhs vs absolute INR).
- Chronological sequencing vs concurrent contradictions.
- Antonym and polarity detection.
- Contextual financial differences (e.g. deposit vs monthly rent).
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.schemas.rag import ConflictSource, CrossDocumentConflict

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
    ("unencumbered", "mortgaged"),
    ("free from encumbrances", "encumbered"),
    ("marketable title", "defective title"),
    ("discharged", "registered mortgage"),
    ("sole owner", "joint owners"),
    ("sole ownership", "co-ownership"),
)

# Area parsing regex
_AREA_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(sq\.?\s*m(?:eters?|etres?)?|square\s*meters?|square\s*metres?|sq\.?\s*ft|square\s*feet|sft|acres?|gunthas?|guntas?)\b",
    re.IGNORECASE,
)

# Currency / consideration parsing regex
_CURRENCY_RE = re.compile(
    r"(?:(?:INR|Rs\.?|\$|USD)\s*)?(\d+(?:[.,]\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|million|m|k|thousand)?\b",
    re.IGNORECASE,
)

# Date / Year parsing regex
_DATE_YEAR_RE = re.compile(
    r"\b((?:19|20)\d\d)(?:[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01]))?\b"
)


def parse_normalized_area(text: str) -> float | None:
    """Parse property area and convert to square feet for neutral comparison."""
    match = _AREA_RE.search(text or "")
    if not match:
        return None
    val_str, unit = match.group(1).replace(",", ""), match.group(2).lower()
    try:
        val = float(val_str)
    except ValueError:
        return None

    if "m" in unit:  # sq meters
        return val * 10.7639
    if "acre" in unit:
        return val * 43560.0
    if "guntha" in unit or "gunta" in unit:
        return val * 1089.0
    return val  # sq ft


def parse_normalized_currency(text: str) -> float | None:
    """Parse monetary consideration and normalize denominations."""
    for match in _CURRENCY_RE.finditer(text or ""):
        raw_val = match.group(1).replace(",", "")
        scale = match.group(2)
        try:
            val = float(raw_val)
        except ValueError:
            continue

        # Skip bare years parsed as numbers
        if scale is None and 1900 <= val <= 2100:
            continue

        multiplier = 1.0
        if scale:
            s = scale.lower()
            if s in ("crore", "crores", "cr"):
                multiplier = 10_000_000.0
            elif s in ("lakh", "lakhs", "lac", "lacs"):
                multiplier = 100_000.0
            elif s in ("million", "m"):
                multiplier = 1_000_000.0
            elif s in ("thousand", "k"):
                multiplier = 1_000.0
        elif val < 1000 and not any(cur in text.upper() for cur in ("INR", "RS", "$", "USD")):
            # Probably not a consideration figure unless currency or scale present
            continue

        return val * multiplier
    return None


normalize_area = parse_normalized_area
normalize_currency = parse_normalized_currency


def extract_dates_or_years(text: str) -> set[str]:
    """Extract explicit years or ISO-style dates from text."""
    found = set()
    for m in _DATE_YEAR_RE.finditer(text or ""):
        found.add(m.group(0))
    return found


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
    """Return an explainable disagreement verdict and short reason.

    Distinguishes genuine contradictions from different measurement units,
    chronological dates, or financial contexts.
    """
    left_terms = _content_terms(left)
    right_terms = _content_terms(right)
    shared = left_terms & right_terms
    if not shared:
        return False, "the claims do not share a specific subject term"

    # Contextual distinction: security deposit vs monthly rent
    left_lower = left.lower()
    right_lower = right.lower()
    if ("deposit" in left_lower and "rent" in right_lower and "deposit" not in right_lower) or (
        "deposit" in right_lower and "rent" in left_lower and "deposit" not in left_lower
    ):
        return False, "distinct financial obligations (security deposit vs rent)"

    # Unit check: Area
    left_area = parse_normalized_area(left)
    right_area = parse_normalized_area(right)
    if left_area is not None and right_area is not None and ("area" in shared or "built" in shared or "super" in shared or "plot" in shared):
        ratio = max(left_area, right_area) / (min(left_area, right_area) or 1.0)
        if ratio <= 1.03:
            return False, "equivalent property area values in different measurement units"
        return True, f"conflicting property area measurements: {left_area:.1f} sq ft vs {right_area:.1f} sq ft"

    # Unit check: Currency / Consideration
    left_curr = parse_normalized_currency(left)
    right_curr = parse_normalized_currency(right)
    if left_curr is not None and right_curr is not None and ("price" in shared or "consideration" in shared or "amount" in shared or "value" in shared or "rent" in shared):
        ratio = max(left_curr, right_curr) / (min(left_curr, right_curr) or 1.0)
        if ratio <= 1.005:  # within rounding tolerance
            return False, "equivalent monetary consideration in different denominations"
        # Check if dates differ (chronological changes over time)
        dates_l = extract_dates_or_years(left)
        dates_r = extract_dates_or_years(right)
        if dates_l and dates_r and not (dates_l & dates_r):
            return False, f"different chronological periods or dates ({list(dates_l)[0]} vs {list(dates_r)[0]})"
        return True, f"different monetary values for shared subject terms ({left_curr:,.0f} vs {right_curr:,.0f})"

    # Chronological distinction for generic numbers/statuses
    dates_l = extract_dates_or_years(left)
    dates_r = extract_dates_or_years(right)
    if dates_l and dates_r and not (dates_l & dates_r):
        if any(term in shared for term in ("valuation", "assessment", "tax", "rent", "rate")):
            return False, f"different chronological periods ({list(dates_l)[0]} vs {list(dates_r)[0]})"

    # Polarity check
    left_negated = bool(_NEGATION_RE.search(left or ""))
    right_negated = bool(_NEGATION_RE.search(right or ""))
    if left_negated != right_negated:
        left_targets = _negated_terms(left)
        right_targets = _negated_terms(right)
        if (left_targets & right_terms) or (right_targets & left_terms):
            return True, "opposite polarity on a shared subject term"

    # Numeric check
    left_numbers = _numbers(left)
    right_numbers = _numbers(right)
    if (
        len(left_numbers) == 1
        and len(right_numbers) == 1
        and left_numbers != right_numbers
    ):
        return True, "different numeric values for shared subject terms"

    # Antonym pairs
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


def detect_cross_document_conflicts(
    sources: Sequence[Any],
) -> list[CrossDocumentConflict]:
    """Detect material contradictions between evidence from DISTINCT documents.

    Multiple chunks from the SAME document do NOT count as independent conflicting sources.
    """
    conflicts: list[CrossDocumentConflict] = []
    seen_pairs: set[tuple[str, str]] = set()

    for i in range(len(sources)):
        src_a = sources[i]
        res_a = getattr(src_a, "result", src_a)
        meta_a = getattr(res_a, "metadata", None)
        doc_a_id = getattr(res_a, "document_id", "")
        cit_a = getattr(src_a, "source_id", f"S{i+1}")
        text_a = getattr(src_a, "text", getattr(res_a, "text", ""))
        fn_a = getattr(meta_a, "filename", "document_a") if meta_a else "document_a"
        pg_a = getattr(meta_a, "page_number", None) if meta_a else None
        pgs_a = getattr(meta_a, "page_numbers", []) if meta_a else []

        for j in range(i + 1, len(sources)):
            src_b = sources[j]
            res_b = getattr(src_b, "result", src_b)
            meta_b = getattr(res_b, "metadata", None)
            doc_b_id = getattr(res_b, "document_id", "")
            cit_b = getattr(src_b, "source_id", f"S{j+1}")
            text_b = getattr(src_b, "text", getattr(res_b, "text", ""))
            fn_b = getattr(meta_b, "filename", "document_b") if meta_b else "document_b"
            pg_b = getattr(meta_b, "page_number", None) if meta_b else None
            pgs_b = getattr(meta_b, "page_numbers", []) if meta_b else []

            # CRITICAL: Multiple chunks from the same document do NOT count as cross-document conflict
            if not doc_a_id or not doc_b_id or doc_a_id == doc_b_id:
                continue

            pair_key = tuple(sorted([f"{doc_a_id}:{cit_a}", f"{doc_b_id}:{cit_b}"]))
            if pair_key in seen_pairs:
                continue

            # Compare sentences / clauses in text_a and text_b
            sentences_a = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text_a) if len(s.strip()) > 15]
            sentences_b = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text_b) if len(s.strip()) > 15]

            found_disagreement = False
            for sa in sentences_a:
                if found_disagreement:
                    break
                for sb in sentences_b:
                    disagrees, reason = claims_materially_disagree(sa, sb)
                    if disagrees:
                        # Determine topic
                        combined_text = (sa + " " + sb).lower()
                        if any(w in combined_text for w in ("price", "consideration", "amount", "rs", "inr", "$", "lakh", "crore", "rent")):
                            topic = "financial_consideration"
                        elif any(w in combined_text for w in ("area", "sq ft", "sq.m", "acre", "guntha", "extent", "boundary")):
                            topic = "property_area"
                        elif any(w in combined_text for w in ("owner", "ownership", "title", "vendor", "purchaser", "lessee", "lessor")):
                            topic = "ownership_status"
                        elif any(w in combined_text for w in ("mortgage", "encumbrance", "lien", "charge", "bank", "clear")):
                            topic = "encumbrance_status"
                        elif any(w in combined_text for w in ("approval", "sanction", "permit", "noc", "commencement")):
                            topic = "approval_status"
                        else:
                            topic = "contractual_terms"

                        conflict = CrossDocumentConflict(
                            topic=topic,
                            description=f"Material contradiction between distinct documents ({fn_a} vs {fn_b}): {reason}.",
                            source_a=ConflictSource(
                                document_id=doc_a_id,
                                filename=fn_a,
                                citation_id=cit_a,
                                quote=sa[:300],
                                page_number=pg_a,
                                page_numbers=pgs_a,
                            ),
                            source_b=ConflictSource(
                                document_id=doc_b_id,
                                filename=fn_b,
                                citation_id=cit_b,
                                quote=sb[:300],
                                page_number=pg_b,
                                page_numbers=pgs_b,
                            ),
                            resolution_note=(
                                "Conflicting records across distinct documents; neither document "
                                "is assumed legally authoritative without judicial or title determination."
                            ),
                        )
                        conflicts.append(conflict)
                        seen_pairs.add(pair_key)
                        found_disagreement = True
                        break

    return conflicts
