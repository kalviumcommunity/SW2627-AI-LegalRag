"""Duplicate document detection service.

Identifies exact duplicates (via SHA-256 content hash) and near-duplicates
(via token n-gram Jaccard / word overlap similarity) while strictly preserving
tenant isolation (never matching across different users) and remaining
entirely non-destructive.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.schemas.document_intelligence import (
    DocumentDuplicatesResponse,
    DuplicateMatch,
)


class DuplicateDetectionService:
    """Detects exact and near-duplicate documents within a user's repository."""

    def __init__(self, near_duplicate_threshold: float = 0.80) -> None:
        self.threshold = near_duplicate_threshold

    def detect_duplicates(
        self,
        session: Session,
        document_id: str,
        owner_id: str,
        content_sha256: str,
        document_text: str | None = None,
    ) -> DocumentDuplicatesResponse:
        """Find exact and near duplicates for a document owned by owner_id."""
        exact_matches: list[DuplicateMatch] = []
        near_matches: list[DuplicateMatch] = []

        # 1. Exact duplicate query: same owner_id, same content_sha256, different document_id
        exact_stmt = (
            select(Document)
            .where(
                Document.owner_id == owner_id,
                Document.content_sha256 == content_sha256,
                Document.id != document_id,
            )
        )
        exact_docs = session.scalars(exact_stmt).all()

        for d in exact_docs:
            exact_matches.append(
                DuplicateMatch(
                    document_id=d.id,
                    filename=d.filename,
                    match_type="exact",
                    similarity=1.0,
                    reasons=[
                        f"Identical file binary content (matching SHA-256 hash {content_sha256[:12]}...)",
                    ],
                    created_at=d.created_at,
                )
            )

        # 2. Near duplicate detection: compare against other documents of the same owner
        if document_text and len(document_text.strip()) > 100:
            current_tokens = self._tokenize(document_text)
            current_shingles = self._get_shingles(current_tokens, n=3)

            if current_shingles:
                # Query candidate documents of the same owner (excluding exact matches and self)
                candidate_stmt = (
                    select(Document)
                    .where(
                        Document.owner_id == owner_id,
                        Document.id != document_id,
                        Document.content_sha256 != content_sha256,
                    )
                )
                candidate_docs = session.scalars(candidate_stmt).all()

                for cand in candidate_docs:
                    # Retrieve candidate chunks or text
                    cand_text = " ".join(c.text for c in cand.chunks if c.text)
                    if not cand_text:
                        from app.db.models import Chunk
                        chunk_texts = session.scalars(select(Chunk.text).where(Chunk.document_id == cand.id)).all()
                        cand_text = " ".join(t for t in chunk_texts if t)
                    if len(cand_text.strip()) < 100:
                        continue

                    cand_tokens = self._tokenize(cand_text)
                    cand_shingles = self._get_shingles(cand_tokens, n=3)

                    similarity = self._jaccard_similarity(current_shingles, cand_shingles)
                    if similarity >= self.threshold:
                        reasons = [
                            f"Near-identical textual content ({int(similarity * 100)}% structural overlap)",
                        ]
                        if cand.filename != "":
                            reasons.append(f"Previously uploaded as '{cand.filename}'")

                        near_matches.append(
                            DuplicateMatch(
                                document_id=cand.id,
                                filename=cand.filename,
                                match_type="near_duplicate",
                                similarity=round(similarity, 3),
                                reasons=reasons,
                                created_at=cand.created_at,
                            )
                        )

        # Sort near-matches by similarity descending
        near_matches.sort(key=lambda x: x.similarity, reverse=True)

        return DocumentDuplicatesResponse(
            document_id=document_id,
            has_duplicates=bool(exact_matches or near_matches),
            exact_matches=exact_matches,
            near_matches=near_matches,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Normalize text into lowercase alphanumeric words."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return [w for w in cleaned.split() if len(w) > 2]

    @staticmethod
    def _get_shingles(tokens: list[str], n: int = 3) -> set[tuple[str, ...]]:
        """Create word n-grams (shingles) for similarity calculation."""
        if len(tokens) < n:
            return set()
        return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """Calculate Jaccard similarity: |A ∩ B| / |A ∪ B|."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        if union == 0:
            return 0.0
        return intersection / union

