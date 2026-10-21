"""Configurable, character-based text chunking with overlap.

The chunker is deliberately independent of embeddings and vector stores. It
prefers paragraph, sentence, and line boundaries, falls back to whitespace, and
only hard-cuts when a long passage has no usable boundary.

Character counts are character counts, not token counts. The default size and
overlap are chosen to approximate 800/120 English tokens without assuming a
specific tokenizer at runtime.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n+")
_SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+")
_LINE_BREAK_RE = re.compile(r"\n")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunking parameters shared by the service and API layer."""

    chunk_size_chars: int
    overlap_chars: int = 0
    min_split_ratio: float = 0.5
    strategy: str = "character"

    def __post_init__(self) -> None:
        if self.chunk_size_chars <= 0:
            raise ValueError("chunk_size_chars must be greater than zero")
        if self.overlap_chars < 0:
            raise ValueError("overlap_chars must not be negative")
        if self.overlap_chars >= self.chunk_size_chars:
            raise ValueError("overlap_chars must be smaller than chunk_size_chars")
        if not 0 < self.min_split_ratio <= 1:
            raise ValueError("min_split_ratio must be in (0, 1]")


@dataclass(frozen=True)
class TextChunk:
    """A chunk with offsets into the cleaned document text."""

    index: int
    text: str
    start_offset: int
    end_offset: int


def _break_positions(text: str) -> dict[str, list[int]]:
    return {
        "paragraph": [match.end() for match in _PARAGRAPH_BREAK_RE.finditer(text)],
        "sentence": [match.end() for match in _SENTENCE_BREAK_RE.finditer(text)],
        "line": [match.end() for match in _LINE_BREAK_RE.finditer(text)],
        "whitespace": [match.end() for match in _WHITESPACE_RE.finditer(text)],
    }


def _last_in_window(positions: list[int], low: int, high: int) -> int | None:
    index = bisect.bisect_right(positions, high) - 1
    if index >= 0 and positions[index] >= low:
        return positions[index]
    return None


def _find_split(
    boundaries: dict[str, list[int]], desired_end: int, minimum: int
) -> int:
    for tier in ("paragraph", "sentence", "line", "whitespace"):
        position = _last_in_window(boundaries[tier], minimum, desired_end)
        if position is not None:
            return position
    return desired_end


def chunk_text(text: str, config: ChunkingConfig) -> list[TextChunk]:
    """Split ``text`` into overlapping chunks that respect boundaries."""
    if not text or not text.strip():
        return []

    boundaries = _break_positions(text)
    length = len(text)
    minimum_window = max(1, int(config.chunk_size_chars * config.min_split_ratio))
    chunks: list[TextChunk] = []

    start = 0
    while start < length:
        if length - start <= config.chunk_size_chars:
            end = length
        else:
            desired_end = start + config.chunk_size_chars
            end = _find_split(boundaries, desired_end, start + minimum_window)

        # Guard against a boundary function that fails to advance.
        if end <= start:
            end = min(length, start + config.chunk_size_chars)

        raw = text[start:end]
        leading_trim = len(raw) - len(raw.lstrip())
        trailing_trim = len(raw) - len(raw.rstrip())
        chunk_start = start + leading_trim
        chunk_end = end - trailing_trim
        chunk_value = text[chunk_start:chunk_end]

        if chunk_value:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=chunk_value,
                    start_offset=chunk_start,
                    end_offset=chunk_end,
                )
            )

        if end >= length:
            break

        next_start = end - config.overlap_chars
        if next_start <= start:
            # Overlap must never prevent forward progress.
            next_start = end
        start = next_start

    return chunks
