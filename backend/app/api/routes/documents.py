"""Document ingestion and lifecycle management endpoints."""

from __future__ import annotations

import math

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.db.models import User
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
from app.services.property_errors import PropertyError
from app.services.property_service import PropertyService

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


def get_property_service(
    settings: Settings = Depends(get_settings_dep),
) -> PropertyService:
    return PropertyService(settings)


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Upload, chunk, embed, and persist a property document",
    responses={
        200: {"description": "Document processed and committed, or OCR is required."},
        400: {"description": "Empty file, invalid contents, or no readable text."},
        404: {"description": "Specified property not found or access denied."},
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
    property_id: str | None = Form(default=None, description="Optional property identifier."),
    property_id_query: str | None = Query(default=None, alias="property_id", description="Optional property ID via query param."),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
    service: DocumentIngestionService = Depends(get_ingestion_service),
    property_service: PropertyService = Depends(get_property_service),
) -> IngestResponse | JSONResponse:
    GLOBAL_RATE_LIMITER.check(
        key=f"upload:{current_user.id}",
        max_requests=settings.rate_limit_upload_per_minute,
        window_seconds=60,
    )

    resolved_property_id = property_id or property_id_query
    if resolved_property_id is not None:
        resolved_property_id = resolved_property_id.strip() or None
        if resolved_property_id:
            try:
                # Ensure the property exists and belongs to the authenticated user
                property_service.get_property(resolved_property_id, user_id=current_user.id)
            except PropertyError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail=f"Property '{resolved_property_id}' not found or access denied.",
                ) from exc

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
            service.ingest,
            data,
            file.filename,
            file.content_type,
            owner_id=current_user.id,
            property_id=resolved_property_id,
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
        401: {"description": "Authentication required."},
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
    property_id: str | None = Query(
        default=None, description="Optional filter by associated property ID."
    ),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentListResponse:
    offset = (page - 1) * page_size
    items, total = await run_in_threadpool(
        store.list_documents,
        limit=page_size,
        offset=offset,
        status=status_filter,
        source_type=source_type,
        owner_id=current_user.id,
        property_id=property_id,
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
        401: {"description": "Authentication required."},
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
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentDetailResponse:
    cleaned_id = _validate_document_id(document_id)
    document = await run_in_threadpool(store.get_document, cleaned_id, owner_id=current_user.id)
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
        401: {"description": "Authentication required."},
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
    current_user: User = Depends(get_current_user),
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
        owner_id=current_user.id,
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
        401: {"description": "Authentication required."},
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
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentDeleteResponse:
    cleaned_id = _validate_document_id(document_id)
    deleted = await run_in_threadpool(store.delete_document, cleaned_id, owner_id=current_user.id)
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



# --- Phase 13: Advanced Document Intelligence Endpoints ---

from app.schemas.document_intelligence import (
    DocumentClassificationResponse,
    DocumentClassificationUpdateRequest,
    DocumentProcessingStatusResponse,
    ExtractedTable,
    ExtractedTablesResponse,
    DocumentDuplicatesResponse,
    DuplicateMatch,
)
from app.services.duplicate_detection import DuplicateDetectionService


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessingStatusResponse,
    summary="Trigger or retry advanced document intelligence processing",
)
async def process_document_intelligence(
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    ingestion_service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentProcessingStatusResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_process", max_requests=20, window_seconds=60)
    try:
        return await run_in_threadpool(
            ingestion_service.reprocess,
            cleaned_id,
            owner_id=current_user.id,
        )
    except DocumentIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {exc}",
        )


