"""End-to-end document ingestion orchestration.

Pipeline: validation -> secure temporary storage -> extraction -> cleaning ->
chunking -> source metadata -> structured result.

Phase 2 stores nothing durably: uploaded files are deleted immediately after
processing and chunks exist only in the response. Persistence and indexing are
later-phase concerns.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.documents import DocumentChunk, IngestResponse
from app.services.chunking import ChunkingConfig, TextChunk, chunk_text
from app.services.document_validation import ValidatedUpload, validate_upload
from app.services.ingestion_errors import (
    DocumentExtractionError,
    DocumentValidationError,
)
from app.services.temp_storage import secure_temp_file
from app.services.text_cleaning import clean_text
from app.services.text_extraction import ExtractionResult, get_extractor


@dataclass(frozen=True)
class _PageSpan:
    page_number: int
    start_offset: int
    end_offset: int


def _new_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class DocumentIngestionService:
    """Turns a validated upload into traceable chunks."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.chunking_config = ChunkingConfig(
            chunk_size_chars=self.settings.document_chunk_size_chars,
            overlap_chars=self.settings.document_chunk_overlap_chars,
            min_split_ratio=self.settings.document_chunk_min_split_ratio,
        )

    def ingest(
        self, data: bytes, filename: str | None, content_type: str | None
    ) -> IngestResponse:
        document_id = _new_identifier("doc")
        upload = validate_upload(data, filename, content_type, self.settings)

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

        if not cleaned_pages:
            if upload.source_type == "pdf":
                return self._ocr_required(document_id, upload, extraction)
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

        return IngestResponse(
            document_id=document_id,
            filename=upload.filename,
            status="processed",
            extracted_characters=sum(len(text) for _, text in cleaned_pages),
            chunk_count=len(chunks),
            chunks=chunks,
            page_count=extraction.page_count,
            warnings=extraction.warnings,
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
