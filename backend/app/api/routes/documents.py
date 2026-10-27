"""Document ingestion and lifecycle management endpoints."""

from __future__ import annotations

import math

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.schemas.documents import (
    DocumentChunkListResponse,
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    IngestResponse,
    IngestionStatus,
    SourceType,
)
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_store import DocumentStore, create_document_store
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_errors import DocumentIngestionError

router = APIRouter(prefix="/documents", tags=["documents"])

STATUS_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def get_settings_dep() -> Settings:
    return get_settings()


def get_embedding_service(
    settings: Settings = Depends(get_settings_dep),
) -> EmbeddingService:
    return EmbeddingService(settings)


def get_document_store(
    settings: Settings = Depends(get_settings_dep),
) -> DocumentStore:
    return create_document_store(settings)


def get_ingestion_service(
    settings: Settings = Depends(get_settings_dep),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentIngestionService:
    return DocumentIngestionService(
        settings,
        embedding_service=embedding_service,
        store=store,
    )


def _validate_document_id(document_id: str) -> str:
    cleaned = document_id.strip()
    if not cleaned:
        raise HTTPException(
            status_code=STATUS_UNPROCESSABLE,
            detail="Document identifier must not be empty or whitespace.",
        )
    return cleaned


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Upload, chunk, embed, and persist a property document",
    responses={
        200: {"description": "Document processed and committed, or OCR is required."},
        400: {"description": "Empty file, invalid contents, or no readable text."},
        413: {"description": "Upload exceeds the configured size limit."},
        415: {"description": "Unsupported extension or MIME type."},
        422: {"description": "Extraction failed (for example, malformed/encrypted PDF)."},
        429: {"description": "Embedding provider rate limit exceeded."},
        500: {"description": "Safe transaction/storage failure; nothing committed."},
        502: {"description": "Embedding provider failed or returned invalid data."},
        503: {"description": "Database or embedding configuration unavailable."},
        504: {"description": "Embedding provider request timed out."},
    },
)
async def ingest_document(
    file: UploadFile = File(..., description="PDF, TXT, or Markdown document."),
    settings: Settings = Depends(get_settings_dep),
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> IngestResponse | JSONResponse:
    try:
        # Read one byte past the limit so oversized uploads can be rejected
        # without buffering the whole payload.
        data = await file.read(settings.document_max_upload_bytes + 1)
    finally:
        await file.close()

    try:
        # Extraction, embedding, and synchronous database I/O must not block
        # the event loop.
        result = await run_in_threadpool(
            service.ingest, data, file.filename, file.content_type
        )
    except DocumentIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None

    if result.status == "failed":
        return JSONResponse(
            status_code=STATUS_UNPROCESSABLE, content=result.model_dump()
        )
    return result


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List ingested documents with pagination",
    responses={
        200: {"description": "Paginated document summaries."},
        422: {"description": "Invalid pagination parameters."},
        500: {"description": "Database read failure."},
        503: {"description": "Database unavailable or unconfigured."},
    },
)
async def list_documents(
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Items per page (1-100)."
    ),
    status_filter: IngestionStatus | None = Query(
        default=None, alias="status", description="Optional status filter."
    ),
    source_type: SourceType | None = Query(
        default=None, description="Optional source format filter (pdf, txt, markdown)."
    ),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentListResponse:
    offset = (page - 1) * page_size
    items, total = await run_in_threadpool(
        store.list_documents,
        limit=page_size,
        offset=offset,
        status=status_filter,
        source_type=source_type,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Retrieve document metadata and processing status",
    responses={
        200: {"description": "Document metadata and processing status."},
        404: {"description": "Document not found."},
        422: {"description": "Invalid document identifier."},
        500: {"description": "Database read failure."},
        503: {"description": "Database unavailable or unconfigured."},
    },
)
async def get_document(
    document_id: str = Path(
        ...,
        min_length=1,
        max_length=64,
        description="Stable document identifier.",
    ),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentDetailResponse:
    cleaned_id = _validate_document_id(document_id)
    document = await run_in_threadpool(store.get_document, cleaned_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return document


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="Retrieve chunk metadata for inspection with pagination",
    responses={
        200: {"description": "Paginated chunk metadata."},
        404: {"description": "Document not found."},
        422: {"description": "Invalid document identifier or pagination parameters."},
        500: {"description": "Database read failure."},
        503: {"description": "Database unavailable or unconfigured."},
    },
)
async def get_document_chunks(
    document_id: str = Path(
        ...,
        min_length=1,
        max_length=64,
        description="Stable document identifier.",
    ),
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Items per page (1-100)."
    ),
    include_text: bool = Query(
        default=False,
        description="Whether to include chunk text. Default false to protect document contents.",
    ),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentChunkListResponse:
    cleaned_id = _validate_document_id(document_id)
    offset = (page - 1) * page_size
    result = await run_in_threadpool(
        store.get_document_chunks,
        cleaned_id,
        limit=page_size,
        offset=offset,
        include_text=include_text,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    items, total = result
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return DocumentChunkListResponse(
        document_id=cleaned_id,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document and its associated chunks and embeddings",
    responses={
        200: {"description": "Document and associated chunks deleted successfully."},
        404: {"description": "Document not found."},
        422: {"description": "Invalid document identifier."},
        500: {"description": "Database write failure."},
        503: {"description": "Database unavailable or unconfigured."},
    },
)
async def delete_document(
    document_id: str = Path(
        ...,
        min_length=1,
        max_length=64,
        description="Stable document identifier.",
    ),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentDeleteResponse:
    cleaned_id = _validate_document_id(document_id)
    deleted = await run_in_threadpool(store.delete_document, cleaned_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentDeleteResponse(
        document_id=cleaned_id,
        deleted=True,
        message="Document and associated chunks deleted successfully.",
    )

