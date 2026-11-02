"""End-to-end document ingestion orchestration with advanced document intelligence.

Pipeline: validation -> secure temporary storage -> extraction (with OCR for images/scanned PDFs)
-> cleaning -> chunking -> bounded embeddings -> legal classification -> table extraction
-> duplicate detection -> durable storage -> structured result.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.db.models import Document
from app.schemas.document_intelligence import DocumentProcessingStatusResponse
from app.schemas.documents import DocumentChunk, IngestResponse
from app.services.chunking import ChunkingConfig, TextChunk, chunk_text
from app.services.document_classification import DocumentClassificationService
from app.services.document_store import (
    DocumentStore,
    create_document_store,
)
from app.services.document_validation import ValidatedUpload, validate_upload
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_errors import (
    DocumentExtractionError,
    DocumentValidationError,
)
from app.services.ocr_service import OcrService
from app.services.table_extraction import TableExtractionService
from app.services.temp_storage import secure_temp_file
from app.services.text_cleaning import clean_text
from app.services.text_extraction import ExtractionResult, get_extractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PageSpan:
    page_number: int
    start_offset: int
    end_offset: int


def _new_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class DocumentIngestionService:
    """Turns a validated upload into traceable chunks and intelligence metadata."""

    def __init__(
        self,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
        store: DocumentStore | None = None,
        ocr_service: OcrService | None = None,
        classifier: DocumentClassificationService | None = None,
        table_extractor: TableExtractionService | None = None,
        duplicate_detector: DuplicateDetectionService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.chunking_config = ChunkingConfig(
            chunk_size_chars=self.settings.document_chunk_size_chars,
            overlap_chars=self.settings.document_chunk_overlap_chars,
            min_split_ratio=self.settings.document_chunk_min_split_ratio,
        )
        self.embedding_service = embedding_service or EmbeddingService(
            self.settings
        )
        self.store = store or create_document_store(self.settings)
        self.ocr_service = ocr_service or OcrService()
        self.classifier = classifier or DocumentClassificationService()
        self.table_extractor = table_extractor or TableExtractionService()
        self.duplicate_detector = duplicate_detector or DuplicateDetectionService()

    def ingest(
        self,
        data: bytes,
        filename: str | None,
        content_type: str | None,
        owner_id: str | None = None,
        property_id: str | None = None,
    ) -> IngestResponse:
        document_id = _new_identifier("doc")
        upload = validate_upload(data, filename, content_type, self.settings)
        content_hash = hashlib.sha256(upload.data).hexdigest()

        try:
            extraction = self._extract(upload)
        except DocumentExtractionError as exc:
            return IngestResponse(
                document_id=document_id,
                filename=upload.filename,
                status="failed",
                extracted_characters=0,
                chunk_count=0,
                chunks=[],
                page_count=None,
                warnings=[],
                detail=exc.message,
            )

        cleaned_pages: list[tuple[int | None, str]] = []
        for page in extraction.pages:
            cleaned = clean_text(page.text)
            if cleaned:
                cleaned_pages.append((page.page_number, cleaned))

        ocr_status: str | None = None
        if upload.source_type == "image":
            ocr_status = "ocr_completed" if cleaned_pages else "ocr_failed"
        elif extraction.requires_ocr:
            ocr_status = "ocr_required"

        if not cleaned_pages:
            if upload.source_type in ("pdf", "image"):
                intel_data: dict[str, Any] = {
                    "ocr_status": ocr_status,
                    "ocr_page_count": extraction.page_count,
                    "classification_category": "Other / Unknown",
                    "classification_confidence": 0.0,
                    "classification_reasoning": "Unreadable or scanned content requiring OCR.",
                    "extracted_tables": [],
                    "near_duplicates": [],
                }
                return self._persist(
                    self._ocr_required(document_id, upload, extraction),
                    content_hash,
                    [],
                    owner_id=owner_id,
                    property_id=property_id,
                    intelligence=intel_data,
                )
            raise DocumentValidationError(
                "The document contains no readable text after cleaning."
            )

        full_text, spans = self._join_pages(cleaned_pages)
        text_chunks = chunk_text(full_text, self.chunking_config)
        if not text_chunks:
            raise DocumentValidationError(
                "The document contains no readable text after cleaning."
            )

        chunks = [
            self._build_chunk(
                document_id=document_id,
                upload=upload,
                extraction=extraction,
                chunk=text_chunk,
                spans=spans,
            )
            for text_chunk in text_chunks
        ]

        # Identical uploads are idempotent
        existing = self.store.find_by_content_hash(
            content_hash, upload.filename, owner_id=owner_id
        )
        if existing is not None:
            if property_id is not None:
                return self.store.save(
                    existing, content_hash, [], owner_id=owner_id, property_id=property_id
                )
            return existing

        # Bounded batch embedding for large documents (e.g. 50 chunks per batch)
        embeddings: list[list[float]] = []
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            chunk_batch = chunks[i : i + batch_size]
            embeddings.extend(self.embedding_service.embed_chunks(chunk_batch))

        # Advanced Intelligence: Document Classification
        classification = self.classifier.classify_document(
            document_id=document_id,
            text=full_text,
            filename=upload.filename,
        )

        # Advanced Intelligence: Table Extraction
        tables = self.table_extractor.extract_tables_from_text(full_text)
        tables_dicts = [t.model_dump() for t in tables]

        # Advanced Intelligence: Near-Duplicate Detection
        near_duplicates: list[dict[str, Any]] = []
        try:
            session_factory = getattr(self.store, "_get_session_factory", None)
            if session_factory and owner_id:
                with session_factory()() as sess:
                    dup_resp = self.duplicate_detector.detect_duplicates(
                        session=sess,
                        document_id=document_id,
                        owner_id=owner_id,
                        content_sha256=content_hash,
                        document_text=full_text,
                    )
                    near_duplicates = [m.model_dump() for m in dup_resp.near_matches]
        except Exception as dup_err:
            logger.debug("Duplicate detection skipped or failed: %s", dup_err)

        intel_data = {
            "classification_category": classification.category,
            "classification_confidence": classification.confidence,
            "classification_reasoning": classification.reasoning,
            "ocr_status": ocr_status or ("ocr_completed" if upload.source_type == "image" else None),
            "ocr_page_count": extraction.page_count,
            "extracted_tables": tables_dicts,
            "near_duplicates": near_duplicates,
        }

        return self._persist(
            IngestResponse(
                document_id=document_id,
                filename=upload.filename,
                status="processed",
                extracted_characters=sum(len(text) for _, text in cleaned_pages),
                chunk_count=len(chunks),
                chunks=chunks,
                page_count=extraction.page_count,
                warnings=extraction.warnings,
            ),
            content_hash,
            embeddings,
            owner_id=owner_id,
            property_id=property_id,
            intelligence=intel_data,
        )

    def reprocess(
        self,
        document_id: str,
        owner_id: str,
    ) -> DocumentProcessingStatusResponse:
        """Trigger or retry advanced document intelligence processing on an existing document."""
        intel = self.store.get_document_intelligence(document_id, owner_id)
        if intel is None:
            raise DocumentValidationError("Document not found or access denied.")

        # Re-fetch chunks to rebuild text
        chunk_res = self.store.get_document_chunks(
            document_id, limit=500, include_text=True, owner_id=owner_id
        )
        existing_text = ""
        if chunk_res:
            items, _ = chunk_res
            existing_text = "\n\n".join(c.text for c in items if c.text)

        # Classification
        classification = self.classifier.classify_document(
            document_id=document_id,
            text=existing_text,
            filename=intel.get("filename"),
        )

        # Table extraction
        tables = self.table_extractor.extract_tables_from_text(existing_text)
        tables_dicts = [t.model_dump() for t in tables]

        # Duplicate detection
        near_duplicates: list[dict[str, Any]] = []
        try:
            session_factory = getattr(self.store, "_get_session_factory", None)
            if session_factory and owner_id:
                with session_factory()() as sess:
                    dup_resp = self.duplicate_detector.detect_duplicates(
                        session=sess,
                        document_id=document_id,
                        owner_id=owner_id,
                        content_sha256=intel.get("content_sha256", ""),
                        document_text=existing_text,
                    )
                    near_duplicates = [m.model_dump() for m in dup_resp.near_matches]
        except Exception:
            pass

        # Update document in store
        session_factory = getattr(self.store, "_get_session_factory", None)
        if session_factory:
            with session_factory()() as sess:
                with sess.begin():
                    doc = sess.query(Document).filter(
                        Document.id == document_id,
                        Document.owner_id == owner_id,
                    ).one_or_none()
                    if doc:
                        doc.classification_category = classification.category
                        doc.classification_confidence = classification.confidence
                        doc.classification_reasoning = classification.reasoning
                        doc.extracted_tables = tables_dicts
                        doc.near_duplicates = near_duplicates
                        if existing_text and doc.status in ("ocr_required", "pending_ocr"):
                            doc.status = "processed"
                            doc.ocr_status = "ocr_completed"

        fresh_intel = self.store.get_document_intelligence(document_id, owner_id) or intel
        return DocumentProcessingStatusResponse(
            document_id=document_id,
            filename=fresh_intel.get("filename", ""),
            status=fresh_intel.get("status", "processed"),
            ocr_status=fresh_intel.get("ocr_status"),
            page_count=fresh_intel.get("page_count"),
            extracted_characters=fresh_intel.get("extracted_characters", 0),
            chunk_count=fresh_intel.get("chunk_count", 0),
            classification_category=fresh_intel.get("classification_category"),
            classification_confidence=fresh_intel.get("classification_confidence"),
            classification_reasoning=fresh_intel.get("classification_reasoning"),
            classification_manually_corrected=fresh_intel.get("classification_manually_corrected", False),
            has_duplicates=bool(fresh_intel.get("near_duplicates")),
            table_count=len(fresh_intel.get("extracted_tables") or []),
            warnings=fresh_intel.get("warnings") or [],
            detail=fresh_intel.get("detail"),
            created_at=fresh_intel.get("created_at") or datetime.now(timezone.utc),
            updated_at=fresh_intel.get("updated_at") or datetime.now(timezone.utc),
        )

    def _persist(
        self,
        response: IngestResponse,
        content_hash: str,
        embeddings: list[list[float]],
        owner_id: str | None = None,
        property_id: str | None = None,
        intelligence: dict[str, Any] | None = None,
    ) -> IngestResponse:
        """Check for an existing identical upload, then commit atomically."""
        existing = self.store.find_by_content_hash(
            content_hash, response.filename, owner_id=owner_id
        )
        if existing is not None:
            if property_id is not None:
                return self.store.save(
                    existing,
                    content_hash,
                    [],
                    owner_id=owner_id,
                    property_id=property_id,
                    intelligence=intelligence,
                )
            return existing
        return self.store.save(
            response,
            content_hash,
            embeddings,
            owner_id=owner_id,
            property_id=property_id,
            intelligence=intelligence,
        )

    def _extract(self, upload: ValidatedUpload) -> ExtractionResult:
        extractor = get_extractor(upload.extension)
        with secure_temp_file(
            upload.data, suffix=upload.extension, directory=self.settings.document_temp_dir
        ) as path:
            return extractor.extract(path)

    def _ocr_required(
        self,
        document_id: str,
        upload: ValidatedUpload,
        extraction: ExtractionResult,
    ) -> IngestResponse:
        detail = (
            "No extractable text was found. This document appears to be scanned "
            "and requires OCR before it can be chunked."
        )
        warnings = list(extraction.warnings)
        if detail not in warnings:
            warnings.append(detail)
        return IngestResponse(
            document_id=document_id,
            filename=upload.filename,
            status="ocr_required",
            extracted_characters=0,
            chunk_count=0,
            chunks=[],
            page_count=extraction.page_count,
            warnings=warnings,
            detail=detail,
        )

    @staticmethod
    def _join_pages(
        pages: list[tuple[int | None, str]],
    ) -> tuple[str, list[_PageSpan]]:
        parts: list[str] = []
        spans: list[_PageSpan] = []
        cursor = 0
        for index, (page_number, text) in enumerate(pages):
            if index:
                parts.append("\n\n")
                cursor += 2
            start = cursor
            parts.append(text)
            cursor += len(text)
            if page_number is not None:
                spans.append(
                    _PageSpan(
                        page_number=page_number,
                        start_offset=start,
                        end_offset=cursor,
                    )
                )
        return "".join(parts), spans

    @staticmethod
    def _pages_for_chunk(
        spans: list[_PageSpan], start_offset: int, end_offset: int
    ) -> list[int]:
        return [
            span.page_number
            for span in spans
            if span.end_offset > start_offset and span.start_offset < end_offset
        ]

    def _build_chunk(
        self,
        document_id: str,
        upload: ValidatedUpload,
        extraction: ExtractionResult,
        chunk: TextChunk,
        spans: list[_PageSpan],
    ) -> DocumentChunk:
        page_numbers = self._pages_for_chunk(
            spans, chunk.start_offset, chunk.end_offset
        )
        metadata: dict = {
            "character_count": len(chunk.text),
            "chunking": {
                "strategy": self.chunking_config.strategy,
                "chunk_size_chars": self.chunking_config.chunk_size_chars,
                "overlap_chars": self.chunking_config.overlap_chars,
            },
            "warnings": list(extraction.warnings),
        }
        if page_numbers:
            metadata["page_numbers"] = page_numbers
        if extraction.page_count is not None:
            metadata["total_pages"] = extraction.page_count

        return DocumentChunk(
            chunk_id=_new_identifier("chk"),
            document_id=document_id,
            chunk_index=chunk.index,
            text=chunk.text,
            source_filename=upload.filename,
            source_type=upload.source_type,
            page_number=page_numbers[0] if len(page_numbers) == 1 else None,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            metadata=metadata,
        )
