"""Persistent document, chunk, embedding, and retrieval-index models.

The embedding column uses pgvector's ``vector`` type. Its dimension is fixed by
the database migration (768 for the default local model). Mismatches between the
configured model dimensions and the physical column are detected at runtime with
a clear configuration error instead of attempting an incompatible insert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SCHEMA_VECTOR_DIMENSIONS = 768


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "content_sha256",
            "filename",
            name="uq_documents_owner_content_filename",
        ),
        CheckConstraint(
            "status IN ('processed', 'ocr_required')",
            name="ck_documents_status",
        ),
        CheckConstraint("chunk_count >= 0", name="ck_documents_chunk_count"),
        CheckConstraint(
            "extracted_characters >= 0",
            name="ck_documents_extracted_characters",
        ),
        Index("ix_documents_owner_id", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_characters: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunks_document_id_chunk_index"
        ),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index"),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1", name="ck_chunks_page_number"
        ),
        CheckConstraint(
            "start_offset IS NULL OR start_offset >= 0", name="ck_chunks_start_offset"
        ),
        CheckConstraint(
            "end_offset IS NULL OR end_offset >= 0", name="ck_chunks_end_offset"
        ),
        Index("ix_chunks_document_id", "document_id"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_chunks_text_fts",
            sql_text("to_tsvector('english', text)"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ``metadata`` is reserved by SQLAlchemy's declarative API, so the Python
    # attribute differs while the database column keeps the Phase 2 name.
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(SCHEMA_VECTOR_DIMENSIONS), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