@router.get(
    "/{document_id}/processing-status",
    response_model=DocumentProcessingStatusResponse,
    summary="Retrieve OCR, classification, and processing status",
)
async def get_processing_status(
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentProcessingStatusResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_status", max_requests=60, window_seconds=60)

    intel = await run_in_threadpool(store.get_document_intelligence, cleaned_id, owner_id=current_user.id)
    if intel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return DocumentProcessingStatusResponse(
        document_id=cleaned_id,
        filename=intel.get("filename", ""),
        status=intel.get("status", "processed"),
        ocr_status=intel.get("ocr_status"),
        page_count=intel.get("page_count"),
        extracted_characters=intel.get("extracted_characters", 0),
        chunk_count=intel.get("chunk_count", 0),
        classification_category=intel.get("classification_category"),
        classification_confidence=intel.get("classification_confidence"),
        classification_reasoning=intel.get("classification_reasoning"),
        classification_manually_corrected=intel.get("classification_manually_corrected", False),
        has_duplicates=bool(intel.get("near_duplicates")),
        table_count=len(intel.get("extracted_tables") or []),
        warnings=intel.get("warnings") or [],
        detail=intel.get("detail"),
        created_at=intel.get("created_at"),
        updated_at=intel.get("updated_at"),
    )


@router.get(
    "/{document_id}/classification",
    response_model=DocumentClassificationResponse,
    summary="Retrieve document classification details",
)
async def get_document_classification(
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentClassificationResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_class", max_requests=60, window_seconds=60)

    intel = await run_in_threadpool(store.get_document_intelligence, cleaned_id, owner_id=current_user.id)
    if intel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return DocumentClassificationResponse(
        document_id=cleaned_id,
        category=intel.get("classification_category") or "Other / Unknown",
        confidence=intel.get("classification_confidence") or 0.0,
        reasoning=intel.get("classification_reasoning") or "No classification reasoning recorded.",
        manually_corrected=intel.get("classification_manually_corrected", False),
        updated_at=intel.get("updated_at"),
    )


@router.patch(
    "/{document_id}/classification",
    response_model=DocumentClassificationResponse,
    summary="Manually correct a document classification category",
)
async def update_document_classification(
    payload: DocumentClassificationUpdateRequest,
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentClassificationResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_class_update", max_requests=30, window_seconds=60)

    updated = await run_in_threadpool(
        store.update_classification,
        cleaned_id,
        owner_id=current_user.id,
        category=payload.category.value,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    from datetime import datetime, timezone
    intel = await run_in_threadpool(store.get_document_intelligence, cleaned_id, owner_id=current_user.id)
    updated_at_val = (intel and intel.get("updated_at")) or getattr(updated, "updated_at", None) or datetime.now(timezone.utc)
    return DocumentClassificationResponse(
        document_id=cleaned_id,
        category=payload.category.value,
        confidence=1.0,
        reasoning="Category manually updated by user.",
        manually_corrected=True,
        updated_at=updated_at_val,
    )


@router.get(
    "/{document_id}/tables",
    response_model=ExtractedTablesResponse,
    summary="Retrieve extracted tables and their provenance",
)
async def get_document_tables(
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> ExtractedTablesResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_tables", max_requests=60, window_seconds=60)

    intel = await run_in_threadpool(store.get_document_intelligence, cleaned_id, owner_id=current_user.id)
    if intel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    raw_tables = intel.get("extracted_tables") or []
    tables = [ExtractedTable(**t) if isinstance(t, dict) else t for t in raw_tables]
    return ExtractedTablesResponse(
        document_id=cleaned_id,
        table_count=len(tables),
        tables=tables,
    )


@router.get(
    "/{document_id}/duplicates",
    response_model=DocumentDuplicatesResponse,
    summary="Retrieve exact or potential duplicate matches",
)
async def get_document_duplicates(
    document_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentDuplicatesResponse:
    cleaned_id = _validate_document_id(document_id)
    GLOBAL_RATE_LIMITER.check(f"user:{current_user.id}:doc_dups", max_requests=60, window_seconds=60)

    intel = await run_in_threadpool(store.get_document_intelligence, cleaned_id, owner_id=current_user.id)
    if intel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Perform fresh duplicate query scoped to current_user
    session_factory = getattr(store, "_get_session_factory", None)
    if session_factory:
        detector = DuplicateDetectionService()
        with session_factory()() as sess:
            # Get text from chunks
            chunk_res = store.get_document_chunks(cleaned_id, limit=500, include_text=True, owner_id=current_user.id)
            doc_text = ""
            if chunk_res:
                items, _ = chunk_res
                doc_text = " ".join(c.text for c in items if c.text)

            dup_result = detector.detect_duplicates(
                session=sess,
                document_id=cleaned_id,
                owner_id=current_user.id,
                content_sha256=intel.get("content_sha256", ""),
                document_text=doc_text,
            )
            return dup_result

    # Fallback to stored near duplicates
    near_matches = [DuplicateMatch(**m) for m in intel.get("near_duplicates") or []]
    return DocumentDuplicatesResponse(
        document_id=cleaned_id,
        has_duplicates=bool(near_matches),
        exact_matches=[],
        near_matches=near_matches,
    )
