"""Add a GIN full-text index used by hybrid retrieval.

Revision ID: 0002_phase4_retrieval
Revises: 0001_phase3_vectors
Create Date: 2026-10-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_phase4_retrieval"
down_revision: Union[str, None] = "0001_phase3_vectors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_chunks_text_fts "
        "ON chunks USING gin (to_tsvector('english', text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_fts")
