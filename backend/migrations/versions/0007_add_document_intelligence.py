"""Add document intelligence columns to documents table.

Revision ID: 0007_add_document_intelligence
Revises: 0006_add_property_risk_assessments
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_add_document_intelligence"
down_revision: Union[str, None] = "0006_add_property_risk_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expand status column length from 16 to 32 to support longer status values
    op.alter_column(
        "documents",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )

    # 2. Add classification columns
    op.add_column("documents", sa.Column("classification_category", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("classification_reasoning", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "classification_manually_corrected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 3. Add OCR columns
    op.add_column("documents", sa.Column("ocr_status", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("ocr_page_count", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("ocr_metadata", JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 4. Add extracted tables and duplicate detection columns
    op.add_column(
        "documents",
        sa.Column(
            "extracted_tables",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "near_duplicates",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "near_duplicates")
    op.drop_column("documents", "extracted_tables")
    op.drop_column("documents", "ocr_metadata")
    op.drop_column("documents", "ocr_page_count")
    op.drop_column("documents", "ocr_status")
    op.drop_column("documents", "classification_manually_corrected")
    op.drop_column("documents", "classification_reasoning")
    op.drop_column("documents", "classification_confidence")
    op.drop_column("documents", "classification_category")

    op.alter_column(
        "documents",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )

