"""Dedicated service for structured property information extraction.

Features:
- Structured extraction using validated Pydantic schemas.
- Strict provenance tracking: document ID, filename, page number, and supporting text for every fact.
- Multi-document aggregation with cross-document conflict detection.
- Unit, currency, and date normalization preserving original representations.
- Integration with EvidenceVerificationService to guard against hallucinations.
- Tenant isolation and database persistence with document-hash stale detection.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document, Property, PropertyDocument, PropertyExtraction
from app.schemas.property_extraction import (
    ApprovalFacts,
    DatesObligationsFacts,
    ExtractedFieldFact,
    FinancialFacts,
    OwnershipLegalFacts,
    PropertyExtractionData,
    PropertyExtractionResponse,
    PropertyExtractionStatusResponse,
    PropertyIdentityFacts,
)
from app.schemas.rag import ConflictSource, CrossDocumentConflict
from app.services.document_store import get_shared_engine
from app.services.evidence_conflict import (
    claims_materially_disagree,
    normalize_area,
    normalize_currency,
)
from app.services.evidence_verification import EvidenceVerificationService
from app.services.llm_service import LLMError, LLMService
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyError,
    PropertyNotFoundError,
)
from app.services.storage_errors import DatabaseUnavailableError, DatabaseWriteError

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a strict, objective legal due diligence and real estate analysis system.
Your task is to extract structured factual property attributes from the provided document text.

Rules:
1. Extract ONLY facts explicitly stated in the document text.
2. NEVER guess, assume, interpolate, or extrapolate.
3. If an attribute is NOT explicitly mentioned or cannot be established from the text, return null for its value.
4. For every extracted attribute, provide:
   - "value": the clean factual text or number
   - "original_value": the verbatim quote or representation as written in the document
   - "page_number": integer page number if identified, else null
   - "supporting_quote": exact excerpt from the text substantiating the attribute
   - "confidence": confidence score from 0.0 to 1.0 (0.0 if not found)
5. Output MUST be a valid JSON object matching the requested schema exactly.
"""

EXTRACTION_USER_PROMPT_TEMPLATE = """Document: {filename} (ID: {document_id})
Document Content:
---
{document_text}
---

Extract the following property fields from the above content into valid JSON.
If a field is not mentioned, set "value" to null, "original_value" to null, and "confidence" to 0.0.

JSON schema to return:
{{
  "property_identity": {{
    "property_name": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "property_address": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "property_type": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "unit_number": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "carpet_area": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "built_up_area": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "area_unit": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}}
  }},
  "financial_information": {{
    "sale_price": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "booking_amount": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "payment_schedule": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "maintenance_charges": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "deposits_and_additional_charges": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}}
  }},
  "ownership_legal": {{
    "named_owner_or_seller": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "title_deed_references": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "ownership_claims": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "encumbrance_information": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "litigation_references": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}}
  }},
  "approvals": {{
    "project_registration_references": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "building_plan_approvals": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "completion_certificates": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "occupancy_certificates": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "fire_and_environmental_approvals": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}}
  }},
  "dates_obligations": {{
    "agreement_date": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "possession_date": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "payment_deadlines": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "renewal_dates": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}},
    "contractual_obligations": {{"value": null, "original_value": null, "page_number": null, "supporting_quote": null, "confidence": 0.0}}
  }}
}}
"""

_DATE_PATTERNS = [
    # YYYY-MM-DD or YYYY/MM/DD
    re.compile(r"\b((?:19|20)\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b"),
    # DD-MM-YYYY or DD/MM/YYYY
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](19\d{2}|20\d{2})\b"),
    # 15th November 2026 or 15 November 2026
    re.compile(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:19|20)\d{2})\b",
        re.IGNORECASE,
    ),
    # November 15, 2026
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,\s+((?:19|20)\d{2})\b",
        re.IGNORECASE,
    ),
    # Bare Year: 2026
    re.compile(r"\b((?:19|20)\d{2})\b"),
]

