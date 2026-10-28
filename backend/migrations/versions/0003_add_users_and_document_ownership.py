"""Add users table and document ownership.

Revision ID: 0003_add_users_and_document_ownership
Revises: 0002_phase4_retrieval
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_users_and_document_ownership"
down_revision: Union[str, None] = "0002_phase4_retrieval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stable Argon2id hash for the legacy system user (account disabled: is_active=False)
LEGACY_USER_ID = "usr_legacy_admin"
LEGACY_USER_EMAIL = "legacy_admin@propertyintel.internal"
LEGACY_USER_HASH = "$argon2id$v=19$m=65536,t=2,p=2$1i6fQ3O3L1+10P3x+Z7t8A$7548jD16n8jD29uVzJ7+9k4YjM6L8vP9xK3yQ2mN8wE"


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Add nullable owner_id column to documents table first
    op.add_column(
        "documents",
        sa.Column("owner_id", sa.String(length=64), nullable=True),
    )

    # 3. Create dedicated legacy system user to safely own existing pre-auth documents
    #    Existing documents are preserved and explicitly NOT made publicly accessible.
    users_table = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": LEGACY_USER_ID,
                "email": LEGACY_USER_EMAIL,
                "hashed_password": LEGACY_USER_HASH,
                "is_active": False,
            }
        ],
    )

    # 4. Migrate any existing unowned documents to the legacy system user
    op.execute(
        sa.text(
            f"UPDATE documents SET owner_id = '{LEGACY_USER_ID}' WHERE owner_id IS NULL"
        )
    )

    # 5. Enforce NOT NULL on documents.owner_id
    op.alter_column("documents", "owner_id", nullable=False)

    # 6. Add foreign key constraint to users(id)
    op.create_foreign_key(
        "fk_documents_owner_id_users",
        "documents",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 7. Add index on documents(owner_id) for fast user document listing and joins
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"], unique=False)

    # 8. Update unique constraint: drop old global constraint and replace with per-user uniqueness
    op.drop_constraint("uq_documents_content_sha256_filename", "documents", type_="unique")
    op.create_unique_constraint(
        "uq_documents_owner_content_filename",
        "documents",
        ["owner_id", "content_sha256", "filename"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_owner_content_filename", "documents", type_="unique")
    op.create_unique_constraint(
        "uq_documents_content_sha256_filename",
        "documents",
        ["content_sha256", "filename"],
    )
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_constraint("fk_documents_owner_id_users", "documents", type_="foreignkey")
    op.drop_column("documents", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
