"""Unit tests for cleaning and character-based chunking."""

import pytest

from app.services.chunking import ChunkingConfig, chunk_text
from app.services.text_cleaning import clean_text


def test_short_text_is_a_single_chunk_with_exact_offsets():
    text = "A short property note with a date: 2026-10-21."
    chunks = chunk_text(text, ChunkingConfig(chunk_size_chars=800, overlap_chars=100))
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == text
    assert chunks[0].start_offset == 0
    assert chunks[0].end_offset == len(text)


def test_empty_whitespace_text_produces_no_chunks():
    config = ChunkingConfig(chunk_size_chars=50, overlap_chars=10)
    assert chunk_text("", config) == []
    assert chunk_text("   \n\n\t ", config) == []


def test_chunk_size_and_overlap_are_respected():
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_text(text, ChunkingConfig(chunk_size_chars=10, overlap_chars=3))
    assert [chunk.start_offset for chunk in chunks] == [0, 7, 14, 21]
    assert [chunk.end_offset for chunk in chunks] == [10, 17, 24, 26]
    for previous, current in zip(chunks, chunks[1:]):
        assert previous.text[-3:] == current.text[:3]
    for chunk in chunks:
        assert len(chunk.text) <= 10
        assert text[chunk.start_offset : chunk.end_offset] == chunk.text


def test_prefers_paragraph_boundaries_over_hard_cuts():
    text = "First clause has meaningful words.\n\nSecond clause has more words."
    chunks = chunk_text(text, ChunkingConfig(chunk_size_chars=40, overlap_chars=0))
    assert len(chunks) >= 2
    assert chunks[0].text == "First clause has meaningful words."
    assert chunks[1].text.startswith("Second clause")


def test_long_unbroken_text_is_hard_cut_without_looping():
    text = "x" * 55
    chunks = chunk_text(text, ChunkingConfig(chunk_size_chars=10, overlap_chars=0))
    assert len(chunks) == 6
    assert [chunk.start_offset for chunk in chunks] == [0, 10, 20, 30, 40, 50]


def test_large_overlap_still_advances_without_duplicate_only_chunks():
    text = "abcdefghijklmnopqrstuvwxyz0123456789"
    chunks = chunk_text(text, ChunkingConfig(chunk_size_chars=10, overlap_chars=9))
    assert len(chunks) > 1
    assert chunks[-1].end_offset == len(text)
    previous_end = -1
    for chunk in chunks:
        assert chunk.end_offset > previous_end
        assert chunk.end_offset > chunk.start_offset
        previous_end = chunk.end_offset


def test_invalid_chunk_configuration_is_rejected():
    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_chars=0)
    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_chars=10, overlap_chars=10)
    with pytest.raises(ValueError):
        ChunkingConfig(chunk_size_chars=10, overlap_chars=-1)


def test_cleaning_normalizes_whitespace_without_losing_substance():
    raw = (
        "Clause 4.2:\r\n"
        "Payment of \u20b91,00,000 on 2026-01-01.\x00   \r\n\r\n\r\n"
        "Survey No. 123/4A \u2014 seller: A. Kumar"
    )
    cleaned = clean_text(raw)
    assert "\r" not in cleaned
    assert "\x00" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "Clause 4.2:" in cleaned
    assert "\u20b91,00,000" in cleaned
    assert "2026-01-01" in cleaned
    assert "Survey No. 123/4A" in cleaned
    assert "A. Kumar" in cleaned
    assert clean_text(cleaned) == cleaned


def test_unicode_and_line_endings_are_normalized_consistently():
    raw = "Cafe\u0301\r\nNo\u00a0vacancy\u200b  here"
    cleaned = clean_text(raw)
    assert cleaned == "Café\nNo vacancy here"
