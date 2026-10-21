"""Conservative text normalization for extracted property documents.

Cleaning deliberately preserves wording, numbers, dates, identifiers, clause
punctuation, headings, and paragraph boundaries. It only removes characters and
whitespace that carry no substantive meaning.
"""

from __future__ import annotations

import re
import unicodedata

_NEWLINE_RE = re.compile(r"\r\n?|\u2028|\u2029|\x0b|\x0c")
_HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")
# Zero-width space and BOM carry no meaning; ZWJ/ZWNJ are kept because they
# can be meaningful in Indic scripts and names.
_INVISIBLE_RE = re.compile(r"[\u200b\ufeff]")
_NULL_AND_CONTROL_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)

# Characters that are visually equivalent to a normal space but are not
# substantive; normalizing them improves retrieval without changing meaning.
_SPACE_VARIANTS = {
    "\u00a0": " ",
    "\u1680": " ",
    "\u2000": " ",
    "\u2001": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u2004": " ",
    "\u2005": " ",
    "\u2006": " ",
    "\u2007": " ",
    "\u2008": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
    "\u205f": " ",
    "\u3000": " ",
}


def clean_text(text: str) -> str:
    """Return conservative, normalized text.

    The function is idempotent: cleaning already-clean text returns the same
    value. It never lowercases, strips punctuation, or rewrites sentences.
    """
    if not text:
        return ""

    normalized = unicodedata.normalize("NFC", text)
    normalized = _NEWLINE_RE.sub("\n", normalized)
    normalized = _INVISIBLE_RE.sub("", normalized)
    normalized = _NULL_AND_CONTROL_RE.sub("", normalized)
    for source, replacement in _SPACE_VARIANTS.items():
        normalized = normalized.replace(source, replacement)

    normalized = _HORIZONTAL_WHITESPACE_RE.sub(" ", normalized)

    lines = [line.strip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)
    normalized = _EXCESS_BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()
