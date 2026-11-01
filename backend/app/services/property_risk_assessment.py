"""Dedicated service for evidence-backed property risk assessment and due diligence intelligence.

Features:
- Deterministic risk assessment engine across 6 core due diligence categories.
- Traceable evidence linkage preserving source documents, pages, and supporting passages.
- Cross-document conflict preservation without fabricating legal truth or safety.
- Reassessment state preservation: retains user-reviewed statuses and notes.
- Hash-based staleness detection when property documents or extracted facts change.
- Strict tenant isolation and property authorization enforcement.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, selectinload

from app.core.config import Settings, get_settings
from app.db.models import (
    Document,
    Property,
    PropertyExtraction,
    PropertyRiskAssessment,
    PropertyRiskFinding,
)
from app.schemas.property_extraction import ExtractedFieldFact, PropertyExtractionData
from app.schemas.property_risk import (
    PropertyRiskAssessmentResponse,
    PropertyRiskAssessmentStatusResponse,
    PropertyRiskAssessmentSummary,
    PropertyRiskFindingResponse,
    RiskCategory,
    RiskEvidenceItem,
    RiskFindingStatus,
    RiskSeverity,
)
from app.schemas.rag import CrossDocumentConflict
from app.services.document_store import get_shared_engine
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyError,
    PropertyNotFoundError,
    PropertyValidationError,
)
from app.services.property_extraction import PropertyExtractionService

logger = logging.getLogger(__name__)

# Keywords signaling adverse litigation or active court disputes
_LITIGATION_KEYWORDS = re.compile(
    r"\b(civil\s+suit|lawsuit|writ\s+petition|injunction|stay\s+order|interim\s+relief|"
    r"arbitration\s+proceeding|dispute\s+pending|pending\s+litigation|court\s+case|"
    r"high\s+court|supreme\s+court|district\s+court|tribunal|drth?|nclt)\b",
    re.IGNORECASE,
)

# Negation terms indicating clear non-litigation declaration
_LITIGATION_NEGATIONS = re.compile(
    r"\b(no\s+litigation|free\s+from\s+(?:all\s+)?litigation|not\s+subject\s+to\s+any\s+(?:suit|litigation)|"
    r"nil\s+litigation|no\s+pending\s+(?:dispute|litigation|suit)|neither\s+pending\s+nor)\b",
    re.IGNORECASE,
)

# Keywords signaling encumbrances or mortgages
_ENCUMBRANCE_KEYWORDS = re.compile(
    r"\b(mortgage|mortgaged\s+to|equitable\s+mortgage|registered\s+mortgage|bank\s+charge|"
    r"hypothecation|lien|attachment\s+order|lis\s+pendens|charge\s+created)\b",
    re.IGNORECASE,
)

_ENCUMBRANCE_NEGATIONS = re.compile(
    r"\b(free\s+from\s+(?:all\s+)?encumbrances?|unencumbered|nil\s+encumbrance|"
    r"no\s+mortgage|charge\s+discharged|reconveyance\s+deed|fully\s+discharged)\b",
    re.IGNORECASE,
)


class PropertyRiskAssessmentService:
    """Rigorous risk assessment engine analyzing structured facts, conflicts, and completeness."""

    def __init__(
        self,
        settings: Settings | None = None,
        extraction_service: PropertyExtractionService | None = None,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.extraction_service = extraction_service or PropertyExtractionService(settings=self.settings)
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

    # --- Core Public Workflows -------------------------------------------

    async def assess_property_risks(
        self, property_id: str, user_id: str, force_refresh: bool = False
    ) -> PropertyRiskAssessmentResponse:
        """Execute or retrieve evidence-backed property risk assessment."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        # 1. Fetch property, verify ownership, retrieve associated docs and current hashes
        prop, docs, current_hashes = self._fetch_property_and_documents(property_id, user_id)

        # 2. Check for existing assessment if not forcing refresh
        existing_assessment = self._fetch_existing_assessment(property_id)
        if existing_assessment and not force_refresh:
            is_stale = existing_assessment.document_hashes != current_hashes
            if not is_stale:
                return self._build_response_from_db(existing_assessment, len(docs), is_stale=False)

        # 3. Retrieve or trigger structured extraction
        extraction_resp = await self.extraction_service.extract_property_information(
            property_id, user_id, force_refresh=force_refresh
        )
        extraction_data = extraction_resp.data

        # 4. Generate deterministic findings
        generated_findings = self._evaluate_all_risk_rules(
            property_id=property_id,
            data=extraction_data,
            documents=docs,
        )

        # 5. Persist assessment and findings, preserving user-reviewed status
        assessment_record = self._persist_assessment_and_findings(
            property_id=property_id,
            current_hashes=current_hashes,
            new_findings=generated_findings,
        )

        return self._build_response_from_db(assessment_record, len(docs), is_stale=False)

    def get_assessment(
        self, property_id: str, user_id: str
    ) -> PropertyRiskAssessmentResponse:
        """Retrieve stored risk assessment for an authorized property."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        prop, docs, current_hashes = self._fetch_property_and_documents(property_id, user_id)
        existing = self._fetch_existing_assessment(property_id)

        if existing is None:
            # Not yet assessed - return pending response with zero findings
            now = datetime.now()
            return PropertyRiskAssessmentResponse(
                assessment_id=f"pending_{property_id}",
                property_id=property_id,
                status="pending",
                summary=PropertyRiskAssessmentSummary(),
                findings=[],
                document_count=len(docs),
                is_stale=False,
                created_at=now,
                updated_at=now,
            )

        is_stale = existing.document_hashes != current_hashes
        return self._build_response_from_db(existing, len(docs), is_stale=is_stale)

    def get_assessment_status(
        self, property_id: str, user_id: str
    ) -> PropertyRiskAssessmentStatusResponse:
        """Retrieve lightweight status and staleness indicator."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        prop, docs, current_hashes = self._fetch_property_and_documents(property_id, user_id)
        existing = self._fetch_existing_assessment(property_id)

        if existing is None:
            return PropertyRiskAssessmentStatusResponse(
                property_id=property_id,
                status="not_started",
                total_findings=0,
                critical_count=0,
                high_count=0,
                is_stale=False,
                last_assessed_at=None,
            )

        is_stale = existing.document_hashes != current_hashes
        summary_dict = existing.summary or {}

        return PropertyRiskAssessmentStatusResponse(
            property_id=property_id,
            status="stale" if is_stale else existing.status,  # type: ignore
            total_findings=summary_dict.get("total_findings", 0),
            critical_count=summary_dict.get("critical_count", 0),
            high_count=summary_dict.get("high_count", 0),
            is_stale=is_stale,
            last_assessed_at=existing.updated_at,
        )

    def update_finding_status(
        self,
        property_id: str,
        risk_id: str,
        user_id: str,
        status: RiskFindingStatus,
        user_notes: str | None = None,
    ) -> PropertyRiskFindingResponse:
        """Update review status or notes for an authorized finding."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        # Verify property ownership
        self._fetch_property_and_documents(property_id, user_id)

        try:
            with self._get_session_factory()() as session:
                finding = (
                    session.query(PropertyRiskFinding)
                    .filter(
                        PropertyRiskFinding.id == risk_id,
                        PropertyRiskFinding.property_id == property_id,
                    )
                    .one_or_none()
                )
                if finding is None:
                    raise PropertyNotFoundError(f"Risk finding '{risk_id}' not found for property '{property_id}'.")

                finding.status = status.value
                if user_notes is not None:
                    finding.user_notes = user_notes.strip()
                finding.updated_at = datetime.now()

                # Update assessment summary
                assessment = (
                    session.query(PropertyRiskAssessment)
                    .filter(PropertyRiskAssessment.id == finding.assessment_id)
                    .one_or_none()
                )
                if assessment:
                    all_findings = (
                        session.query(PropertyRiskFinding)
                        .filter(PropertyRiskFinding.assessment_id == assessment.id)
                        .all()
                    )
                    summary = self._compute_summary(all_findings)
                    assessment.summary = summary.model_dump()
                    assessment.updated_at = datetime.now()

                session.commit()
                session.refresh(finding)

                return self._finding_model_to_schema(finding)
        except PropertyError:
            raise
        except Exception as exc:
            logger.error("Failed to update risk finding %s: %s", risk_id, exc)
            raise PropertyError(f"Database error updating risk finding: {exc}", status_code=500) from exc

    # --- Deterministic Evaluation Rules -----------------------------------

    def _evaluate_all_risk_rules(
        self,
        property_id: str,
        data: PropertyExtractionData | None,
        documents: list[Document],
    ) -> list[dict[str, Any]]:
        """Run all deterministic due diligence rules and generate structured findings."""
        findings: list[dict[str, Any]] = []

        if data is None:
            return findings

        # A. Ownership and Title Risks
        findings.extend(self._evaluate_ownership_title_rules(property_id, data))

        # B. Regulatory and Approval Risks
        findings.extend(self._evaluate_regulatory_approval_rules(property_id, data))

        # C. Financial Risks
        findings.extend(self._evaluate_financial_rules(property_id, data))

        # D. Property Identity and Area Risks
        findings.extend(self._evaluate_identity_area_rules(property_id, data))

        # E. Legal and Dispute Indicators
        findings.extend(self._evaluate_legal_dispute_rules(property_id, data, documents))

        # F. Documentation Completeness
        findings.extend(self._evaluate_documentation_completeness_rules(property_id, data, documents))

        return findings

    def _evaluate_ownership_title_rules(
        self, property_id: str, data: PropertyExtractionData
    ) -> list[dict[str, Any]]:
        findings = []
        ownership = data.ownership_legal

        # 1. Conflicting ownership claims or owner names across documents
        owner_fact = ownership.named_owner_or_seller
        claims_fact = ownership.ownership_claims
        has_owner_conflict = (
            owner_fact.verification_status == "conflicting"
            or claims_fact.verification_status == "conflicting"
            or any(c.topic == "ownership_legal" for c in data.conflicts)
        )

        if has_owner_conflict:
            evidence_items = []
            if owner_fact.filename:
                evidence_items.append(self._fact_to_evidence(owner_fact))
            for alt in owner_fact.alternative_values:
                evidence_items.append(RiskEvidenceItem(
                    document_id=alt.get("document_id"),
                    filename=alt.get("filename"),
                    page_number=alt.get("page_number"),
                    supporting_text=alt.get("supporting_text"),
                    fact_field="named_owner_or_seller",
                    original_value=alt.get("original_value"),
                    verification_status="conflicting",
                ))

            findings.append({
                "rule_key": "ownership_conflict",
                "property_id": property_id,
                "category": RiskCategory.OWNERSHIP_TITLE.value,
                "severity": RiskSeverity.CRITICAL.value,
                "title": "Conflicting Ownership or Seller Identities Across Documents",
                "description": (
                    "Multiple documents associate differing seller or owner names with this property, "
                    "or present mutually contradictory title claims."
                ),
                "reason": (
                    owner_fact.uncertainty_note
                    or "Discrepancy detected between legal instruments regarding the rightful owner/vendor."
                ),
                "recommended_action": (
                    "Conduct an official sub-registrar title search and inspect registered devolution "
                    "documents (conveyance, probate, or partition deeds) to establish unbroken chain of title."
                ),
                "evidence": [e.model_dump() for e in evidence_items],
                "affected_facts": ["named_owner_or_seller", "ownership_claims"],
            })

        # 2. Missing Owner / Vendor Name
        if owner_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_owner_name",
                "property_id": property_id,
                "category": RiskCategory.OWNERSHIP_TITLE.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Missing Named Owner or Seller in Document Inventory",
                "description": "None of the uploaded documents establish the identity of the named owner or seller.",
                "reason": "Ownership field could not be established from available document text.",
                "recommended_action": (
                    "Obtain copy of the registered Sale Deed or Allotment Letter confirming "
                    "the vendor's legal identity."
                ),
                "evidence": [],
                "affected_facts": ["named_owner_or_seller"],
            })

        # 3. Missing Title Deed References
        title_ref = ownership.title_deed_references
        if title_ref.extracted_value is None:
            findings.append({
                "rule_key": "missing_title_deed_ref",
                "property_id": property_id,
                "category": RiskCategory.OWNERSHIP_TITLE.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Missing Title Deed References",
                "description": "No registered conveyance deed, sale deed, or mother deed reference is cited.",
                "reason": "Title deed reference field is absent across all uploaded instruments.",
                "recommended_action": (
                    "Request parent title deeds and registration details for a minimum 30-year search period."
                ),
                "evidence": [],
                "affected_facts": ["title_deed_references"],
            })

        # 4. Unverified Ownership Claims
        if claims_fact.extracted_value and claims_fact.verification_status == "unverified":
            findings.append({
                "rule_key": "unverified_ownership_claims",
                "property_id": property_id,
                "category": RiskCategory.OWNERSHIP_TITLE.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Unverified Ownership Claims",
                "description": "Ownership assertion was extracted but is not fully substantiated by supporting clauses.",
                "reason": claims_fact.uncertainty_note or "Text does not contain verifiable operative conveyance wording.",
                "recommended_action": "Engage legal counsel to examine operative granting clauses in the deed.",
                "evidence": [self._fact_to_evidence(claims_fact).model_dump()],
                "affected_facts": ["ownership_claims"],
            })

        return findings

    def _evaluate_regulatory_approval_rules(
        self, property_id: str, data: PropertyExtractionData
    ) -> list[dict[str, Any]]:
        findings = []
        approvals = data.approvals

        # 1. Conflicting approvals
        has_approval_conflict = any(
            getattr(approvals, f).verification_status == "conflicting"
            for f in ("project_registration_references", "building_plan_approvals", "occupancy_certificates", "completion_certificates")
        ) or any(c.topic == "approvals" for c in data.conflicts)

        if has_approval_conflict:
            findings.append({
                "rule_key": "approval_conflicts",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Conflicting Regulatory Sanction or RERA References",
                "description": "Contradictory building sanction or RERA registration numbers found across documents.",
                "reason": "Different documents report conflicting approval IDs or registration codes.",
                "recommended_action": (
                    "Cross-reference sanction codes directly with the state RERA portal "
                    "and municipal planning department."
                ),
                "evidence": [
                    self._fact_to_evidence(getattr(approvals, f)).model_dump()
                    for f in ("project_registration_references", "building_plan_approvals")
                    if getattr(approvals, f).filename
                ],
                "affected_facts": ["project_registration_references", "building_plan_approvals"],
            })

        # 2. Missing Occupancy Certificate (OC)
        oc_fact = approvals.occupancy_certificates
        if oc_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_occupancy_certificate",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Occupancy Certificate (OC) Not Found in Document Set",
                "description": (
                    "The property document set does not cite or include an Occupancy Certificate. "
                    "Note: Applicability depends on construction milestone; absence is a diligence gap, "
                    "not conclusive proof of a violation."
                ),
                "reason": "No Occupancy Certificate referenced in available documents.",
                "recommended_action": (
                    "Inquire whether Part or Final OC has been issued by the local authority "
                    "prior to physical possession."
                ),
                "evidence": [],
                "affected_facts": ["occupancy_certificates"],
            })

        # 3. Missing Completion Certificate (CC)
        cc_fact = approvals.completion_certificates
        if cc_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_completion_certificate",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Completion Certificate (CC) Not Found in Document Set",
                "description": "No formal architect or municipal completion certificate was located.",
                "reason": "Completion Certificate is unmentioned across uploaded documentation.",
                "recommended_action": "Request verification of building completion status from developer.",
                "evidence": [],
                "affected_facts": ["completion_certificates"],
            })

        # 4. Missing Building Plan Sanctions
        bp_fact = approvals.building_plan_approvals
        if bp_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_building_plan_approvals",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Building Plan Approval Reference Missing",
                "description": "No Intimation of Disapproval (IOD) or sanctioned layout plan cited.",
                "reason": "Building plan approvals missing from document records.",
                "recommended_action": "Verify municipal sanctioned floor plans to ensure unit does not deviate from approvals.",
                "evidence": [],
                "affected_facts": ["building_plan_approvals"],
            })

        # 5. Missing RERA Project Registration
        rera_fact = approvals.project_registration_references
        if rera_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_project_registration",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Project Registration (RERA) Reference Missing",
                "description": "No RERA registration number identified in property documents.",
                "reason": "Registration details absent from document inventory.",
                "recommended_action": "Check state RERA portal to confirm registration or statutory exemption.",
                "evidence": [],
                "affected_facts": ["project_registration_references"],
            })

        # 6. Environmental / Fire Clearance Status Unconfirmed
        fire_fact = approvals.fire_and_environmental_approvals
        if fire_fact.extracted_value is None:
            findings.append({
                "rule_key": "unconfirmed_environmental_fire",
                "property_id": property_id,
                "category": RiskCategory.REGULATORY_APPROVAL.value,
                "severity": RiskSeverity.INFORMATIONAL.value,
                "title": "Fire & Environmental Approvals Unconfirmed",
                "description": (
                    "No fire NOC or environmental clearance cited. Applicability is unknown without "
                    "height, plot area, and layout specifications."
                ),
                "reason": "Fire and environmental approvals not mentioned; applicability undetermined.",
                "recommended_action": "Check if high-rise or large-layout clearances are mandatory for this specific project.",
                "evidence": [],
                "affected_facts": ["fire_and_environmental_approvals"],
            })

        return findings

    def _evaluate_financial_rules(
        self, property_id: str, data: PropertyExtractionData
    ) -> list[dict[str, Any]]:
        findings = []
        financial = data.financial

        # 1. Conflicting Sale Consideration
        price_fact = financial.sale_price
        if price_fact.verification_status == "conflicting":
            evidence_items = []
            if price_fact.filename:
                evidence_items.append(self._fact_to_evidence(price_fact))
            for alt in price_fact.alternative_values:
                evidence_items.append(RiskEvidenceItem(
                    document_id=alt.get("document_id"),
                    filename=alt.get("filename"),
                    page_number=alt.get("page_number"),
                    supporting_text=alt.get("supporting_text"),
                    fact_field="sale_price",
                    original_value=alt.get("original_value"),
                    verification_status="conflicting",
                ))

            findings.append({
                "rule_key": "financial_price_conflict",
                "property_id": property_id,
                "category": RiskCategory.FINANCIAL.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Conflicting Monetary Consideration Across Documents",
                "description": "Different legal documents record materially conflicting consideration or sale figures.",
                "reason": price_fact.uncertainty_note or "Discrepancy in sale price across distinct instruments.",
                "recommended_action": (
                    "Reconcile payment receipts, stamp duty challans, and registered agreement "
                    "to confirm exact lawful consideration."
                ),
                "evidence": [e.model_dump() for e in evidence_items],
                "affected_facts": ["sale_price"],
            })

        # 2. Conflicting Booking Amount or Payment Schedule
        booking_fact = financial.booking_amount
        sched_fact = financial.payment_schedule
        if (
            booking_fact.verification_status == "conflicting"
            or sched_fact.verification_status == "conflicting"
        ):
            findings.append({
                "rule_key": "booking_schedule_conflict",
                "property_id": property_id,
                "category": RiskCategory.FINANCIAL.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Discrepancy in Booking Amount or Payment Schedule",
                "description": "Conflicting milestone deadlines, installment percentages, or booking tokens cited.",
                "reason": "Payment schedule terms vary across uploaded documents.",
                "recommended_action": "Request builder's ledger / statement of account and demand letters.",
                "evidence": [
                    self._fact_to_evidence(f).model_dump()
                    for f in (booking_fact, sched_fact)
                    if f.filename
                ],
                "affected_facts": ["booking_amount", "payment_schedule"],
            })

        # 3. Missing Sale Price
        if price_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_sale_price",
                "property_id": property_id,
                "category": RiskCategory.FINANCIAL.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Transaction Consideration Not Disclosed",
                "description": "Financial consideration is missing across all uploaded documents.",
                "reason": "Sale price field absent.",
                "recommended_action": "Ensure full consideration and payment terms are documented in executed agreements.",
                "evidence": [],
                "affected_facts": ["sale_price"],
            })

        # 4. Unexplained Additional Charges
        deposit_fact = financial.deposits_and_additional_charges
        if deposit_fact.extracted_value:
            findings.append({
                "rule_key": "unexplained_charges",
                "property_id": property_id,
                "category": RiskCategory.FINANCIAL.value,
                "severity": RiskSeverity.LOW.value,
                "title": "Ancillary Deposits & Additional Charges Noted",
                "description": "Non-consideration charges or deposits (clubhouse, parking, electrification) are noted.",
                "reason": f"Additional charges specified: '{deposit_fact.extracted_value}'.",
                "recommended_action": "Verify itemized breakdown to ensure compliance with statutory rules on parking and society transfer fees.",
                "evidence": [self._fact_to_evidence(deposit_fact).model_dump()] if deposit_fact.filename else [],
                "affected_facts": ["deposits_and_additional_charges"],
            })

        return findings

    def _evaluate_identity_area_rules(
        self, property_id: str, data: PropertyExtractionData
    ) -> list[dict[str, Any]]:
        findings = []
        identity = data.identity

        # 1. Conflicting Area Measurements
        carpet_fact = identity.carpet_area
        builtup_fact = identity.built_up_area
        if (
            carpet_fact.verification_status == "conflicting"
            or builtup_fact.verification_status == "conflicting"
        ):
            evidence_items = []
            if carpet_fact.filename:
                evidence_items.append(self._fact_to_evidence(carpet_fact))
            for alt in carpet_fact.alternative_values:
                evidence_items.append(RiskEvidenceItem(
                    document_id=alt.get("document_id"),
                    filename=alt.get("filename"),
                    page_number=alt.get("page_number"),
                    supporting_text=alt.get("supporting_text"),
                    fact_field="carpet_area",
                    original_value=alt.get("original_value"),
                    verification_status="conflicting",
                ))

            findings.append({
                "rule_key": "area_conflict",
                "property_id": property_id,
                "category": RiskCategory.PROPERTY_IDENTITY.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Conflicting Property Area Measurements",
                "description": "Discrepancy detected in carpet area or built-up area figures across documents.",
                "reason": carpet_fact.uncertainty_note or "Area figures materially disagree between documents.",
                "recommended_action": "Commission independent architect carpet area measurement against sanctioned municipal plan.",
                "evidence": [e.model_dump() for e in evidence_items],
                "affected_facts": ["carpet_area", "built_up_area"],
            })

        # 2. Conflicting Unit Number or Address
        unit_fact = identity.unit_number
        addr_fact = identity.property_address
        if (
            unit_fact.verification_status == "conflicting"
            or addr_fact.verification_status == "conflicting"
        ):
            findings.append({
                "rule_key": "unit_address_conflict",
                "property_id": property_id,
                "category": RiskCategory.PROPERTY_IDENTITY.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Inconsistent Unit Number or Property Address",
                "description": "Unit designation, floor number, wing, or plot address differs between documents.",
                "reason": "Inconsistent property identification across documents.",
                "recommended_action": "Cross-check municipal assessment tax bill and electricity bill for exact demarcation.",
                "evidence": [
                    self._fact_to_evidence(f).model_dump()
                    for f in (unit_fact, addr_fact)
                    if f.filename
                ],
                "affected_facts": ["unit_number", "property_address"],
            })

        # 3. Missing Carpet Area
        if carpet_fact.extracted_value is None:
            findings.append({
                "rule_key": "missing_carpet_area",
                "property_id": property_id,
                "category": RiskCategory.PROPERTY_IDENTITY.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Carpet Area Not Established in Documentation",
                "description": "Carpet area is unmentioned. RERA mandates net usable carpet area specification.",
                "reason": "Carpet area field is missing across documents.",
                "recommended_action": "Obtain carpet area certificate signed by project architect.",
                "evidence": [],
                "affected_facts": ["carpet_area"],
            })

        return findings

    def _evaluate_legal_dispute_rules(
        self,
        property_id: str,
        data: PropertyExtractionData,
        documents: list[Document] | None = None,
    ) -> list[dict[str, Any]]:
        findings = []
        ownership = data.ownership_legal

        # 1. Explicit Litigation References
        lit_fact = ownership.litigation_references
        lit_text = str(lit_fact.extracted_value or "") + " " + str(lit_fact.supporting_text or "")
        has_lit_kw = bool(_LITIGATION_KEYWORDS.search(lit_text))
        has_lit_negation = bool(_LITIGATION_NEGATIONS.search(lit_text))

        evidence_items = []
        if lit_fact.filename and has_lit_kw and not has_lit_negation:
            evidence_items.append(self._fact_to_evidence(lit_fact).model_dump())

        # Inspect document chunk texts directly for explicit litigation references
        if documents and not has_lit_kw:
            for d in documents:
                for c in getattr(d, "chunks", []):
                    c_text = c.text or ""
                    if _LITIGATION_KEYWORDS.search(c_text) and not _LITIGATION_NEGATIONS.search(c_text):
                        has_lit_kw = True
                        lit_text = c_text[:250]
                        evidence_items.append(
                            RiskEvidenceItem(
                                document_id=d.id,
                                filename=d.filename,
                                page_number=c.page_number or 1,
                                supporting_text=c_text[:300],
                                fact_field="litigation_references",
                                verification_status="supported",
                            ).model_dump()
                        )
                        break
                if has_lit_kw:
                    break

        if has_lit_kw and not has_lit_negation:
            findings.append({
                "rule_key": "litigation_detected",
                "property_id": property_id,
                "category": RiskCategory.LEGAL_DISPUTE.value,
                "severity": RiskSeverity.CRITICAL.value,
                "title": "Explicit Litigation or Legal Dispute Reference Detected",
                "description": "Document text references pending court proceedings, lawsuits, or interim orders.",
                "reason": f"Dispute keywords identified in text: '{lit_text[:180]}...'",
                "recommended_action": (
                    "Urgent: Check e-Courts portal for case status, interim stay orders, "
                    "and lis pendens notices."
                ),
                "evidence": evidence_items,
                "affected_facts": ["litigation_references"],
            })

        # 2. Active Mortgage or Encumbrance Claim
        enc_fact = ownership.encumbrance_information
        enc_text = str(enc_fact.extracted_value or "") + " " + str(enc_fact.supporting_text or "")
        has_enc_kw = bool(_ENCUMBRANCE_KEYWORDS.search(enc_text))
        has_enc_negation = bool(_ENCUMBRANCE_NEGATIONS.search(enc_text))

        enc_evidence = []
        if enc_fact.filename and has_enc_kw and not has_enc_negation:
            enc_evidence.append(self._fact_to_evidence(enc_fact).model_dump())

        if documents and not has_enc_kw:
            for d in documents:
                for c in getattr(d, "chunks", []):
                    c_text = c.text or ""
                    if _ENCUMBRANCE_KEYWORDS.search(c_text) and not _ENCUMBRANCE_NEGATIONS.search(c_text):
                        has_enc_kw = True
                        enc_text = c_text[:250]
                        enc_evidence.append(
                            RiskEvidenceItem(
                                document_id=d.id,
                                filename=d.filename,
                                page_number=c.page_number or 1,
                                supporting_text=c_text[:300],
                                fact_field="encumbrance_information",
                                verification_status="supported",
                            ).model_dump()
                        )
                        break
                if has_enc_kw:
                    break

        if has_enc_kw and not has_enc_negation:
            findings.append({
                "rule_key": "encumbrance_detected",
                "property_id": property_id,
                "category": RiskCategory.LEGAL_DISPUTE.value,
                "severity": RiskSeverity.CRITICAL.value,
                "title": "Active Mortgage or Financial Encumbrance Detected",
                "description": "Document passages state property is subject to a bank mortgage or financial charge.",
                "reason": f"Encumbrance statement identified: '{enc_text[:180]}...'",
                "recommended_action": (
                    "Demand bank No Objection Certificate (NOC) and registered Release / Reconveyance Deed "
                    "clearing the charge."
                ),
                "evidence": enc_evidence,
                "affected_facts": ["encumbrance_information"],
            })

        # 3. Unverified Non-Litigation Status
        if lit_fact.extracted_value and lit_fact.verification_status == "unverified":
            findings.append({
                "rule_key": "unverified_litigation_status",
                "property_id": property_id,
                "category": RiskCategory.LEGAL_DISPUTE.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Unverified Non-Litigation Declaration",
                "description": "Non-litigation assertion is stated by vendor but not independently substantiated.",
                "reason": "Supporting clause lacks independent registry or judicial search backing.",
                "recommended_action": "Commission advocate search report in local civil and revenue courts.",
                "evidence": [self._fact_to_evidence(lit_fact).model_dump()] if lit_fact.filename else [],
                "affected_facts": ["litigation_references"],
            })

        return findings

    def _evaluate_documentation_completeness_rules(
        self,
        property_id: str,
        data: PropertyExtractionData,
        documents: list[Document],
    ) -> list[dict[str, Any]]:
        findings = []

        # 1. Scanned Documents Requiring OCR
        ocr_docs = [d for d in documents if d.status == "ocr_required"]
        if ocr_docs:
            findings.append({
                "rule_key": "scanned_ocr_required_docs",
                "property_id": property_id,
                "category": RiskCategory.DOCUMENTATION_COMPLETENESS.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Scanned Document(s) Require OCR Processing",
                "description": (
                    f"{len(ocr_docs)} document(s) contain scanned pages with limited text extractability. "
                    "Key covenants may remain unanalyzed."
                ),
                "reason": f"Documents requiring OCR: {', '.join(d.filename for d in ocr_docs[:3])}.",
                "recommended_action": "Run optical character recognition or upload native text PDFs.",
                "evidence": [
                    RiskEvidenceItem(
                        document_id=d.id,
                        filename=d.filename,
                        verification_status="ocr_required",
                    ).model_dump()
                    for d in ocr_docs
                ],
                "affected_facts": [],
            })

        # 2. Failed Ingestion Documents
        failed_docs = [d for d in documents if d.status == "failed"]
        if failed_docs:
            findings.append({
                "rule_key": "failed_processing_docs",
                "property_id": property_id,
                "category": RiskCategory.DOCUMENTATION_COMPLETENESS.value,
                "severity": RiskSeverity.HIGH.value,
                "title": "Failed or Unreadable Document(s) in Inventory",
                "description": f"{len(failed_docs)} document(s) failed ingestion and could not be evaluated.",
                "reason": f"Failed documents: {', '.join(d.filename for d in failed_docs[:3])}.",
                "recommended_action": "Re-upload readable, uncorrupted versions of the failed documents.",
                "evidence": [
                    RiskEvidenceItem(
                        document_id=d.id,
                        filename=d.filename,
                        verification_status="failed",
                    ).model_dump()
                    for d in failed_docs
                ],
                "affected_facts": [],
            })

        # 3. High Number of Unverified Facts
        if data.unverified_count >= 3:
            findings.append({
                "rule_key": "high_unverified_fact_count",
                "property_id": property_id,
                "category": RiskCategory.DOCUMENTATION_COMPLETENESS.value,
                "severity": RiskSeverity.MEDIUM.value,
                "title": "Multiple Extracted Attributes Lack Passage Entailment",
                "description": (
                    f"{data.unverified_count} extracted facts could not be fully substantiated "
                    "by exact supporting text quotes."
                ),
                "reason": "Text evidence is ambiguous or incomplete for multiple attributes.",
                "recommended_action": "Conduct manual human legal verification of the highlighted unverified facts.",
                "evidence": [],
                "affected_facts": [],
            })

        # 4. Sparse Document Set
        if len(documents) == 1:
            findings.append({
                "rule_key": "sparse_document_inventory",
                "property_id": property_id,
                "category": RiskCategory.DOCUMENTATION_COMPLETENESS.value,
                "severity": RiskSeverity.LOW.value,
                "title": "Single Document Due Diligence Limitation",
                "description": (
                    "Only 1 document is associated with this property. Cross-document validation "
                    "cannot detect discrepancies without comparison records."
                ),
                "reason": "Property has only a single associated document.",
                "recommended_action": (
                    "Associate complementary documents (e.g. Allotment Letter, Index II, Sanction Plan, Tax Receipt) "
                    "for multi-instrument verification."
                ),
                "evidence": [],
                "affected_facts": [],
            })

        return findings

    # --- Persistence Helpers ---------------------------------------------

    def _persist_assessment_and_findings(
        self,
        property_id: str,
        current_hashes: dict[str, str],
        new_findings: list[dict[str, Any]],
    ) -> PropertyRiskAssessment:
        """Persist or update assessment and findings, preserving user review status."""
        try:
            with self._get_session_factory()() as session:
                assessment = (
                    session.query(PropertyRiskAssessment)
                    .filter(PropertyRiskAssessment.property_id == property_id)
                    .one_or_none()
                )

                now = datetime.now()
                if assessment is None:
                    assessment_id = f"ra_{uuid.uuid4().hex[:16]}"
                    assessment = PropertyRiskAssessment(
                        id=assessment_id,
                        property_id=property_id,
                        status="completed",
                        document_hashes=current_hashes,
                        summary={},
                        error_message=None,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(assessment)
                    session.flush()
                else:
                    assessment.status = "completed"
                    assessment.document_hashes = current_hashes
                    assessment.updated_at = now

                # Existing findings map by rule_key to preserve user review status
                existing_findings_map: dict[str, PropertyRiskFinding] = {
                    f.rule_key: f
                    for f in session.query(PropertyRiskFinding)
                    .filter(PropertyRiskFinding.assessment_id == assessment.id)
                    .all()
                }

                current_rule_keys = set()
                persisted_findings: list[PropertyRiskFinding] = []

                for finding_dict in new_findings:
                    rule_key = finding_dict["rule_key"]
                    current_rule_keys.add(rule_key)

                    existing_finding = existing_findings_map.get(rule_key)

                    if existing_finding is not None:
                        # Update description, evidence, recommendation, severity but PRESERVE user review status & notes
                        existing_finding.category = finding_dict["category"]
                        existing_finding.severity = finding_dict["severity"]
                        existing_finding.title = finding_dict["title"]
                        existing_finding.description = finding_dict["description"]
                        existing_finding.reason = finding_dict["reason"]
                        existing_finding.recommended_action = finding_dict["recommended_action"]
                        existing_finding.evidence = finding_dict["evidence"]
                        existing_finding.affected_facts = finding_dict["affected_facts"]
                        existing_finding.updated_at = now
                        persisted_findings.append(existing_finding)
                    else:
                        # New finding
                        finding_id = f"rf_{uuid.uuid4().hex[:16]}"
                        new_finding_rec = PropertyRiskFinding(
                            id=finding_id,
                            assessment_id=assessment.id,
                            property_id=property_id,
                            rule_key=rule_key,
                            category=finding_dict["category"],
                            severity=finding_dict["severity"],
                            status=RiskFindingStatus.OPEN.value,
                            title=finding_dict["title"],
                            description=finding_dict["description"],
                            reason=finding_dict["reason"],
                            recommended_action=finding_dict["recommended_action"],
                            evidence=finding_dict["evidence"],
                            affected_facts=finding_dict["affected_facts"],
                            user_notes=None,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(new_finding_rec)
                        persisted_findings.append(new_finding_rec)

                # For findings previously recorded that are no longer triggered by new documents, mark as resolved
                for old_key, old_finding in existing_findings_map.items():
                    if old_key not in current_rule_keys:
                        if old_finding.status == RiskFindingStatus.OPEN.value:
                            old_finding.status = RiskFindingStatus.RESOLVED.value
                            old_finding.user_notes = (
                                (old_finding.user_notes or "")
                                + " [Automatically resolved: condition no longer present in updated documents.]"
                            ).strip()
                            old_finding.updated_at = now
                        persisted_findings.append(old_finding)

                session.flush()

                # Recompute and store summary
                summary = self._compute_summary(persisted_findings)
                assessment.summary = summary.model_dump()
                session.commit()
                session.refresh(assessment)

                return assessment
        except Exception as exc:
            logger.error("Failed persisting risk assessment for %s: %s", property_id, exc)
            raise PropertyError(f"Database error persisting risk assessment: {exc}", status_code=500) from exc

    def _compute_summary(
        self, findings: Sequence[PropertyRiskFinding]
    ) -> PropertyRiskAssessmentSummary:
        """Calculate counts by severity and status."""
        summary = PropertyRiskAssessmentSummary(total_findings=len(findings))
        for f in findings:
            # Severity
            if f.severity == RiskSeverity.CRITICAL.value:
                summary.critical_count += 1
            elif f.severity == RiskSeverity.HIGH.value:
                summary.high_count += 1
            elif f.severity == RiskSeverity.MEDIUM.value:
                summary.medium_count += 1
            elif f.severity == RiskSeverity.LOW.value:
                summary.low_count += 1
            elif f.severity == RiskSeverity.INFORMATIONAL.value:
                summary.informational_count += 1

            # Status
            if f.status == RiskFindingStatus.OPEN.value:
                summary.open_count += 1
            elif f.status == RiskFindingStatus.UNDER_REVIEW.value:
                summary.under_review_count += 1
            elif f.status == RiskFindingStatus.RESOLVED.value:
                summary.resolved_count += 1
            elif f.status == RiskFindingStatus.DISMISSED.value:
                summary.dismissed_count += 1

        return summary

    def _fetch_property_and_documents(
        self, property_id: str, user_id: str
    ) -> tuple[Property, list[Document], dict[str, str]]:
        """Verify property ownership and retrieve documents with sha256 hashes."""
        try:
            with self._get_session_factory()() as session:
                prop = (
                    session.query(Property)
                    .filter(Property.id == property_id, Property.owner_id == user_id)
                    .one_or_none()
                )
                if prop is None:
                    raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                docs = (
                    session.query(Document)
                    .options(selectinload(Document.chunks))
                    .filter(
                        (Document.property_id == property_id)
                        | (Document.property_associations.any(property_id=property_id))
                    )
                    .all()
                )

                hashes = {d.id: d.content_sha256 for d in docs}
                return prop, docs, hashes
        except PropertyError:
            raise
        except Exception as exc:
            logger.error("Database query failed for property %s: %s", property_id, exc)
            raise PropertyError(f"Database read failure: {exc}", status_code=500) from exc

    def _fetch_existing_assessment(self, property_id: str) -> PropertyRiskAssessment | None:
        """Fetch stored assessment record."""
        try:
            with self._get_session_factory()() as session:
                return (
                    session.query(PropertyRiskAssessment)
                    .filter(PropertyRiskAssessment.property_id == property_id)
                    .one_or_none()
                )
        except Exception as exc:
            logger.error("Failed fetching assessment for %s: %s", property_id, exc)
            return None

    def _build_response_from_db(
        self,
        assessment: PropertyRiskAssessment,
        document_count: int,
        is_stale: bool,
    ) -> PropertyRiskAssessmentResponse:
        """Construct validated response schema from SQLAlchemy ORM record."""
        with self._get_session_factory()() as session:
            db_findings = (
                session.query(PropertyRiskFinding)
                .filter(PropertyRiskFinding.assessment_id == assessment.id)
                .all()
            )
            findings = [self._finding_model_to_schema(f) for f in db_findings]

        summary_dict = assessment.summary or {}
        summary = PropertyRiskAssessmentSummary(**summary_dict)

        return PropertyRiskAssessmentResponse(
            assessment_id=assessment.id,
            property_id=assessment.property_id,
            status="stale" if is_stale else assessment.status,  # type: ignore
            summary=summary,
            findings=findings,
            document_count=document_count,
            is_stale=is_stale,
            error_message=assessment.error_message,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
        )

    def _finding_model_to_schema(
        self, f: PropertyRiskFinding
    ) -> PropertyRiskFindingResponse:
        """Map ORM finding record to Pydantic schema."""
        raw_evidence = f.evidence or []
        evidence_items = [
            RiskEvidenceItem(**e) if isinstance(e, dict) else e for e in raw_evidence
        ]

        return PropertyRiskFindingResponse(
            risk_id=f.id,
            property_id=f.property_id,
            rule_key=f.rule_key,
            category=RiskCategory(f.category),
            severity=RiskSeverity(f.severity),
            status=RiskFindingStatus(f.status),
            title=f.title,
            description=f.description,
            reason=f.reason,
            recommended_action=f.recommended_action,
            evidence=evidence_items,
            affected_facts=f.affected_facts or [],
            user_notes=f.user_notes,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )

    @staticmethod
    def _fact_to_evidence(fact: ExtractedFieldFact) -> RiskEvidenceItem:
        """Convert extracted fact to traceable risk evidence item."""
        return RiskEvidenceItem(
            document_id=fact.document_id,
            filename=fact.filename,
            page_number=fact.page_number,
            supporting_text=fact.supporting_text,
            fact_field=fact.field_name,
            verification_status=fact.verification_status,
            original_value=fact.original_value,
        )
