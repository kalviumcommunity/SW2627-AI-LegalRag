"""Document ingestion endpoint. Validation lives in the service layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.schemas.documents import IngestResponse
from app.services.document_ingestion import DocumentIngestionService
from app.services.ingestion_errors import DocumentIngestionError

router = APIRouter(prefix="/documents", tags=["documents"])

STATUS_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def get_settings_dep() -> Settings:
    return get_settings()


def get_ingestion_service(
    settings: Settings = Depends(get_settings_dep),
) -> DocumentIngestionService:
    return DocumentIngestionService(settings)


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Upload and chunk a property document",
    responses={
        200: {"description": "Document processed, or OCR is required (see status)."},
        400: {"description": "Empty file, invalid contents, or no readable text."},
        413: {"description": "Upload exceeds the configured size limit."},
        415: {"description": "Unsupported extension or MIME type."},
        422: {"description": "Extraction failed (for example, malformed/encrypted PDF)."},
        500: {"description": "Safe internal processing or storage failure."},
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
        result = service.ingest(data, file.filename, file.content_type)
    except DocumentIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None

    if result.status == "failed":
        return JSONResponse(
            status_code=STATUS_UNPROCESSABLE, content=result.model_dump()
        )
    return result
