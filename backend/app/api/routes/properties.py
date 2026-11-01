"""Property management, property intelligence, and structured extraction API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.db.models import User
from app.schemas.properties import (
    PropertyCreateRequest,
    PropertyDocumentAssociationResponse,
    PropertyDocumentListResponse,
    PropertyIntelligenceResponse,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdateRequest,
)
from app.schemas.property_extraction import (
    PropertyExtractionResponse,
    PropertyExtractionStatusResponse,
)
from app.services.document_store import DocumentStore, create_document_store
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyError,
    PropertyNotFoundError,
    PropertyValidationError,
)
from app.services.property_extraction import PropertyExtractionService
from app.services.property_service import PropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


def get_settings_dep() -> Settings:
    return get_settings()


def get_document_store(
    settings: Settings = Depends(get_settings_dep),
) -> DocumentStore:
    return create_document_store(settings)


def get_property_service(
    settings: Settings = Depends(get_settings_dep),
) -> PropertyService:
    return PropertyService(settings)


def get_extraction_service(
    settings: Settings = Depends(get_settings_dep),
) -> PropertyExtractionService:
    return PropertyExtractionService(settings=settings)


@router.post(
    "",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new property for the authenticated user",
    responses={
        201: {"description": "Property created successfully."},
        401: {"description": "Authentication required."},
        422: {"description": "Validation error in property data."},
        500: {"description": "Database write failure."},
    },
)
async def create_property(
    payload: PropertyCreateRequest,
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyResponse:
    GLOBAL_RATE_LIMITER.check(
        key=f"property_create:{current_user.id}",
        max_requests=60,
        window_seconds=60,
    )
    try:
        return await run_in_threadpool(service.create_property, current_user.id, payload)
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "",
    response_model=PropertyListResponse,
    summary="List properties owned by the authenticated user",
    responses={
        200: {"description": "Paginated list of properties."},
        401: {"description": "Authentication required."},
        422: {"description": "Invalid pagination parameters."},
        500: {"description": "Database read failure."},
    },
)
async def list_properties(
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyListResponse:
    try:
        return await run_in_threadpool(
            service.list_properties, current_user.id, page=page, page_size=page_size
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Retrieve details of a property owned by the user",
    responses={
        200: {"description": "Property details."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Database read failure."},
    },
)
async def get_property(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyResponse:
    try:
        return await run_in_threadpool(service.get_property, property_id.strip(), current_user.id)
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Update property fields",
    responses={
        200: {"description": "Property updated successfully."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        422: {"description": "Validation error."},
        500: {"description": "Database write failure."},
    },
)
async def update_property(
    payload: PropertyUpdateRequest,
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyResponse:
    try:
        return await run_in_threadpool(
            service.update_property, property_id.strip(), current_user.id, payload
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete(
    "/{property_id}",
    summary="Delete a property, preserving associated documents by unassigning them",
    responses={
        200: {"description": "Property deleted successfully; associated documents preserved."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Database write failure."},
    },
)
async def delete_property(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> dict[str, Any]:
    try:
        deleted = await run_in_threadpool(service.delete_property, property_id.strip(), current_user.id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Property not found.")
        return {
            "property_id": property_id.strip(),
            "deleted": True,
            "message": "Property deleted successfully; associated documents have been preserved.",
        }
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/{property_id}/documents",
    response_model=PropertyDocumentListResponse,
    summary="List documents associated with this property",
    responses={
        200: {"description": "List of associated documents."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Database read failure."},
    },
)
async def get_property_documents(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyDocumentListResponse:
    try:
        return await run_in_threadpool(
            service.get_property_documents,
            property_id.strip(),
            current_user.id,
            page=page,
            page_size=page_size,
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{property_id}/documents/{document_id}/associate",
    response_model=PropertyDocumentAssociationResponse,
    summary="Associate a document with a property (both must be owned by the user)",
    responses={
        200: {"description": "Document associated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Access denied; document or property owned by another user."},
        404: {"description": "Property or document not found."},
        500: {"description": "Database write failure."},
    },
)
async def associate_document(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    document_id: str = Path(..., min_length=1, max_length=64, description="Document identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyDocumentAssociationResponse:
    try:
        return await run_in_threadpool(
            service.associate_document,
            property_id.strip(),
            document_id.strip(),
            current_user.id,
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{property_id}/documents/{document_id}/disassociate",
    response_model=PropertyDocumentAssociationResponse,
    summary="Disassociate a document from a property",
    responses={
        200: {"description": "Document disassociated successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Access denied."},
        404: {"description": "Property or document not found."},
        500: {"description": "Database write failure."},
    },
)
async def disassociate_document(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    document_id: str = Path(..., min_length=1, max_length=64, description="Document identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyDocumentAssociationResponse:
    try:
        return await run_in_threadpool(
            service.disassociate_document,
            property_id.strip(),
            document_id.strip(),
            current_user.id,
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/{property_id}/intelligence",
    response_model=PropertyIntelligenceResponse,
    summary="Consolidated property intelligence, fact extraction, conflict detection, and due-diligence gaps",
    responses={
        200: {"description": "Property intelligence report."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Service failure."},
    },
)
async def get_property_intelligence(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyService = Depends(get_property_service),
) -> PropertyIntelligenceResponse:
    try:
        return await run_in_threadpool(
            service.get_property_intelligence, property_id.strip(), current_user.id
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{property_id}/extract",
    response_model=PropertyExtractionResponse,
    summary="Trigger structured information extraction for an authorized property",
    responses={
        200: {"description": "Property information extracted successfully."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Extraction service failure."},
    },
)
async def extract_property_information(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyExtractionService = Depends(get_extraction_service),
) -> PropertyExtractionResponse:
    GLOBAL_RATE_LIMITER.check(
        key=f"property_extract:{current_user.id}",
        max_requests=30,
        window_seconds=60,
    )
    try:
        return await service.extract_property_information(
            property_id.strip(), current_user.id, force_refresh=False
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/{property_id}/extraction",
    response_model=PropertyExtractionResponse,
    summary="Retrieve extracted property facts and cross-document verification",
    responses={
        200: {"description": "Extracted property facts report."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Database read failure."},
    },
)
async def get_property_extraction(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyExtractionService = Depends(get_extraction_service),
) -> PropertyExtractionResponse:
    try:
        return await run_in_threadpool(
            service.get_extraction, property_id.strip(), current_user.id
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get(
    "/{property_id}/extraction/status",
    response_model=PropertyExtractionStatusResponse,
    summary="Retrieve current extraction status and staleness indicator",
    responses={
        200: {"description": "Extraction status report."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Database read failure."},
    },
)
async def get_property_extraction_status(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyExtractionService = Depends(get_extraction_service),
) -> PropertyExtractionStatusResponse:
    try:
        return await run_in_threadpool(
            service.get_extraction_status, property_id.strip(), current_user.id
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{property_id}/extraction/refresh",
    response_model=PropertyExtractionResponse,
    summary="Force refresh structured extraction after associated documents change",
    responses={
        200: {"description": "Property information re-extracted successfully."},
        401: {"description": "Authentication required."},
        404: {"description": "Property not found or access denied."},
        500: {"description": "Extraction service failure."},
    },
)
async def refresh_property_extraction(
    property_id: str = Path(..., min_length=1, max_length=64, description="Property identifier."),
    current_user: User = Depends(get_current_user),
    service: PropertyExtractionService = Depends(get_extraction_service),
) -> PropertyExtractionResponse:
    GLOBAL_RATE_LIMITER.check(
        key=f"property_extract:{current_user.id}",
        max_requests=30,
        window_seconds=60,
    )
    try:
        return await service.extract_property_information(
            property_id.strip(), current_user.id, force_refresh=True
        )
    except PropertyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
