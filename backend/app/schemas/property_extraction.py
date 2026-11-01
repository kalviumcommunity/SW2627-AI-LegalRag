"""Pydantic schemas for structured property information extraction."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rag import CrossDocumentConflict


class FactVerificationStatus(str, Enum):
    """Rigorous verification status of an extracted property fact."""

    SUPPORTED = "supported"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    MISSING = "missing"


class ExtractedFieldFact(BaseModel):
    """Individual extracted factual attribute with provenance and verification metadata."""

    model_config = ConfigDict(extra="ignore")

    field_name: str = Field(..., description="Canonical programmatic identifier of the field.")
    display_name: str = Field(..., description="Human-readable label for dashboard display.")
    extracted_value: Any | None = Field(
        default=None,
        description="Clean, extracted representation of the fact, or null if missing.",
    )
    original_value: str | None = Field(
        default=None,
        description="Verbatim or near-verbatim representation as stated in the source document.",
    )
    normalized_value: Any | None = Field(
        default=None,
        description="Standardized representation (e.g. numeric float, ISO date).",
    )
    unit: str | None = Field(
        default=None,
        description="Normalized unit of measurement or currency denomination.",
    )
    document_id: str | None = Field(
        default=None,
        description="ID of the document from which this fact originated.",
    )
    filename: str | None = Field(
        default=None,
        description="Filename of the originating document.",
    )
    page_number: int | None = Field(
        default=None,
        description="Page number in the originating document.",
    )
    supporting_text: str | None = Field(
        default=None,
        description="Supporting passage or clause substantiating this fact.",
    )
    verification_status: str = Field(
        default="missing",
        description="Verification outcome: supported, unverified, conflicting, or missing.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence or uncertainty score between 0.0 and 1.0.",
    )
    uncertainty_note: str | None = Field(
        default=None,
        description="Explanation of ambiguity, lack of corroboration, or caveat.",
    )
    alternative_values: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative or conflicting values identified across distinct documents.",
    )


class PropertyIdentityFacts(BaseModel):
    """Property identification attributes."""

    property_name: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="property_name",
            display_name="Property Name",
        )
    )
    property_address: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="property_address",
            display_name="Property Address",
        )
    )
    property_type: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="property_type",
            display_name="Property Type",
        )
    )
    unit_number: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="unit_number",
            display_name="Unit Number",
        )
    )
    carpet_area: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="carpet_area",
            display_name="Carpet Area",
        )
    )
    built_up_area: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="built_up_area",
            display_name="Built-up / Super Built-up Area",
        )
    )
    area_unit: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="area_unit",
            display_name="Area Units",
        )
    )


class FinancialFacts(BaseModel):
    """Financial considerations and fee obligations."""

    sale_price: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="sale_price",
            display_name="Sale Price / Total Consideration",
        )
    )
    booking_amount: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="booking_amount",
            display_name="Booking / Earnest Amount",
        )
    )
    payment_schedule: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="payment_schedule",
            display_name="Payment Schedule",
        )
    )
    maintenance_charges: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="maintenance_charges",
            display_name="Maintenance Charges",
        )
    )
    deposits_and_additional_charges: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="deposits_and_additional_charges",
            display_name="Deposits and Additional Charges",
        )
    )


class OwnershipLegalFacts(BaseModel):
    """Title ownership, deed references, and legal standing."""

    named_owner_or_seller: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="named_owner_or_seller",
            display_name="Named Owner / Seller / Grantor",
        )
    )
    title_deed_references: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="title_deed_references",
            display_name="Title Deed References",
        )
    )
    ownership_claims: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="ownership_claims",
            display_name="Ownership Claims / Title Type",
        )
    )
    encumbrance_information: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="encumbrance_information",
            display_name="Encumbrance Information / Mortgages",
        )
    )
    litigation_references: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="litigation_references",
            display_name="Litigation References / Legal Disputes",
        )
    )


class ApprovalFacts(BaseModel):
    """Statutory, municipal, and regulatory clearances."""

    project_registration_references: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="project_registration_references",
            display_name="Project Registration (e.g. RERA)",
        )
    )
    building_plan_approvals: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="building_plan_approvals",
            display_name="Building Plan Approvals",
        )
    )
    completion_certificates: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="completion_certificates",
            display_name="Completion Certificate (CC)",
        )
    )
    occupancy_certificates: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="occupancy_certificates",
            display_name="Occupancy Certificate (OC)",
        )
    )
    fire_and_environmental_approvals: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="fire_and_environmental_approvals",
            display_name="Fire and Environmental Approvals",
        )
    )


class DatesObligationsFacts(BaseModel):
    """Contractual milestones, deadlines, and covenants."""

    agreement_date: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="agreement_date",
            display_name="Agreement / Execution Date",
        )
    )
    possession_date: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="possession_date",
            display_name="Possession Date",
        )
    )
    payment_deadlines: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="payment_deadlines",
            display_name="Payment Deadlines",
        )
    )
    renewal_dates: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="renewal_dates",
            display_name="Renewal Dates / Lease Term",
        )
    )
    contractual_obligations: ExtractedFieldFact = Field(
        default_factory=lambda: ExtractedFieldFact(
            field_name="contractual_obligations",
            display_name="Contractual Obligations / Penalties",
        )
    )


class PropertyExtractionData(BaseModel):
    """Complete structured property facts payload."""

    property_id: str
    identity: PropertyIdentityFacts = Field(default_factory=PropertyIdentityFacts)
    financial: FinancialFacts = Field(default_factory=FinancialFacts)
    ownership_legal: OwnershipLegalFacts = Field(default_factory=OwnershipLegalFacts)
    approvals: ApprovalFacts = Field(default_factory=ApprovalFacts)
    dates_obligations: DatesObligationsFacts = Field(default_factory=DatesObligationsFacts)
    conflicts: list[CrossDocumentConflict] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    supported_count: int = 0
    unverified_count: int = 0
    conflicting_count: int = 0
    missing_count: int = 0
    document_count: int = 0
    legal_disclaimer: str = (
        "Automated extraction is provided for informational and due diligence assistance only. "
        "It does NOT constitute certified legal due diligence, title guarantee, or independent "
        "verification of marketable title. Absence of encumbrances or defects in processed "
        "documents does not guarantee clear legal title."
    )


class PropertyExtractionResponse(BaseModel):
    """API response for property extraction."""

    property_id: str
    status: Literal["completed", "pending", "failed", "stale"]
    data: PropertyExtractionData | None = None
    document_count: int = 0
    is_stale: bool = False
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PropertyExtractionStatusResponse(BaseModel):
    """Lightweight API response for polling extraction status."""

    property_id: str
    status: Literal["completed", "pending", "failed", "stale", "not_started"]
    document_count: int = 0
    is_stale: bool = False
    last_extracted_at: datetime | None = None
    supported_facts_count: int = 0
    conflicts_count: int = 0
    missing_fields_count: int = 0

