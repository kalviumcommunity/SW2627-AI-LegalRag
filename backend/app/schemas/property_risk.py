"""Pydantic schemas for property risk assessment and due diligence intelligence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskCategory(str, Enum):
    """Categories of real estate due diligence risks."""

    OWNERSHIP_TITLE = "ownership_title"
    REGULATORY_APPROVAL = "regulatory_approval"
    FINANCIAL = "financial"
    PROPERTY_IDENTITY = "property_identity"
    LEGAL_DISPUTE = "legal_dispute"
    DOCUMENTATION_COMPLETENESS = "documentation_completeness"


class RiskSeverity(str, Enum):
    """Deterministic severity ranking for risk findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RiskFindingStatus(str, Enum):
    """Lifecycle status of an identified risk finding."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RiskEvidenceItem(BaseModel):
    """Traceable evidence substantiating an identified risk."""

    model_config = ConfigDict(extra="ignore")

    document_id: str | None = Field(default=None, description="Source document identifier.")
    filename: str | None = Field(default=None, description="Source document filename.")
    page_number: int | None = Field(default=None, description="Page number where evidence appears.")
    supporting_text: str | None = Field(default=None, description="Verbatim or near-verbatim supporting quote.")
    fact_field: str | None = Field(default=None, description="Associated extracted fact field name.")
    verification_status: str | None = Field(default=None, description="Verification status of the underlying fact.")
    original_value: str | None = Field(default=None, description="Original representation in document.")


class PropertyRiskFindingResponse(BaseModel):
    """Individual risk finding response."""

    model_config = ConfigDict(extra="ignore")

    risk_id: str = Field(..., description="Unique identifier for the finding.")
    property_id: str = Field(..., description="Associated property identifier.")
    rule_key: str = Field(..., description="Stable deterministic rule key for reassessments.")
    category: RiskCategory = Field(..., description="Risk category.")
    severity: RiskSeverity = Field(..., description="Deterministic severity ranking.")
    status: RiskFindingStatus = Field(default=RiskFindingStatus.OPEN, description="Finding workflow status.")
    title: str = Field(..., description="Concise human-readable risk title.")
    description: str = Field(..., description="Detailed explanation of the risk.")
    reason: str = Field(..., description="Why this finding was flagged.")
    recommended_action: str = Field(..., description="Actionable due diligence recommendation.")
    evidence: list[RiskEvidenceItem] = Field(default_factory=list, description="Traceable supporting evidence.")
    affected_facts: list[str] = Field(default_factory=list, description="Extracted fact field names involved.")
    user_notes: str | None = Field(default=None, description="User review or resolution notes.")
    created_at: datetime = Field(..., description="Timestamp when finding was created.")
    updated_at: datetime = Field(..., description="Timestamp when finding was last updated.")


class PropertyRiskFindingUpdateRequest(BaseModel):
    """Request payload for updating a finding status or user review notes."""

    model_config = ConfigDict(extra="forbid")

    status: RiskFindingStatus = Field(..., description="New status for the finding.")
    user_notes: str | None = Field(default=None, max_length=2000, description="Optional review/resolution notes.")


class PropertyRiskAssessmentSummary(BaseModel):
    """Quantitative summary of findings by severity and status."""

    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    informational_count: int = 0
    open_count: int = 0
    under_review_count: int = 0
    resolved_count: int = 0
    dismissed_count: int = 0


class PropertyRiskAssessmentResponse(BaseModel):
    """Complete risk assessment response."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: str = Field(..., description="Unique assessment record identifier.")
    property_id: str = Field(..., description="Associated property identifier.")
    status: Literal["completed", "pending", "failed", "stale"] = Field(..., description="Assessment status.")
    summary: PropertyRiskAssessmentSummary = Field(default_factory=PropertyRiskAssessmentSummary)
    findings: list[PropertyRiskFindingResponse] = Field(default_factory=list)
    document_count: int = 0
    is_stale: bool = False
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    disclaimer: str = Field(
        default=(
            "Property risk assessment and due diligence intelligence is provided strictly for "
            "informational assistance and does NOT constitute a certified legal opinion, title "
            "guarantee, or structural verification. A low risk finding does not declare a property "
            "legally safe or free from disputes. Always consult qualified legal counsel."
        )
    )


class PropertyRiskAssessmentStatusResponse(BaseModel):
    """Lightweight status check for dashboard badges and polling."""

    property_id: str
    status: Literal["not_started", "pending", "completed", "failed", "stale"]
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    is_stale: bool = False
    last_assessed_at: datetime | None = None

