"""Pydantic schemas for Phase 14: Portfolio Intelligence, Due Diligence Reporting, and Activity History."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PortfolioAttentionItem(BaseModel):
    """A property that requires user attention due to critical risks, unassessed changes, or OCR issues."""

    model_config = ConfigDict(extra="ignore")

    property_id: str
    property_name: str
    reasons: list[str] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    has_failed_ocr: bool = False
    is_assessment_stale: bool = False


class PortfolioStatsResponse(BaseModel):
    """Real computed analytics across all properties owned by the authenticated user."""

    model_config = ConfigDict(extra="ignore")

    total_properties: int
    total_documents: int
    processed_documents: int
    ocr_or_review_documents: int
    pending_assessment_properties: int
    critical_findings_count: int
    high_findings_count: int
    open_findings_count: int
    resolved_findings_count: int
    properties_requiring_attention: list[PortfolioAttentionItem] = Field(default_factory=list)


class PropertyActivityEvent(BaseModel):
    """An auditable lifecycle event in the property intelligence timeline."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str
    title: str
    description: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class PropertyActivityResponse(BaseModel):
    """Chronological activity history for a property."""

    model_config = ConfigDict(extra="ignore")

    property_id: str
    events: list[PropertyActivityEvent] = Field(default_factory=list)

