"""Add properties table and document associations.

Revision ID: 0004_add_properties_and_document_association
Revises: 0003_add_users_and_document_ownership
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_properties_and_docs"
down_revision: Union[str, None] = "0003_users_and_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create properties table
    op.create_table(
        "properties",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("property_type", sa.String(length=64), nullable=True),
        sa.Column("area", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(length=32), nullable=True),
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
            ["owner_id"],
            ["users.id"],
            name="fk_properties_owner_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_properties_owner_id", "properties", ["owner_id"], unique=False)

    # 2. Add nullable property_id column to documents table
    op.add_column(
        "documents",
        sa.Column("property_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_property_id_properties",
        "documents",
        "properties",
        ["property_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_property_id", "documents", ["property_id"], unique=False)

    # 3. Create property_documents association table
    op.create_table(
        "property_documents",
        sa.Column("property_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("property_id", "document_id"),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="fk_property_documents_property_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_property_documents_document_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_property_documents_property_id",
        "property_documents",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        "ix_property_documents_document_id",
        "property_documents",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_property_documents_document_id", table_name="property_documents")
    op.drop_index("ix_property_documents_property_id", table_name="property_documents")
    op.drop_table("property_documents")

    op.drop_index("ix_documents_property_id", table_name="documents")
    op.drop_constraint(
        "fk_documents_property_id_properties", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "property_id")

    op.drop_index("ix_properties_owner_id", table_name="properties")
    op.drop_table("properties")
