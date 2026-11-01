"""Property management and property-level intelligence service."""

from __future__ import annotations

import math
import re
import threading
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document, Property, PropertyDocument
from app.schemas.documents import DocumentSummary
from app.schemas.properties import (
    ExtractedFact,
    PropertyCreateRequest,
    PropertyDocumentAssociationResponse,
    PropertyDocumentListResponse,
    PropertyIntelligenceResponse,
    PropertyListResponse,
    PropertyProcessingSummary,
    PropertyResponse,
    PropertyUpdateRequest,
)
from app.services.document_store import get_shared_engine
from app.services.evidence_conflict import (
    claims_materially_disagree,
    detect_cross_document_conflicts,
)
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyError,
    PropertyNotFoundError,
    PropertyValidationError,
)
from app.services.storage_errors import DatabaseUnavailableError, DatabaseWriteError


def _new_property_id() -> str:
    return f"prop_{uuid.uuid4().hex}"


class PropertyService:
    """Owner-scoped property lifecycle, document association, and intelligence analysis."""

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

    def create_property(
        self, user_id: str, payload: PropertyCreateRequest
    ) -> PropertyResponse:
        """Create a new property belonging to the authenticated user."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required to create a property.")

        prop_id = _new_property_id()
        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    prop = Property(
                        id=prop_id,
                        owner_id=user_id,
                        name=payload.name,
                        address=payload.address,
                        city=payload.city,
                        state=payload.state,
                        postal_code=payload.postal_code,
                        property_type=payload.property_type,
                        area=payload.area,
                        area_unit=payload.area_unit,
                    )
                    session.add(prop)
                session.refresh(prop)
                return self._to_response(prop, document_count=0)
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Property could not be created.") from exc

    def list_properties(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> PropertyListResponse:
        """List properties belonging to user_id with pagination."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")
        if page < 1 or page_size < 1:
            raise PropertyValidationError("Invalid pagination parameters.")

        offset = (page - 1) * page_size
        try:
            with self._get_session_factory()() as session:
                base_query = session.query(Property).filter(Property.owner_id == user_id)
                total = base_query.count()
                properties = (
                    base_query.order_by(Property.created_at.desc(), Property.id.desc())
                    .offset(offset)
                    .limit(page_size)
                    .all()
                )

                items = []
                for prop in properties:
                    # Count distinct associated documents
                    doc_count = self._count_associated_documents(session, prop.id, user_id)
                    items.append(self._to_response(prop, document_count=doc_count))

                total_pages = math.ceil(total / page_size) if total > 0 else 0
                return PropertyListResponse(
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Properties could not be retrieved.") from exc

    def get_property(self, property_id: str, user_id: str) -> PropertyResponse:
        """Fetch a property belonging to user_id."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                prop = (
                    session.query(Property)
                    .filter(Property.id == property_id, Property.owner_id == user_id)
                    .one_or_none()
                )
                if prop is None:
                    raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                doc_count = self._count_associated_documents(session, prop.id, user_id)
                return self._to_response(prop, document_count=doc_count)
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Property could not be retrieved.") from exc

    def update_property(
        self, property_id: str, user_id: str, payload: PropertyUpdateRequest
    ) -> PropertyResponse:
        """Update property attributes, enforcing owner authorization."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    prop = (
                        session.query(Property)
                        .filter(Property.id == property_id, Property.owner_id == user_id)
                        .one_or_none()
                    )
                    if prop is None:
                        raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                    if payload.name is not None:
                        prop.name = payload.name
                    if payload.address is not None:
                        prop.address = payload.address
                    if payload.city is not None:
                        prop.city = payload.city
                    if payload.state is not None:
                        prop.state = payload.state
                    if payload.postal_code is not None:
                        prop.postal_code = payload.postal_code
                    if payload.property_type is not None:
                        prop.property_type = payload.property_type
                    if payload.area is not None:
                        prop.area = payload.area
                    if payload.area_unit is not None:
                        prop.area_unit = payload.area_unit

                session.refresh(prop)
                doc_count = self._count_associated_documents(session, prop.id, user_id)
                return self._to_response(prop, document_count=doc_count)
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Property could not be updated.") from exc

    def delete_property(self, property_id: str, user_id: str) -> bool:
        """Delete property while preserving associated documents."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    prop = (
                        session.query(Property)
                        .filter(Property.id == property_id, Property.owner_id == user_id)
                        .one_or_none()
                    )
                    if prop is None:
                        raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                    # Documents associated directly have property_id set to NULL by DB FK (SET NULL),
                    # but we also update explicitly for clarity and safety across DB engines.
                    session.query(Document).filter(
                        Document.property_id == property_id
                    ).update({"property_id": None}, synchronize_session=False)

                    # Remove junction records for this property
                    session.query(PropertyDocument).filter(
                        PropertyDocument.property_id == property_id
                    ).delete(synchronize_session=False)

                    session.delete(prop)
                return True
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Property could not be deleted.") from exc

    def get_property_documents(
        self, property_id: str, user_id: str, page: int = 1, page_size: int = 50
    ) -> PropertyDocumentListResponse:
        """List documents associated with a property."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        offset = (page - 1) * page_size
        try:
            with self._get_session_factory()() as session:
                prop = (
                    session.query(Property)
                    .filter(Property.id == property_id, Property.owner_id == user_id)
                    .one_or_none()
                )
                if prop is None:
                    raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                doc_query = self._get_associated_documents_query(session, property_id, user_id)
                total = doc_query.count()
                docs = (
                    doc_query.order_by(Document.created_at.desc(), Document.id.desc())
                    .offset(offset)
                    .limit(page_size)
                    .all()
                )

                items = [
                    DocumentSummary(
                        document_id=d.id,
                        filename=d.filename,
                        source_type=d.source_type,
                        status=d.status,
                        extracted_characters=d.extracted_characters,
                        chunk_count=d.chunk_count,
                        page_count=d.page_count,
                        warnings=list(d.warnings or []),
                        detail=d.detail,
                        owner_id=d.owner_id,
                        property_id=d.property_id or property_id,
                        created_at=d.created_at,
                        updated_at=d.updated_at,
                    )
                    for d in docs
                ]
                return PropertyDocumentListResponse(
                    property_id=property_id,
                    items=items,
                    total=total,
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Property documents could not be listed.") from exc

    def associate_document(
        self, property_id: str, document_id: str, user_id: str
    ) -> PropertyDocumentAssociationResponse:
        """Associate a document with a property, enforcing strict tenant isolation."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    # 1. Verify property exists and is owned by user_id
                    prop = (
                        session.query(Property)
                        .filter(Property.id == property_id, Property.owner_id == user_id)
                        .one_or_none()
                    )
                    if prop is None:
                        raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                    # 2. Verify document exists AND is owned by user_id (IDOR defense)
                    doc = (
                        session.query(Document)
                        .filter(Document.id == document_id)
                        .one_or_none()
                    )
                    if doc is None or doc.owner_id != user_id:
                        raise PropertyAuthorizationError(
                            f"Document '{document_id}' not found or access denied."
                        )

                    # 3. Associate document
                    doc.property_id = property_id

                    # 4. Insert junction record if not present
                    existing_assoc = (
                        session.query(PropertyDocument)
                        .filter(
                            PropertyDocument.property_id == property_id,
                            PropertyDocument.document_id == document_id,
                        )
                        .one_or_none()
                    )
                    if existing_assoc is None:
                        session.add(
                            PropertyDocument(
                                property_id=property_id,
                                document_id=document_id,
                            )
                        )

                return PropertyDocumentAssociationResponse(
                    property_id=property_id,
                    document_id=document_id,
                    associated=True,
                    message=f"Document '{doc.filename}' successfully associated with property '{prop.name}'.",
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Could not associate document with property.") from exc

    def disassociate_document(
        self, property_id: str, document_id: str, user_id: str
    ) -> PropertyDocumentAssociationResponse:
        """Disassociate a document from a property."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                with session.begin():
                    prop = (
                        session.query(Property)
                        .filter(Property.id == property_id, Property.owner_id == user_id)
                        .one_or_none()
                    )
                    if prop is None:
                        raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                    doc = (
                        session.query(Document)
                        .filter(Document.id == document_id)
                        .one_or_none()
                    )
                    if doc is None or doc.owner_id != user_id:
                        raise PropertyAuthorizationError(
                            f"Document '{document_id}' not found or access denied."
                        )

                    # Remove junction record
                    session.query(PropertyDocument).filter(
                        PropertyDocument.property_id == property_id,
                        PropertyDocument.document_id == document_id,
                    ).delete(synchronize_session=False)

                    # If Document.property_id matches this property, update to another or NULL
                    if doc.property_id == property_id:
                        other_assoc = (
                            session.query(PropertyDocument.property_id)
                            .filter(PropertyDocument.document_id == document_id)
                            .first()
                        )
                        doc.property_id = other_assoc[0] if other_assoc else None

                return PropertyDocumentAssociationResponse(
                    property_id=property_id,
                    document_id=document_id,
                    associated=False,
                    message=f"Document '{doc.filename}' disassociated from property '{prop.name}'.",
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Could not disassociate document from property.") from exc

    def get_property_intelligence(
        self, property_id: str, user_id: str
    ) -> PropertyIntelligenceResponse:
        """Consolidate property metadata, documents, verified facts, conflicts, and gaps."""
        if not user_id:
            raise PropertyAuthorizationError("Authentication required.")

        try:
            with self._get_session_factory()() as session:
                # 1. Fetch Property
                prop = (
                    session.query(Property)
                    .filter(Property.id == property_id, Property.owner_id == user_id)
                    .one_or_none()
                )
                if prop is None:
                    raise PropertyNotFoundError(f"Property '{property_id}' not found.")

                # 2. Fetch associated documents
                doc_query = self._get_associated_documents_query(session, property_id, user_id)
                docs = doc_query.order_by(Document.created_at.desc()).all()

                doc_summaries = [
                    DocumentSummary(
                        document_id=d.id,
                        filename=d.filename,
                        source_type=d.source_type,
                        status=d.status,
                        extracted_characters=d.extracted_characters,
                        chunk_count=d.chunk_count,
                        page_count=d.page_count,
                        warnings=list(d.warnings or []),
                        detail=d.detail,
                        owner_id=d.owner_id,
                        property_id=d.property_id or property_id,
                        created_at=d.created_at,
                        updated_at=d.updated_at,
                    )
                    for d in docs
                ]

                # 3. Processing summary
                proc_summary = PropertyProcessingSummary(
                    total_documents=len(docs),
                    processed=sum(1 for d in docs if d.status == "processed"),
                    ocr_required=sum(1 for d in docs if d.status == "ocr_required"),
                    failed=sum(1 for d in docs if d.status == "failed"),
                )

                # 4. Fetch chunks across all associated documents for intelligence extraction
                doc_ids = [d.id for d in docs]
                chunks: list[Chunk] = []
                if doc_ids:
                    chunks = (
                        session.query(Chunk)
                        .filter(Chunk.document_id.in_(doc_ids))
                        .order_by(Chunk.document_id, Chunk.chunk_index)
                        .all()
                    )

                # 5. Extract supported key facts
                verified_facts, citations = self._extract_supported_facts(chunks, docs)

                # 6. Detect cross-document conflicts
                conflicts = self._detect_conflicts_across_chunks(chunks, docs)

                # 7. Identify missing or unverified information
                missing_info = self._identify_missing_information(docs, verified_facts)

                prop_resp = self._to_response(prop, document_count=len(docs))

                return PropertyIntelligenceResponse(
                    property=prop_resp,
                    document_inventory=doc_summaries,
                    document_count=len(docs),
                    processing_summary=proc_summary,
                    verified_facts=verified_facts,
                    cross_document_conflicts=conflicts,
                    unverified_or_missing_information=missing_info,
                    citations=citations,
                )
        except OperationalError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        except PropertyError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseWriteError("Could not generate property intelligence.") from exc

    # --- internal helpers ------------------------------------------------

    @staticmethod
    def _to_response(prop: Property, document_count: int = 0) -> PropertyResponse:
        return PropertyResponse(
            id=prop.id,
            owner_id=prop.owner_id,
            name=prop.name,
            address=prop.address,
            city=prop.city,
            state=prop.state,
            postal_code=prop.postal_code,
            property_type=prop.property_type,
            area=prop.area,
            area_unit=prop.area_unit,
            document_count=document_count,
            created_at=prop.created_at,
            updated_at=prop.updated_at,
        )

    @staticmethod
    def _get_associated_documents_query(
        session: Session, property_id: str, user_id: str
    ):
        assoc_subquery = session.query(PropertyDocument.document_id).filter(
            PropertyDocument.property_id == property_id
        )
        return session.query(Document).filter(
            Document.owner_id == user_id,
            or_(
                Document.property_id == property_id,
                Document.id.in_(assoc_subquery),
            ),
        )

    @staticmethod
    def _count_associated_documents(session: Session, property_id: str, user_id: str) -> int:
        assoc_subquery = session.query(PropertyDocument.document_id).filter(
            PropertyDocument.property_id == property_id
        )
        return (
            session.query(Document)
            .filter(
                Document.owner_id == user_id,
                or_(
                    Document.property_id == property_id,
                    Document.id.in_(assoc_subquery),
                ),
            )
            .count()
        )

    def _extract_supported_facts(
        self, chunks: list[Chunk], docs: list[Document]
    ) -> tuple[list[ExtractedFact], list[dict[str, Any]]]:
        """Extract verified facts supported directly by document chunk text."""
        doc_map = {d.id: d.filename for d in docs}
        facts: list[ExtractedFact] = []
        citations: list[dict[str, Any]] = []

        seen_facts: set[str] = set()
        cit_idx = 1

        # Patterns for factual extraction
        patterns = [
            (
                "ownership",
                re.compile(
                    r"(?:owner|purchaser|vendor|seller|buyer|executed in favor of|conveyed to)\s+[:\-]?\s*([A-Z][A-Za-z\s.,]{3,50})",
                    re.IGNORECASE,
                ),
            ),
            (
                "area",
                re.compile(
                    r"(\b\d+(?:[.,]\d+)?\s*(?:sq(?:uare)?\.?\s*(?:ft|feet|meters|metres|yards)|acres?|gunthas?|cents?)\b)",
                    re.IGNORECASE,
                ),
            ),
            (
                "consideration",
                re.compile(
                    r"(\b(?:Rs\.?|INR|\$)\s*[\d,]+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:lakhs?|crores?|million)\b)",
                    re.IGNORECASE,
                ),
            ),
            (
                "encumbrance",
                re.compile(
                    r"\b(free\s+from\s+all\s+encumbrances|mortgaged\s+to\s+[A-Za-z\s]+|subject\s+to\s+mortgage|no\s+prior\s+lien)\b",
                    re.IGNORECASE,
                ),
            ),
            (
                "approval",
                re.compile(
                    r"\b(sanctioned\s+plan\s+no\.?\s*[A-Za-z0-9\/-]+|building\s+permit\s+no\.?\s*[A-Za-z0-9\/-]+|commencement\s+certificate)\b",
                    re.IGNORECASE,
                ),
            ),
        ]

        for chunk in chunks:
            text = chunk.text
            fn = doc_map.get(chunk.document_id, chunk.source_filename)

            for topic, pat in patterns:
                for match in pat.finditer(text):
                    matched_str = match.group(0).strip()
                    # Clean up and normalize
                    fact_key = f"{topic}:{matched_str.lower()}"
                    if fact_key in seen_facts:
                        continue
                    seen_facts.add(fact_key)

                    cit_label = f"S{cit_idx}"
                    cit_idx += 1

                    fact_obj = ExtractedFact(
                        fact=matched_str,
                        topic=topic,
                        citation_id=cit_label,
                        document_id=chunk.document_id,
                        filename=fn,
                        page_number=chunk.page_number,
                    )
                    facts.append(fact_obj)

                    citations.append(
                        {
                            "citation_id": cit_label,
                            "document_id": chunk.document_id,
                            "filename": fn,
                            "chunk_id": chunk.id,
                            "page_number": chunk.page_number,
                            "excerpt": text[max(0, match.start() - 40) : min(len(text), match.end() + 60)],
                        }
                    )
                    if len(facts) >= 20:
                        break
                if len(facts) >= 20:
                    break
            if len(facts) >= 20:
                break

        return facts, citations

    def _detect_conflicts_across_chunks(
        self, chunks: list[Chunk], docs: list[Document]
    ):
        """Run cross-document conflict detection across chunks of distinct documents."""
        if len(docs) < 2:
            return []

        doc_map = {d.id: d.filename for d in docs}
        # Build mock source objects compatible with detect_cross_document_conflicts
        class _SourceWrapper:
            def __init__(self, ch: Chunk, filename: str, idx: int):
                self.document_id = ch.document_id
                self.text = ch.text
                self.source_id = f"S{idx}"
                self.result = self
                self.metadata = type(
                    "Meta",
                    (),
                    {
                        "filename": filename,
                        "page_number": ch.page_number,
                        "page_numbers": [ch.page_number] if ch.page_number else [],
                    },
                )()

        source_wrappers = [
            _SourceWrapper(ch, doc_map.get(ch.document_id, ch.source_filename), i + 1)
            for i, ch in enumerate(chunks[:40])
        ]

        return detect_cross_document_conflicts(source_wrappers)

    def _identify_missing_information(
        self, docs: list[Document], facts: list[ExtractedFact]
    ) -> list[str]:
        """Identify missing due-diligence records without falsely inferring title clearance."""
        gaps: list[str] = []
        if not docs:
            gaps.append("No documents have been uploaded or associated with this property.")
            gaps.append("A title deed or sale deed is required to determine property ownership.")
            gaps.append("An encumbrance certificate (EC) is missing.")
            return gaps

        filenames_lower = " ".join(d.filename.lower() for d in docs)
        topics_present = {f.topic for f in facts}

        if not any(w in filenames_lower for w in ("encumbrance", "ec", "nil_encumbrance")):
            gaps.append(
                "Encumbrance Certificate (EC) is missing: legal lien status is unverified."
            )
        if not any(w in filenames_lower for w in ("sale_deed", "title_deed", "conveyance", "deed", "ownership")):
            if "ownership" not in topics_present:
                gaps.append(
                    "Primary Title/Sale Deed is not clearly identified among associated documents."
                )
        if not any(w in filenames_lower for w in ("tax", "receipt", "municipal", "property_tax")):
            gaps.append(
                "Property tax receipts or municipal revenue records are missing."
            )
        if not any(w in filenames_lower for w in ("sanction", "approval", "permit", "noc", "occupancy", "khata", "patta")):
            gaps.append(
                "Municipal sanction, building permits, or occupancy records are missing."
            )
        if "area" not in topics_present:
            gaps.append(
                "Survey boundary and precise plot area documentation is incomplete."
            )

        return gaps