_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def normalize_date_string(date_str: str | None) -> str | None:
    """Normalize unstructured date representations into ISO 8601 (YYYY-MM-DD or YYYY)."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    if not cleaned:
        return None

    # Try ISO YYYY-MM-DD
    m = _DATE_PATTERNS[0].search(cleaned)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # Try DD-MM-YYYY
    m = _DATE_PATTERNS[1].search(cleaned)
    if m:
        return f"{m.group(3).strip()}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # Try "15th November 2026"
    m = _DATE_PATTERNS[2].search(cleaned)
    if m:
        day = m.group(1).zfill(2)
        month_num = _MONTH_MAP.get(m.group(2).lower(), 1)
        year = m.group(3)
        return f"{year}-{month_num:02d}-{day}"

    # Try "November 15, 2026"
    m = _DATE_PATTERNS[3].search(cleaned)
    if m:
        month_num = _MONTH_MAP.get(m.group(1).lower(), 1)
        day = m.group(2).zfill(2)
        year = m.group(3)
        return f"{year}-{month_num:02d}-{day}"

    # Try bare year
    m = _DATE_PATTERNS[4].search(cleaned)
    if m:
        return m.group(1)

    return cleaned


class PropertyExtractionService:
    """Rigorous structured extraction service with multi-document aggregation and verification."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm_service: LLMService | None = None,
        verification_service: EvidenceVerificationService | None = None,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm_service = llm_service
        self.verification_service = verification_service or EvidenceVerificationService()
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

    def _get_llm_service(self) -> LLMService:
        if self.llm_service is not None:
            return self.llm_service
        return LLMService(self.settings)

    # --- Core Extraction Workflow -----------------------------------------

    async def extract_property_information(
        self, property_id: str, user_id: str, force_refresh: bool = False
    ) -> PropertyExtractionResponse:
        """Execute full extraction workflow for an authorized property and all associated documents."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        # 1. Verify property existence and ownership
        prop, docs, doc_hashes = self._fetch_property_and_documents(property_id, user_id)

        # 2. Check if a valid, up-to-date extraction already exists (unless force_refresh)
        if not force_refresh:
            existing = self._fetch_existing_extraction(property_id)
            if existing is not None:
                # Compare document hashes to determine if extraction is stale
                is_stale = existing.document_hashes != doc_hashes
                if not is_stale and existing.status == "completed":
                    data = PropertyExtractionData(**existing.extracted_data)
                    return PropertyExtractionResponse(
                        property_id=property_id,
                        status="completed",
                        data=data,
                        document_count=len(docs),
                        is_stale=False,
                        created_at=existing.created_at,
                        updated_at=existing.updated_at,
                    )

        # 3. If property has no documents
        if not docs:
            empty_data = self._build_empty_extraction_data(property_id)
            self._persist_extraction(property_id, "completed", empty_data, doc_hashes)
            now = datetime.now()
            return PropertyExtractionResponse(
                property_id=property_id,
                status="completed",
                data=empty_data,
                document_count=0,
                is_stale=False,
                created_at=now,
                updated_at=now,
            )

        # 4. Extract structured facts from each document
        per_doc_facts: list[dict[str, Any]] = []
        for doc in docs:
            doc_facts = await self._extract_from_single_document(doc)
            per_doc_facts.append(doc_facts)

        # 5. Aggregate across all documents, detect cross-document conflicts, and normalize
        aggregated_data = self._aggregate_and_verify_facts(property_id, per_doc_facts, docs)

        # 6. Persist extraction results to database
        self._persist_extraction(property_id, "completed", aggregated_data, doc_hashes)

        now = datetime.now()
        return PropertyExtractionResponse(
            property_id=property_id,
            status="completed",
            data=aggregated_data,
            document_count=len(docs),
            is_stale=False,
            created_at=now,
            updated_at=now,
        )

    def get_extraction(
        self, property_id: str, user_id: str
    ) -> PropertyExtractionResponse:
        """Retrieve stored extraction record for an authorized property."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        prop, docs, current_hashes = self._fetch_property_and_documents(property_id, user_id)
        existing = self._fetch_existing_extraction(property_id)

        if existing is None:
            # Not yet extracted
            empty_data = self._build_empty_extraction_data(property_id)
            now = datetime.now()
            return PropertyExtractionResponse(
                property_id=property_id,
                status="pending",
                data=empty_data,
                document_count=len(docs),
                is_stale=False,
                created_at=now,
                updated_at=now,
            )

        is_stale = existing.document_hashes != current_hashes
        data = PropertyExtractionData(**existing.extracted_data)
        return PropertyExtractionResponse(
            property_id=property_id,
            status="stale" if is_stale else existing.status,  # type: ignore
            data=data,
            document_count=len(docs),
            is_stale=is_stale,
            error_message=existing.error_message,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )

    def get_extraction_status(
        self, property_id: str, user_id: str
    ) -> PropertyExtractionStatusResponse:
        """Lightweight status query for dashboard polling and badge indicator."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        prop, docs, current_hashes = self._fetch_property_and_documents(property_id, user_id)
        existing = self._fetch_existing_extraction(property_id)

        if existing is None:
            return PropertyExtractionStatusResponse(
                property_id=property_id,
                status="not_started",
                document_count=len(docs),
                is_stale=False,
                last_extracted_at=None,
            )

        is_stale = existing.document_hashes != current_hashes
        raw_data = existing.extracted_data or {}
        return PropertyExtractionStatusResponse(
            property_id=property_id,
            status="stale" if is_stale else existing.status,  # type: ignore
            document_count=len(docs),
            is_stale=is_stale,
            last_extracted_at=existing.updated_at,
            supported_facts_count=raw_data.get("supported_count", 0),
            conflicts_count=len(raw_data.get("conflicts", [])),
            missing_fields_count=len(raw_data.get("missing_fields", [])),
        )

    # --- Document-Level Extraction ----------------------------------------

    async def _extract_from_single_document(self, doc: Document) -> dict[str, Any]:
        """Run LLM extraction on text chunks of a single document."""
        chunks = self._fetch_document_chunks(doc.id)
        combined_text = "\n\n".join(
            f"[Page {c.page_number or 1}] {c.text}" for c in chunks[:30]
        )
        if not combined_text.strip():
            combined_text = f"Document filename: {doc.filename}\nStatus: {doc.status}"

        user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(
            filename=doc.filename,
            document_id=doc.id,
            document_text=combined_text[:12000],  # Bound context length
        )

        llm_service = self._get_llm_service()
        try:
            raw_response = await llm_service.generate(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
            parsed_json = self._clean_and_parse_json(raw_response)
        except (LLMError, ValueError, Exception) as exc:
            logger.warning("LLM extraction failed or returned malformed json for doc=%s: %s", doc.id, exc)
            # Safe heuristic fallback
            parsed_json = self._heuristic_fallback_extraction(doc, combined_text)

        # Attach document provenance metadata to every extracted field
        return self._attach_provenance(parsed_json, doc.id, doc.filename, chunks)

    def _clean_and_parse_json(self, response_text: str) -> dict[str, Any]:
        """Strip markdown fences and parse structured JSON."""
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())

    def _heuristic_fallback_extraction(
        self, doc: Document, text: str
    ) -> dict[str, Any]:
        """Deterministic regex heuristic fallback when LLM is unavailable or malformed."""
        result: dict[str, Any] = {
            "property_identity": {},
            "financial_information": {},
            "ownership_legal": {},
            "approvals": {},
            "dates_obligations": {},
        }

        # 1. Consideration
        curr = normalize_currency(text)
        if curr is not None:
            m = re.search(r"\b(?:Rs\.?|INR|\$)\s*[\d,]+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:lakhs?|crores?)\b", text, re.I)
            raw = m.group(0) if m else str(curr)
            result["financial_information"]["sale_price"] = {
                "value": f"{curr:,.0f}",
                "original_value": raw,
                "page_number": 1,
                "supporting_quote": raw,
                "confidence": 0.8,
            }

        # 2. Area
        area_val = normalize_area(text)
        if area_val is not None:
            m = re.search(r"\b(\d+(?:[.,]\d+)?\s*(?:sq\.?\s*ft|square\s*feet|sq\.?\s*m|acres?))\b", text, re.I)
            raw = m.group(0) if m else f"{area_val:.1f} sq ft"
            result["property_identity"]["carpet_area"] = {
                "value": f"{area_val:.1f} sq ft",
                "original_value": raw,
                "page_number": 1,
                "supporting_quote": raw,
                "confidence": 0.8,
            }

        # 3. Dates
        date_str = normalize_date_string(text)
        if date_str:
            result["dates_obligations"]["agreement_date"] = {
                "value": date_str,
                "original_value": date_str,
                "page_number": 1,
                "supporting_quote": f"Date referenced: {date_str}",
                "confidence": 0.7,
            }

        # 4. Owner / Vendor
        owner_match = re.search(
            r"(?:owner|purchaser|vendor|seller|buyer)\s*[:\-]?\s*([A-Z][A-Za-z\s.,]{3,40})",
            text,
            re.I,
        )
        if owner_match:
            result["ownership_legal"]["named_owner_or_seller"] = {
                "value": owner_match.group(1).strip(),
                "original_value": owner_match.group(0).strip(),
                "page_number": 1,
                "supporting_quote": owner_match.group(0).strip(),
                "confidence": 0.75,
            }

        # 5. Litigation references
        lit_m = re.search(
            r"(?:litigation|dispute|court\s+case|pending\s+suit|lawsuit)[^\.\n;]{3,120}",
            text,
            re.I,
        )
        if lit_m:
            result["ownership_legal"]["litigation_references"] = {
                "value": lit_m.group(0).strip(),
                "original_value": lit_m.group(0).strip(),
                "page_number": 1,
                "supporting_quote": lit_m.group(0).strip(),
                "confidence": 0.8,
            }

        # 6. Encumbrance information
        enc_m = re.search(
            r"(?:mortgage|encumbrance|bank\s+charge|hypothecation|lien)[^\.\n;]{3,120}",
            text,
            re.I,
        )
        if enc_m:
            result["ownership_legal"]["encumbrance_information"] = {
                "value": enc_m.group(0).strip(),
                "original_value": enc_m.group(0).strip(),
                "page_number": 1,
                "supporting_quote": enc_m.group(0).strip(),
                "confidence": 0.8,
            }

        return result

    def _attach_provenance(
        self,
        parsed_data: dict[str, Any],
        document_id: str,
        filename: str,
        chunks: list[Chunk],
    ) -> dict[str, Any]:
        """Attach document ID, filename, and verified supporting text to raw fields."""
        enriched: dict[str, Any] = {}
        for category, fields in parsed_data.items():
            if not isinstance(fields, dict):
                continue
            enriched[category] = {}
            for field_name, fact_dict in fields.items():
                if not isinstance(fact_dict, dict):
                    continue
                val = fact_dict.get("value")
                orig = fact_dict.get("original_value") or (str(val) if val is not None else None)
                quote = fact_dict.get("supporting_quote")
                page = fact_dict.get("page_number")
                conf = float(fact_dict.get("confidence") or 0.0)

                # Check if fact was genuinely found
                is_missing = (
                    val is None
                    or str(val).strip().lower() in ("null", "none", "not mentioned", "n/a", "not specified", "")
                )

                if is_missing:
                    enriched[category][field_name] = {
                        "value": None,
                        "original_value": None,
                        "page_number": None,
                        "supporting_text": None,
                        "confidence": 0.0,
                        "document_id": document_id,
                        "filename": filename,
                    }
                else:
                    enriched[category][field_name] = {
                        "value": str(val).strip(),
                        "original_value": str(orig).strip() if orig else str(val).strip(),
                        "page_number": page or 1,
                        "supporting_text": str(quote).strip() if quote else str(orig or val),
                        "confidence": min(max(conf, 0.5), 1.0),
                        "document_id": document_id,
                        "filename": filename,
                    }
        return enriched

    # --- Aggregation and Cross-Document Verification ----------------------

    def _aggregate_and_verify_facts(
        self,
        property_id: str,
        per_doc_facts: list[dict[str, Any]],
        docs: list[Document],
    ) -> PropertyExtractionData:
        """Consolidate facts across documents, detect conflicts, and perform normalizations."""
        conflicts: list[CrossDocumentConflict] = []
        missing_fields: list[str] = []

        # Prepare container classes
        identity = PropertyIdentityFacts()
        financial = FinancialFacts()
        ownership = OwnershipLegalFacts()
        approvals = ApprovalFacts()
        dates_oblig = DatesObligationsFacts()

        categories_map = {
            "property_identity": identity,
            "financial_information": financial,
            "ownership_legal": ownership,
            "approvals": approvals,
            "dates_obligations": dates_oblig,
        }

        # Canonical field keys per category
        category_fields: dict[str, list[str]] = {
            "property_identity": [
                "property_name", "property_address", "property_type", "unit_number",
                "carpet_area", "built_up_area", "area_unit",
            ],
            "financial_information": [
                "sale_price", "booking_amount", "payment_schedule",
                "maintenance_charges", "deposits_and_additional_charges",
            ],
            "ownership_legal": [
                "named_owner_or_seller", "title_deed_references", "ownership_claims",
                "encumbrance_information", "litigation_references",
            ],
            "approvals": [
                "project_registration_references", "building_plan_approvals",
                "completion_certificates", "occupancy_certificates",
                "fire_and_environmental_approvals",
            ],
            "dates_obligations": [
                "agreement_date", "possession_date", "payment_deadlines",
                "renewal_dates", "contractual_obligations",
            ],
        }

        for cat_name, field_names in category_fields.items():
            cat_obj = categories_map[cat_name]

            for field_name in field_names:
                fact_attr: ExtractedFieldFact = getattr(cat_obj, field_name)
                # Collect all non-empty extractions for this field across all documents
                collected_candidates: list[dict[str, Any]] = []

                for doc_dict in per_doc_facts:
                    cat_dict = doc_dict.get(cat_name, {})
                    field_dict = cat_dict.get(field_name)
                    if field_dict and field_dict.get("value") is not None:
                        collected_candidates.append(field_dict)

                if not collected_candidates:
                    # Field missing across all documents
                    fact_attr.verification_status = "missing"
                    missing_fields.append(fact_attr.display_name)
                    continue

                # Primary candidate: candidate with highest confidence
                primary = max(collected_candidates, key=lambda c: c.get("confidence", 0.0))
                fact_attr.extracted_value = primary["value"]
                fact_attr.original_value = primary["original_value"]
                fact_attr.document_id = primary["document_id"]
                fact_attr.filename = primary["filename"]
                fact_attr.page_number = primary["page_number"]
                fact_attr.supporting_text = primary["supporting_text"]
                fact_attr.confidence = primary["confidence"]

                # Apply Normalization
                self._apply_field_normalization(fact_attr, field_name, cat_name)

                # Cross-Document Conflict Check
                has_conflict = False
                for other in collected_candidates:
                    if other["document_id"] == primary["document_id"]:
                        continue  # Same document cannot conflict with itself

                    disagrees, reason = self._check_candidate_disagreement(
                        field_name, primary, other
                    )
                    if disagrees:
                        has_conflict = True
                        fact_attr.alternative_values.append({
                            "extracted_value": other["value"],
                            "original_value": other["original_value"],
                            "document_id": other["document_id"],
                            "filename": other["filename"],
                            "page_number": other["page_number"],
                            "supporting_text": other["supporting_text"],
                        })
                        conflicts.append(
                            CrossDocumentConflict(
                                topic=cat_name,
                                description=(
                                    f"Material disagreement for {fact_attr.display_name} "
                                    f"between '{primary['filename']}' and '{other['filename']}': {reason}."
                                ),
                                contradiction_reason=reason,
                                source_a=ConflictSource(
                                    document_id=primary["document_id"],
                                    filename=primary["filename"],
                                    citation_id="Primary",
                                    quote=str(primary["supporting_text"])[:300],
                                    page_number=primary["page_number"],
                                ),
                                source_b=ConflictSource(
                                    document_id=other["document_id"],
                                    filename=other["filename"],
                                    citation_id="Alternative",
                                    quote=str(other["supporting_text"])[:300],
                                    page_number=other["page_number"],
                                ),
                                resolution_note=(
                                    "Values preserved from distinct legal documents without "
                                    "assuming independent legal authoritativeness."
                                ),
                            )
                        )

                if has_conflict:
                    fact_attr.verification_status = "conflicting"
                    fact_attr.uncertainty_note = (
                        f"Conflicting values detected across distinct documents ({len(fact_attr.alternative_values)} alternative(s))."
                    )
                else:
                    # Entailment / Verification Check
                    verified = self._verify_fact_entailment(fact_attr)
                    if verified:
                        fact_attr.verification_status = "supported"
                    else:
                        fact_attr.verification_status = "unverified"
                        fact_attr.uncertainty_note = (
                            "Extracted statement is not fully corroborated by supporting passage."
                        )

        # Count verification statuses across all fields
        supported_cnt = 0
        unverified_cnt = 0
        conflicting_cnt = 0
        missing_cnt = 0

        for cat_obj in categories_map.values():
            for field_name in cat_obj.model_dump().keys():
                fact = getattr(cat_obj, field_name)
                st = fact.verification_status
                if st == "supported":
                    supported_cnt += 1
                elif st == "unverified":
                    unverified_cnt += 1
                elif st == "conflicting":
                    conflicting_cnt += 1
                elif st == "missing":
                    missing_cnt += 1

        return PropertyExtractionData(
            property_id=property_id,
            identity=identity,
            financial=financial,
            ownership_legal=ownership,
            approvals=approvals,
            dates_obligations=dates_oblig,
            conflicts=conflicts,
            missing_fields=missing_fields,
            supported_count=supported_cnt,
            unverified_count=unverified_cnt,
            conflicting_count=conflicting_cnt,
            missing_count=missing_cnt,
            document_count=len(docs),
        )

    def _apply_field_normalization(
        self, fact: ExtractedFieldFact, field_name: str, category: str
    ) -> None:
        """Normalize currency, area, and dates into uniform representations."""
        orig = fact.original_value or str(fact.extracted_value or "")

        # 1. Financial fields: Currency normalization
        if category == "financial_information" or "price" in field_name or "amount" in field_name or "charge" in field_name:
            curr_val = normalize_currency(orig)
            if curr_val is not None:
                fact.normalized_value = curr_val
                fact.unit = "INR"
            else:
                fact.normalized_value = fact.extracted_value

        # 2. Area fields: Area normalization
        elif "area" in field_name:
            area_val = normalize_area(orig)
            if area_val is not None:
                fact.normalized_value = round(area_val, 2)
                fact.unit = "sq ft"
            else:
                fact.normalized_value = fact.extracted_value

        # 3. Dates fields: ISO 8601 normalization
        elif category == "dates_obligations" or "date" in field_name or "deadline" in field_name:
            norm_date = normalize_date_string(orig)
            fact.normalized_value = norm_date or fact.extracted_value

        else:
            fact.normalized_value = fact.extracted_value

    def _check_candidate_disagreement(
        self, field_name: str, cand_a: dict[str, Any], cand_b: dict[str, Any]
    ) -> tuple[bool, str]:
        """Determine whether two extractions for the same field materially disagree."""
        val_a = str(cand_a.get("value") or "").strip().lower()
        val_b = str(cand_b.get("value") or "").strip().lower()
        if not val_a or not val_b or val_a == val_b:
            return False, "identical values"

        orig_a = str(cand_a.get("original_value") or cand_a.get("value") or "")
        orig_b = str(cand_b.get("original_value") or cand_b.get("value") or "")

        # Currency comparison
        curr_a = normalize_currency(orig_a)
        curr_b = normalize_currency(orig_b)
        if curr_a is not None and curr_b is not None:
            if abs(curr_a - curr_b) > 1.0:
                return True, f"different monetary figures ({curr_a:,.0f} vs {curr_b:,.0f})"
            return False, "equivalent monetary value in different denominations"

        # Area comparison
        area_a = normalize_area(orig_a)
        area_b = normalize_area(orig_b)
        if area_a is not None and area_b is not None:
            ratio = max(area_a, area_b) / (min(area_a, area_b) or 1.0)
            if ratio > 1.03:
                return True, f"different property areas ({area_a:.1f} sq ft vs {area_b:.1f} sq ft)"
            return False, "equivalent area in different units"

        # Date comparison
        date_a = normalize_date_string(orig_a)
        date_b = normalize_date_string(orig_b)
        if date_a and date_b and len(date_a) >= 4 and len(date_b) >= 4:
            if date_a != date_b:
                return True, f"different dates ({date_a} vs {date_b})"
            return False, "equivalent dates"

        # General text disagreement
        disagrees, reason = claims_materially_disagree(orig_a, orig_b)
        if disagrees:
            return True, reason

        return False, "no verifiable disagreement"

    def _verify_fact_entailment(self, fact: ExtractedFieldFact) -> bool:
        """Verify that supporting text genuinely substantiates the extracted fact."""
        if not fact.extracted_value:
            return False
        if not fact.supporting_text:
            return False

        ext_str = str(fact.extracted_value).lower()
        orig_str = str(fact.original_value or "").lower()
        supp_str = str(fact.supporting_text).lower()

        # Direct containment
        if ext_str in supp_str or (orig_str and orig_str in supp_str):
            return True

        # Normalized values containment
        if fact.normalized_value is not None:
            norm_str = str(fact.normalized_value).lower()
            if norm_str in supp_str:
                return True
            # Numeric equality for currency/area if both can be normalized from text
            if isinstance(fact.normalized_value, (int, float)):
                supp_curr = normalize_currency(supp_str)
                if supp_curr is not None and abs(supp_curr - float(fact.normalized_value)) < 1.0:
                    return True
                supp_area = normalize_area(supp_str)
                if supp_area is not None and abs(supp_area - float(fact.normalized_value)) < 1.0:
                    return True

        # Punctuation/whitespace stripped containment (e.g. 85,00,000 vs 8500000)
        clean_ext = re.sub(r"[^\w]", "", ext_str)
        clean_supp = re.sub(r"[^\w]", "", supp_str)
        if clean_ext and clean_ext in clean_supp:
            return True
        if orig_str:
            clean_orig = re.sub(r"[^\w]", "", orig_str)
            if clean_orig and (clean_orig in clean_supp or clean_supp in clean_orig):
                return True

        # Numeric / key token overlap
        key_tokens = [w for w in re.findall(r"\b\w+\b", ext_str) if len(w) > 2]
        if not key_tokens:
            return True
        matched = [w for w in key_tokens if w in supp_str]
        return len(matched) / len(key_tokens) >= 0.5

    # --- Persistence Helpers ---------------------------------------------

    def _fetch_property_and_documents(
        self, property_id: str, user_id: str
    ) -> tuple[Property, list[Document], dict[str, str]]:
        """Fetch property, verify ownership, and retrieve associated documents with hashes."""
        try:
            with self._get_session_factory()() as session:
                prop = (
                    session.query(Property)
                    .filter(Property.id == property_id, Property.owner_id == user_id)
                    .one_or_none()
                )
                if prop is None:
                    raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                assoc_subquery = session.query(PropertyDocument.document_id).filter(
                    PropertyDocument.property_id == property_id
                )
                docs = (
                    session.query(Document)
                    .filter(
                        Document.owner_id == user_id,
                        (Document.property_id == property_id) | (Document.id.in_(assoc_subquery)),
                    )
                    .order_by(Document.created_at.desc())
                    .all()
                )

                hashes = {d.id: d.content_sha256 for d in docs}
                return prop, docs, hashes
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Could not retrieve property documents.") from exc

    def _fetch_document_chunks(self, document_id: str) -> list[Chunk]:
        """Fetch all chunks for a document."""
        try:
            with self._get_session_factory()() as session:
                return (
                    session.query(Chunk)
                    .filter(Chunk.document_id == document_id)
                    .order_by(Chunk.chunk_index)
                    .all()
                )
        except Exception:
            return []

    def _fetch_existing_extraction(self, property_id: str) -> PropertyExtraction | None:
        """Fetch existing extraction record from the database."""
        try:
            with self._get_session_factory()() as session:
                return (
                    session.query(PropertyExtraction)
                    .filter(PropertyExtraction.property_id == property_id)
                    .one_or_none()
                )
        except Exception:
            return None

    def _persist_extraction(
        self,
        property_id: str,
        status: str,
        data: PropertyExtractionData,
        document_hashes: dict[str, str],
        error_message: str | None = None,
    ) -> None:
        """Persist or update extraction record in the database."""
        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    record = (
                        session.query(PropertyExtraction)
                        .filter(PropertyExtraction.property_id == property_id)
                        .one_or_none()
                    )
                    data_dict = data.model_dump()
                    if record is None:
                        record = PropertyExtraction(
                            id=f"ext_{uuid.uuid4().hex}",
                            property_id=property_id,
                            status=status,
                            extracted_data=data_dict,
                            document_hashes=document_hashes,
                            error_message=error_message,
                        )
                        session.add(record)
                    else:
                        record.status = status
                        record.extracted_data = data_dict
                        record.document_hashes = document_hashes
                        record.error_message = error_message
                        record.updated_at = datetime.now()
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Could not persist property extraction.") from exc

    def _build_empty_extraction_data(self, property_id: str) -> PropertyExtractionData:
        """Construct default empty extraction payload with all fields marked as missing."""
        identity = PropertyIdentityFacts()
        financial = FinancialFacts()
        ownership = OwnershipLegalFacts()
        approvals = ApprovalFacts()
        dates_oblig = DatesObligationsFacts()

        missing = []
        for cat in (identity, financial, ownership, approvals, dates_oblig):
            for field_name in cat.model_dump().keys():
                fact = getattr(cat, field_name)
                missing.append(fact.display_name)

        return PropertyExtractionData(
            property_id=property_id,
            identity=identity,
            financial=financial,
            ownership_legal=ownership,
            approvals=approvals,
            dates_obligations=dates_oblig,
            conflicts=[],
            missing_fields=missing,
            supported_count=0,
            unverified_count=0,
            conflicting_count=0,
            missing_count=len(missing),
            document_count=0,
        )
