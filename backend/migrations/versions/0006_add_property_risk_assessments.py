"""Add property_risk_assessments and property_risk_findings tables.

Revision ID: 0006_add_property_risk_assessments
Revises: 0005_add_property_extractions
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_add_property_risk_assessments"
down_revision: Union[str, None] = "0005_add_property_extractions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create property_risk_assessments table
    op.create_table(
        "property_risk_assessments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column(
            "document_hashes",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "summary",
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
            name="fk_property_risk_assessments_property_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("property_id", name="uq_property_risk_assessments_property_id"),
    )
    op.create_index(
        "ix_property_risk_assessments_property_id",
        "property_risk_assessments",
        ["property_id"],
        unique=False,
    )

    # 2. Create property_risk_findings table
    op.create_table(
        "property_risk_findings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column(
            "evidence",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "affected_facts",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("user_notes", sa.Text(), nullable=True),
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
            ["assessment_id"],
            ["property_risk_assessments.id"],
            name="fk_property_risk_findings_assessment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="fk_property_risk_findings_property_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_property_risk_findings_assessment_id",
        "property_risk_findings",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        "ix_property_risk_findings_property_id",
        "property_risk_findings",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        "ix_property_risk_findings_rule_key",
        "property_risk_findings",
        ["rule_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_property_risk_findings_rule_key", table_name="property_risk_findings")
    op.drop_index("ix_property_risk_findings_property_id", table_name="property_risk_findings")
    op.drop_index("ix_property_risk_findings_assessment_id", table_name="property_risk_findings")
    op.drop_table("property_risk_findings")

    op.drop_index("ix_property_risk_assessments_property_id", table_name="property_risk_assessments")
    op.drop_table("property_risk_assessments")

