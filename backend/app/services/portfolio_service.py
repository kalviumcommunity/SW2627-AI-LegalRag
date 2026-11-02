"""Portfolio analytics and property activity history service."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import (
    Document,
    Property,
    PropertyDocument,
    PropertyExtraction,
    PropertyRiskAssessment,
    PropertyRiskFinding,
)
from app.schemas.portfolio_and_reporting import (
    PortfolioAttentionItem,
    PortfolioStatsResponse,
    PropertyActivityEvent,
    PropertyActivityResponse,
)
from app.services.document_store import get_shared_engine
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyNotFoundError,
)


class PortfolioService:
    """Owner-scoped portfolio analytics and auditable property activity history."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._engine = engine
        self._session_factory = session_factory
        self._lock = threading.RLock()

    def _get_engine(self) -> Engine:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = get_shared_engine(self.settings)
        return self._engine

    def _get_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            with self._lock:
                if self._session_factory is None:
                    self._session_factory = sessionmaker(
                        bind=self._get_engine(),
                        expire_on_commit=False,
                    )
        return self._session_factory

    def get_portfolio_stats(self, user_id: str) -> PortfolioStatsResponse:
        """Compute aggregated portfolio intelligence strictly scoped to the authenticated user."""
        factory = self._get_session_factory()
        with factory() as session:
            # 1. Properties owned by user
            props_stmt = select(Property).where(Property.owner_id == user_id).order_by(Property.created_at.desc())
            properties = list(session.scalars(props_stmt).all())
            property_ids = [p.id for p in properties]

            total_properties = len(properties)

            if not property_ids:
                return PortfolioStatsResponse(
                    total_properties=0,
                    total_documents=0,
                    processed_documents=0,
                    ocr_or_review_documents=0,
                    pending_assessment_properties=0,
                    critical_findings_count=0,
                    high_findings_count=0,
                    open_findings_count=0,
                    resolved_findings_count=0,
                    properties_requiring_attention=[],
                )

            # 2. Associated documents across user's properties
            # Distinct document IDs associated with user's properties
            doc_assoc_stmt = (
                select(PropertyDocument.property_id, Document)
                .join(Document, PropertyDocument.document_id == Document.id)
                .where(PropertyDocument.property_id.in_(property_ids))
            )
            assoc_rows = session.execute(doc_assoc_stmt).all()

            seen_doc_ids: set[str] = set()
            property_docs_map: dict[str, list[Document]] = {pid: [] for pid in property_ids}

            total_docs = 0
            processed_docs = 0
            ocr_or_review_docs = 0

            for pid, doc in assoc_rows:
                property_docs_map[pid].append(doc)
                if doc.id not in seen_doc_ids:
                    seen_doc_ids.add(doc.id)
                    total_docs += 1
                    if doc.status == "processed":
                        processed_docs += 1
                    if (
                        doc.status in ("ocr_required", "pending_ocr", "processing_ocr", "needs_manual_review", "ocr_failed")
                        or doc.ocr_status in ("needs_manual_review", "ocr_failed")
                    ):
                        ocr_or_review_docs += 1

            # 3. Risk assessments and findings for user's properties
            assess_stmt = select(PropertyRiskAssessment).where(
                PropertyRiskAssessment.property_id.in_(property_ids)
            )
            assessments = list(session.scalars(assess_stmt).all())
            assess_map: dict[str, PropertyRiskAssessment] = {a.property_id: a for a in assessments}

            findings_stmt = select(PropertyRiskFinding).where(
                PropertyRiskFinding.property_id.in_(property_ids)
            )
            findings = list(session.scalars(findings_stmt).all())

            critical_count = 0
            high_count = 0
            open_count = 0
            resolved_count = 0

            property_findings_map: dict[str, list[PropertyRiskFinding]] = {pid: [] for pid in property_ids}
            for f in findings:
                property_findings_map[f.property_id].append(f)
                if f.status in ("open", "under_review"):
                    if f.severity == "critical":
                        critical_count += 1
                    elif f.severity == "high":
                        high_count += 1
                    open_count += 1
                elif f.status == "resolved":
                    resolved_count += 1

            # 4. Determine pending assessments and properties requiring attention
            pending_assessment_count = 0
            attention_items: list[PortfolioAttentionItem] = []

            for p in properties:
                assessment = assess_map.get(p.id)
                prop_docs = property_docs_map.get(p.id, [])
                prop_findings = property_findings_map.get(p.id, [])

                # Assessment status check
                has_pending = False
                is_stale = False
                if assessment is None or assessment.status == "pending":
                    has_pending = True
                elif assessment.status == "completed":
                    # Check staleness: if documents changed since assessment
                    current_doc_hashes = {d.id: d.content_sha256 for d in prop_docs}
                    if current_doc_hashes != (assessment.document_hashes or {}):
                        is_stale = True

                if has_pending or is_stale:
                    pending_assessment_count += 1

                # Attention triggers:
                # - open critical findings
                # - open high findings
                # - documents needing manual review or failed OCR
                # - stale assessment with new docs
                p_crit = sum(1 for f in prop_findings if f.severity == "critical" and f.status in ("open", "under_review"))
                p_high = sum(1 for f in prop_findings if f.severity == "high" and f.status in ("open", "under_review"))
                p_failed_ocr = any(
                    d.status in ("ocr_failed", "needs_manual_review") or d.ocr_status in ("ocr_failed", "needs_manual_review")
                    for d in prop_docs
                )

                reasons: list[str] = []
                if p_crit > 0:
                    reasons.append(f"{p_crit} critical open finding(s)")
                if p_high > 0:
                    reasons.append(f"{p_high} high severity open finding(s)")
                if p_failed_ocr:
                    reasons.append("Document(s) require manual review or failed OCR")
                if is_stale:
                    reasons.append("Risk assessment is stale (documents updated)")
                elif assessment is None and len(prop_docs) > 0:
                    reasons.append("Assessment not yet run for associated documents")

                if reasons:
                    attention_items.append(
                        PortfolioAttentionItem(
                            property_id=p.id,
                            property_name=p.name,
                            reasons=reasons,
                            critical_count=p_crit,
                            high_count=p_high,
                            has_failed_ocr=p_failed_ocr,
                            is_assessment_stale=is_stale,
                        )
                    )

            return PortfolioStatsResponse(
                total_properties=total_properties,
                total_documents=total_docs,
                processed_documents=processed_docs,
                ocr_or_review_documents=ocr_or_review_docs,
                pending_assessment_properties=pending_assessment_count,
                critical_findings_count=critical_count,
                high_findings_count=high_count,
                open_findings_count=open_count,
                resolved_findings_count=resolved_count,
                properties_requiring_attention=attention_items,
            )

    def get_activity_history(self, property_id: str, user_id: str) -> PropertyActivityResponse:
        """Aggregate chronological activity timeline for a property from persisted records."""
        factory = self._get_session_factory()
        with factory() as session:
            # 1. Validate property exists and belongs to user
            prop = session.get(Property, property_id)
            if prop is None:
                raise PropertyNotFoundError(f"Property with ID '{property_id}' was not found.")
            if prop.owner_id != user_id:
                raise PropertyAuthorizationError("You do not have permission to view activity for this property.")

            def _normalize_dt(dt: datetime | None) -> datetime:
                if dt is None:
                    return datetime.now(timezone.utc)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt

            events: list[PropertyActivityEvent] = []

            # 2. Property creation
            events.append(
                PropertyActivityEvent(
                    event_id=f"evt_create_{prop.id}",
                    event_type="property_created",
                    title="Property Created",
                    description=f"Property '{prop.name}' was created.",
                    timestamp=_normalize_dt(prop.created_at),
                    metadata={"name": prop.name, "property_type": prop.property_type or "Residential"},
                )
            )

            # 3. Document associations
            doc_assoc_stmt = (
                select(PropertyDocument, Document)
                .join(Document, PropertyDocument.document_id == Document.id)
                .where(PropertyDocument.property_id == property_id)
            )
            for assoc, doc in session.execute(doc_assoc_stmt).all():
                ts = assoc.created_at or doc.created_at
                events.append(
                    PropertyActivityEvent(
                        event_id=f"evt_doc_{doc.id}",
                        event_type="document_associated",
                        title="Document Associated",
                        description=f"File '{doc.filename}' ({doc.source_type.upper()}) was associated with property.",
                        timestamp=_normalize_dt(ts),
                        metadata={
                            "document_id": doc.id,
                            "filename": doc.filename,
                            "classification": doc.classification_category or "Unclassified",
                            "status": doc.status,
                        },
                    )
                )

            # 4. Structured extraction runs
            extraction_stmt = select(PropertyExtraction).where(PropertyExtraction.property_id == property_id)
            extraction = session.scalars(extraction_stmt).first()
            if extraction:
                fact_count = len(extraction.extracted_data.get("supported_facts") or [])
                events.append(
                    PropertyActivityEvent(
                        event_id=f"evt_extract_{extraction.id}",
                        event_type="extraction_completed",
                        title="Structured Extraction Run",
                        description=f"Extraction completed with {fact_count} supported facts.",
                        timestamp=_normalize_dt(extraction.updated_at or extraction.created_at),
                        metadata={
                            "status": extraction.status,
                            "supported_facts": fact_count,
                            "conflicts_count": len(extraction.extracted_data.get("conflicts") or []),
                        },
                    )
                )

            # 5. Risk assessment runs and finding updates
            assess_stmt = select(PropertyRiskAssessment).where(PropertyRiskAssessment.property_id == property_id)
            assessment = session.scalars(assess_stmt).first()
            if assessment:
                summary = assessment.summary or {}
                events.append(
                    PropertyActivityEvent(
                        event_id=f"evt_assess_{assessment.id}",
                        event_type="risk_assessed",
                        title="Due Diligence Risk Assessment",
                        description=f"Risk assessment executed ({summary.get('total_findings', 0)} total findings, {summary.get('critical_count', 0)} critical).",
                        timestamp=_normalize_dt(assessment.updated_at or assessment.created_at),
                        metadata={
                            "status": assessment.status,
                            "critical": summary.get("critical_count", 0),
                            "high": summary.get("high_count", 0),
                            "total": summary.get("total_findings", 0),
                        },
                    )
                )

                # Findings that were reviewed or have user notes
                findings_stmt = select(PropertyRiskFinding).where(
                    PropertyRiskFinding.property_id == property_id
                )
                for f in session.scalars(findings_stmt).all():
                    if f.status != "open" or f.user_notes:
                        events.append(
                            PropertyActivityEvent(
                                event_id=f"evt_finding_{f.id}",
                                event_type="finding_status_updated",
                                title=f"Risk Review: {f.title[:40]}...",
                                description=f"Finding status updated to '{f.status.upper()}'. Note: {f.user_notes or 'No notes provided'}",
                                timestamp=_normalize_dt(f.updated_at or f.created_at),
                                metadata={
                                    "finding_id": f.id,
                                    "severity": f.severity,
                                    "status": f.status,
                                },
                            )
                        )

            # Sort events in reverse chronological order (newest first)
            events.sort(key=lambda e: _normalize_dt(e.timestamp), reverse=True)
            return PropertyActivityResponse(property_id=property_id, events=events)
