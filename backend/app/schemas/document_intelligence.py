"""Pydantic schemas for Phase 13 Advanced Document Intelligence.

Covers OCR lifecycle, legal document classification, table extraction,
duplicate detection, and processing status tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentClassificationCategory(str, Enum):
    """Recognized real estate legal document categories."""

    SALE_DEED = "Sale Deed"
    TITLE_DEED = "Title Deed"
    ALLOTMENT_LETTER = "Allotment Letter"
    AGREEMENT_TO_SELL = "Agreement to Sell"
    ENCUMBRANCE_CERTIFICATE = "Encumbrance Certificate"
    OCCUPANCY_CERTIFICATE = "Occupancy Certificate"
    COMPLETION_CERTIFICATE = "Completion Certificate"
    BUILDING_PLAN_APPROVAL = "Building Plan Approval"
    RERA_REGISTRATION = "RERA Registration"
    PROPERTY_TAX_RECEIPT = "Property Tax Receipt"
    PAYMENT_RECEIPT = "Payment Receipt"
    LOAN_OR_MORTGAGE = "Loan or Mortgage Document"
    LEGAL_NOTICE = "Legal Notice"
    LITIGATION_DOCUMENT = "Litigation Document"
    OTHER_UNKNOWN = "Other / Unknown"


class DocumentOcrStatus(str, Enum):
    """Explicit lifecycle status for optical character recognition."""

    PENDING_OCR = "pending_ocr"
    PROCESSING_OCR = "processing_ocr"
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class DocumentClassificationResponse(BaseModel):
    """Classification result including confidence and deterministic reasoning."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    manually_corrected: bool = False
    updated_at: datetime


class DocumentClassificationUpdateRequest(BaseModel):
    """Request payload to manually correct a document's classification category."""

    model_config = ConfigDict(extra="forbid")

    category: DocumentClassificationCategory


class ExtractedTable(BaseModel):
    """Structured table representation preserving rows and column relationships."""

    model_config = ConfigDict(extra="ignore")

    table_id: str
    title: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    page_number: int | None = None
    category: str | None = None  # e.g. financial_consideration, payment_schedule, area_measurement
    raw_text: str | None = None


class ExtractedTablesResponse(BaseModel):
    """Extracted tables response for a document."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    table_count: int
    tables: list[ExtractedTable] = Field(default_factory=list)


class DuplicateMatch(BaseModel):
    """Details of an exact or near-duplicate document match."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    filename: str
    match_type: Literal["exact", "near_duplicate"]
    similarity: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class DocumentDuplicatesResponse(BaseModel):
    """Exact and near duplicate findings for a document."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    has_duplicates: bool = False
    exact_matches: list[DuplicateMatch] = Field(default_factory=list)
    near_matches: list[DuplicateMatch] = Field(default_factory=list)


class DocumentProcessingStatusResponse(BaseModel):
    """Comprehensive status covering OCR, classification, table extraction, and duplicates."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    filename: str
    status: str
    ocr_status: str | None = None
    page_count: int | None = None
    extracted_characters: int = 0
    chunk_count: int = 0
    classification_category: str | None = None
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    classification_manually_corrected: bool = False
    has_duplicates: bool = False
    table_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    detail: str | None = None
    created_at: datetime
    updated_at: datetime

