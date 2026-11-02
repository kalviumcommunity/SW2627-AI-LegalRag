"""Due Diligence PDF Report Generation Service using ReportLab."""

from __future__ import annotations

import io
import threading
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
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
from app.services.document_store import get_shared_engine
from app.services.property_errors import (
    PropertyAuthorizationError,
    PropertyNotFoundError,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y' and footer disclaimer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[Any] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header running line on pages > 1
        if self._pageNumber > 1:
            self.drawString(36, 756, "SW2627-AI-LegalRag — Automated Property Due Diligence Report")
            self.drawRightString(letter[0] - 36, 756, f"Ref: Confidential Property Analysis")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 750, letter[0] - 36, 750)

        # Footer running line on all pages
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 40, letter[0] - 36, 40)

        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 28, "CONFIDENTIAL — STRICTLY INFORMATIONAL (NOT A LEGAL TITLE CLEARANCE CERTIFICATE)")
        self.drawRightString(letter[0] - 36, 28, page_str)
        self.restoreState()


class DueDiligenceReportService:
    """Generates evidence-backed, comprehensive Due Diligence PDF reports for authorized properties."""

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

    def generate_pdf_report(self, property_id: str, user_id: str) -> bytes:
        """Fetch persisted property intelligence and build a multi-page due diligence PDF document."""
        factory = self._get_session_factory()
        with factory() as session:
            # 1. Authorize property ownership
            prop = session.get(Property, property_id)
            if prop is None:
                raise PropertyNotFoundError(f"Property with ID '{property_id}' was not found.")
            if prop.owner_id != user_id:
                raise PropertyAuthorizationError("You do not have permission to export reports for this property.")

            # 2. Retrieve associated documents
            doc_assoc_stmt = (
                select(Document)
                .join(PropertyDocument, PropertyDocument.document_id == Document.id)
                .where(PropertyDocument.property_id == property_id)
                .order_by(Document.created_at.desc())
            )
            documents = list(session.scalars(doc_assoc_stmt).all())

            # 3. Retrieve extraction data
            extraction_stmt = select(PropertyExtraction).where(PropertyExtraction.property_id == property_id)
            extraction_record = session.scalars(extraction_stmt).first()
            extraction_data = extraction_record.extracted_data if extraction_record else {}

            # 4. Retrieve risk assessment and findings
            assess_stmt = select(PropertyRiskAssessment).where(PropertyRiskAssessment.property_id == property_id)
            assessment_record = session.scalars(assess_stmt).first()
            assessment_summary = assessment_record.summary if assessment_record else {}

            findings_stmt = (
                select(PropertyRiskFinding)
                .where(PropertyRiskFinding.property_id == property_id)
                .order_by(
                    # Order by severity priority
                    PropertyRiskFinding.severity.desc(),
                    PropertyRiskFinding.created_at.desc(),
                )
            )
            findings = list(session.scalars(findings_stmt).all())

        # Build Flowable Story
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=45,
            bottomMargin=45,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12,
        )
        h2_style = ParagraphStyle(
            "SectionH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155"),
        )
        body_bold = ParagraphStyle(
            "ReportBodyBold",
            parent=body_style,
            fontName="Helvetica-Bold",
        )
        table_hdr_style = ParagraphStyle(
            "TableHdr",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=body_style,
            fontSize=7.5,
            leading=10,
        )

        story: list[Any] = []

        # --- 1. Header Banner ---
        gen_time = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        story.append(Paragraph("PROPERTY DUE DILIGENCE & INTELLIGENCE REPORT", title_style))
        story.append(
            Paragraph(
                f"Generated for <b>{prop.name}</b> &bull; Report ID: <font name='Courier'>{prop.id}</font> &bull; Timestamp: {gen_time}",
                subtitle_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#7C3AED"), spaceAfter=10))

        # --- 2. Executive Overview & Metadata ---
        meta_data = [
            [
                Paragraph("<b>Property Name:</b>", body_style),
                Paragraph(prop.name, body_style),
                Paragraph("<b>Property Type:</b>", body_style),
                Paragraph(prop.property_type or "Residential", body_style),
            ],
            [
                Paragraph("<b>Address:</b>", body_style),
                Paragraph(prop.address or "Address not specified", body_style),
                Paragraph("<b>Associated Documents:</b>", body_style),
                Paragraph(f"{len(documents)} document(s)", body_style),
            ],
            [
                Paragraph("<b>Assessment Status:</b>", body_style),
                Paragraph(
                    f"<b>{(assessment_record.status.upper() if assessment_record else 'NOT RUN')}</b>",
                    body_style,
                ),
                Paragraph("<b>Open Risk Findings:</b>", body_style),
                Paragraph(
                    f"<b>{assessment_summary.get('open_count', 0)}</b> (Critical: {assessment_summary.get('critical_count', 0)}, High: {assessment_summary.get('high_count', 0)})",
                    body_style,
                ),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[105, 165, 110, 160])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # --- 3. Document Inventory & Processing Status ---
        story.append(Paragraph("1. Document Inventory & Classification", h2_style))
        if not documents:
            story.append(Paragraph("<i>No documents associated with this property.</i>", body_style))
        else:
            doc_rows = [[
                Paragraph("Document Filename", table_hdr_style),
                Paragraph("Category", table_hdr_style),
                Paragraph("Pages", table_hdr_style),
                Paragraph("OCR / Ingestion", table_hdr_style),
                Paragraph("Characters", table_hdr_style),
            ]]
            for d in documents:
                ocr_str = d.ocr_status or d.status
                doc_rows.append([
                    Paragraph(f"<b>{d.filename}</b>", table_cell_style),
                    Paragraph(d.classification_category or "Other / Unknown", table_cell_style),
                    Paragraph(str(d.page_count or d.ocr_page_count or 1), table_cell_style),
                    Paragraph(ocr_str.upper(), table_cell_style),
                    Paragraph(f"{d.extracted_characters:,}", table_cell_style),
                ])
            doc_table = Table(doc_rows, colWidths=[180, 140, 50, 90, 80])
            doc_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(doc_table)
        story.append(Spacer(1, 10))

        # --- 4. Extracted Structured Property Information ---
        story.append(Paragraph("2. Extracted Property Facts & Verification Status", h2_style))
        supported_facts = extraction_data.get("supported_facts") or []
        if not supported_facts:
            story.append(Paragraph("<i>No structured property facts currently extracted. Run extraction to populate.</i>", body_style))
        else:
            fact_rows = [[
                Paragraph("Category / Field", table_hdr_style),
                Paragraph("Extracted Value", table_hdr_style),
                Paragraph("Status", table_hdr_style),
                Paragraph("Source Document & Page", table_hdr_style),
            ]]
            for fact in supported_facts[:25]:  # Bounded to top facts for report brevity
                category = fact.get("category", "").replace("_", " ").title()
                field_name = fact.get("field_name", "").replace("_", " ").title()
                val = str(fact.get("extracted_value") or "—")
                status = fact.get("verification_status", "unverified").upper()

                src_doc = fact.get("source_document_filename") or fact.get("source_document_id") or "Document"
                page = fact.get("source_page_number")
                page_str = f"Page {page}" if page else "Page —"
                citation = f"{src_doc} ({page_str})"

                fact_rows.append([
                    Paragraph(f"<b>{field_name}</b><br/><font color='#64748B'>{category}</font>", table_cell_style),
                    Paragraph(val, table_cell_style),
                    Paragraph(f"<b>{status}</b>", table_cell_style),
                    Paragraph(citation, table_cell_style),
                ])
            fact_table = Table(fact_rows, colWidths=[130, 160, 80, 170])
            fact_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(fact_table)
        story.append(Spacer(1, 10))

        # --- 5. Risk Assessment Findings Matrix ---
        story.append(Paragraph("3. Due Diligence Risk Findings Matrix", h2_style))
        if not findings:
            story.append(Paragraph("<i>No risk findings identified for this property.</i>", body_style))
        else:
            risk_rows = [[
                Paragraph("Severity", table_hdr_style),
                Paragraph("Finding Title & Category", table_hdr_style),
                Paragraph("Status", table_hdr_style),
                Paragraph("Rationale & Evidence", table_hdr_style),
                Paragraph("Recommended Due Diligence Action", table_hdr_style),
            ]]
            for f in findings:
                sev_color = {
                    "critical": "#DC2626",
                    "high": "#EA580C",
                    "medium": "#D97706",
                    "low": "#2563EB",
                    "informational": "#475569",
                }.get(f.severity.lower(), "#0F172A")

                risk_rows.append([
                    Paragraph(f"<font color='{sev_color}'><b>{f.severity.upper()}</b></font>", table_cell_style),
                    Paragraph(f"<b>{f.title}</b><br/><font color='#64748B'>{f.category.replace('_', ' ').title()}</font>", table_cell_style),
                    Paragraph(f.status.upper(), table_cell_style),
                    Paragraph(f.reason[:250] + ("..." if len(f.reason) > 250 else ""), table_cell_style),
                    Paragraph(f.recommended_action[:250] + ("..." if len(f.recommended_action) > 250 else ""), table_cell_style),
                ])
            risk_table = Table(risk_rows, colWidths=[65, 125, 60, 150, 140])
            risk_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(risk_table)
        story.append(Spacer(1, 10))

        # --- 6. Cross-Document Conflicts ---
        conflicts = extraction_data.get("conflicts") or []
        story.append(Paragraph("4. Cross-Document Conflicts & Inconsistencies", h2_style))
        if not conflicts:
            story.append(Paragraph("<i>No contradictory statements detected across uploaded documents.</i>", body_style))
        else:
            for i, c in enumerate(conflicts, 1):
                reason = c.get("contradiction_reason", "Material discrepancy")
                sa = c.get("source_a", {})
                sb = c.get("source_b", {})
                c_data = [
                    [
                        Paragraph(f"<b>Conflict #{i}: {reason}</b>", body_bold),
                        Paragraph("", body_style),
                    ],
                    [
                        Paragraph(
                            f"<b>Document A:</b> {sa.get('filename', 'Doc A')} (Page {sa.get('page_number', '—')})<br/>"
                            f"<i>&ldquo;{sa.get('quote', '—')}&rdquo;</i>",
                            body_style,
                        ),
                        Paragraph(
                            f"<b>Document B:</b> {sb.get('filename', 'Doc B')} (Page {sb.get('page_number', '—')})<br/>"
                            f"<i>&ldquo;{sb.get('quote', '—')}&rdquo;</i>",
                            body_style,
                        ),
                    ],
                ]
                c_tbl = Table(c_data, colWidths=[270, 270])
                c_tbl.setStyle(
                    TableStyle([
                        ("SPAN", (0, 0), (1, 0)),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF2F2")),
                        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FFF7ED")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#FCA5A5")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FECACA")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ])
                )
                story.append(c_tbl)
                story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

        # --- 7. Due Diligence Gap Checklist ---
        missing_fields = extraction_data.get("missing_fields") or []
        story.append(Paragraph("5. Due Diligence Gap Checklist (Missing Information)", h2_style))
        if not missing_fields:
            story.append(Paragraph("<i>Standard statutory approval fields and core facts are present.</i>", body_style))
        else:
            chk_rows = [[
                Paragraph("Status", table_hdr_style),
                Paragraph("Diligence Checklist Item", table_hdr_style),
                Paragraph("Note / Applicability", table_hdr_style),
            ]]
            for mf in missing_fields:
                chk_rows.append([
                    Paragraph("<font color='#D97706'><b>MISSING</b></font>", table_cell_style),
                    Paragraph(f"<b>{mf}</b>", table_cell_style),
                    Paragraph("Not found in associated property documents. Verification with developer or title authority recommended.", table_cell_style),
                ])
            chk_tbl = Table(chk_rows, colWidths=[70, 200, 270])
            chk_tbl.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(chk_tbl)
        story.append(Spacer(1, 14))

        # --- 8. Mandatory Due Diligence Legal Disclaimer ---
        disclaimer_text = (
            "<b>IMPORTANT STATUTORY & DUE DILIGENCE DISCLAIMER:</b><br/>"
            "This document is an automated property intelligence summary generated exclusively for preliminary due diligence and "
            "informational review. <b>THIS IS NOT A FORMAL LEGAL OPINION, TITLE INSURANCE GUARANTEE, OR CERTIFICATE OF CLEAR TITLE.</b> "
            "Neither the SW2627-AI-LegalRag platform nor its operators warrant that the property is legally marketable, unencumbered, "
            "or free from disputes. Real estate purchases, leases, and loans must always be independently investigated and verified "
            "by a licensed attorney or advocate with local registrar records."
        )
        disc_p = Paragraph(disclaimer_text, body_style)
        disc_table = Table([[disc_p]], colWidths=[540])
        disc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#DC2626")),
                ("TOPPADDING", (0, 0), (0, 0), 8),
                ("BOTTOMPADDING", (0, 0), (0, 0), 8),
                ("LEFTPADDING", (0, 0), (0, 0), 10),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ])
        )
        story.append(KeepTogether([disc_table]))

        # Build document with custom canvas
        doc.build(story, canvasmaker=NumberedCanvas)
        return buf.getvalue()

