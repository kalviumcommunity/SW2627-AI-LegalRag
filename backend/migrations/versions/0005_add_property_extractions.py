"""Add property_extractions table for structured information extraction.

Revision ID: 0005_add_property_extractions
Revises: 0004_add_properties_and_document_association
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005_add_property_extractions"
down_revision: Union[str, None] = "0004_add_properties_and_document_association"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "property_extractions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column(
            "extracted_data",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "document_hashes",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="fk_property_extractions_property_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("property_id", name="uq_property_extractions_property_id"),
    )
    op.create_index(
        "ix_property_extractions_property_id",
        "property_extractions",
        ["property_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_property_extractions_property_id", table_name="property_extractions")
    op.drop_table("property_extractions")

