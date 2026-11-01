"""Pydantic schemas for property management and property-level intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.documents import DocumentSummary
from app.schemas.rag import ClaimVerification, CrossDocumentConflict


class PropertyCreateRequest(BaseModel):
    """Payload to create a new property."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name or display label for the property.",
        examples=["Maple Heights Apt 4B"],
    )
    address: str | None = Field(
        default=None,
        max_length=1000,
        description="Street address or location.",
    )
    city: str | None = Field(
        default=None,
        max_length=100,
        description="City.",
    )
    state: str | None = Field(
        default=None,
        max_length=100,
        description="State or province.",
    )
    postal_code: str | None = Field(
        default=None,
        max_length=32,
        description="Postal or ZIP code.",
    )
    property_type: str | None = Field(
        default=None,
        max_length=64,
        description="Type of property: residential, commercial, industrial, plot, etc.",
    )
    area: float | None = Field(
        default=None,
        ge=0,
        description="Area of the property.",
    )
    area_unit: str | None = Field(
        default=None,
        max_length=32,
        description="Unit of area, e.g. sq ft, sq m, acres, gunthas.",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Property name must not be blank.")
        return cleaned


class PropertyUpdateRequest(BaseModel):
    """Payload to update an existing property."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name or label.",
    )
    address: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)
    property_type: str | None = Field(default=None, max_length=64)
    area: float | None = Field(default=None, ge=0)
    area_unit: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Property name must not be blank.")
        return cleaned


class PropertyResponse(BaseModel):
    """Structured representation of a property entity."""

    id: str = Field(..., description="Unique property identifier.")
    owner_id: str = Field(..., description="Identifier of the owning user.")
    name: str = Field(..., description="Property name or display label.")
    address: str | None = Field(default=None)
    city: str | None = Field(default=None)
    state: str | None = Field(default=None)
    postal_code: str | None = Field(default=None)
    property_type: str | None = Field(default=None)
    area: float | None = Field(default=None)
    area_unit: str | None = Field(default=None)
    document_count: int = Field(default=0, ge=0, description="Number of associated documents.")
    created_at: datetime
    updated_at: datetime


class PropertyListResponse(BaseModel):
    """Paginated list of properties owned by the user."""

    items: list[PropertyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PropertyDocumentAssociationResponse(BaseModel):
    """Outcome of associating or disassociating a document with a property."""

    property_id: str
    document_id: str
    associated: bool
    message: str


class PropertyDocumentListResponse(BaseModel):
    """Documents associated with a specific property."""

    property_id: str
    items: list[DocumentSummary]
    total: int


class PropertyProcessingSummary(BaseModel):
    """Breakdown of processing statuses across associated documents."""

    total_documents: int = 0
    processed: int = 0
    ocr_required: int = 0
    failed: int = 0


class ExtractedFact(BaseModel):
    """A factual statement extracted from property documents supported by citations."""

    fact: str
    topic: str
    citation_id: str
    document_id: str
    filename: str
    page_number: int | None = None


class PropertyIntelligenceResponse(BaseModel):
    """Consolidated property intelligence report."""

    property: PropertyResponse
    document_inventory: list[DocumentSummary]
    document_count: int
    processing_summary: PropertyProcessingSummary
    verified_facts: list[ExtractedFact]
    cross_document_conflicts: list[CrossDocumentConflict]
    unverified_or_missing_information: list[str]
    citations: list[dict[str, Any]]
    legal_disclaimer: str = (
        "Automated property intelligence is an informational tool and is NOT a substitute "
        "for professional legal due diligence, title search, or certified encumbrance verification. "
        "Absence of records in uploaded documents does not guarantee clear or unencumbered legal title."
    )
