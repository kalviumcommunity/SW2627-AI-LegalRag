"""Table extraction service for real estate legal documents.

Parses markdown, pipe-delimited, tab-separated, and structured schedule tables
from document text. Preserves row and column integrity without intermixing values,
retaining page references and original raw text.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.schemas.document_intelligence import ExtractedTable


class TableExtractionService:
    """Extracts and structures tabular records from legal text documents."""

    def extract_tables_from_text(
        self,
        text: str,
        page_number: int | None = None,
    ) -> list[ExtractedTable]:
        """Parse tables from text, recognizing markdown and delimited formats."""
        if not text or not text.strip():
            return []

        tables: list[ExtractedTable] = []

        # 1. Markdown / Pipe-delimited tables: | Col1 | Col2 |
        pipe_tables = self._extract_pipe_tables(text, page_number)
        tables.extend(pipe_tables)

        # 2. Sequential payment schedule tables: e.g. "1. On Booking ... 10% ... Rs. 5,00,000"
        schedule_tables = self._extract_schedule_blocks(text, page_number)
        tables.extend(schedule_tables)

        # 3. Tab or Multi-space aligned tables
        if not tables:
            aligned_tables = self._extract_aligned_tables(text, page_number)
            tables.extend(aligned_tables)

        return tables

    def _extract_pipe_tables(
        self,
        text: str,
        page_number: int | None,
    ) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        lines = text.split("\n")
        current_rows: list[list[str]] = []
        raw_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                # Clean pipe row
                cells = [c.strip() for c in stripped[1:-1].split("|")]
                # Ignore markdown separator line e.g. |---|---|
                if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                    continue
                current_rows.append(cells)
                raw_lines.append(stripped)
            else:
                if len(current_rows) >= 2:
                    tables.append(
                        self._build_table_from_rows(
                            current_rows, raw_lines, page_number
                        )
                    )
                current_rows = []
                raw_lines = []

        if len(current_rows) >= 2:
            tables.append(
                self._build_table_from_rows(current_rows, raw_lines, page_number)
            )

        return tables

    def _extract_schedule_blocks(
        self,
        text: str,
        page_number: int | None,
    ) -> list[ExtractedTable]:
        """Extract multi-row numbered milestone schedules (e.g., payment / construction stages)."""
        tables: list[ExtractedTable] = []
        # Pattern for milestone items: "1. At the time of booking ... 10% ... Rs. 500000"
        item_re = re.compile(
            r"^\s*(?:(?:[0-9]+|[a-z])[\.\)]|\([0-9]+\))\s+(.+?)(?:\s{2,}|\t|:\s+)(.+)$",
            re.MULTILINE,
        )

        matches = list(item_re.finditer(text))
        if len(matches) >= 3:
            # Group into a schedule table
            headers = ["Milestone / Stage", "Percentage / Amount"]
            rows: list[list[str]] = []
            raw_lines: list[str] = []

            for m in matches:
                stage = m.group(1).strip()
                details = m.group(2).strip()
                if stage and details:
                    rows.append([stage, details])
                    raw_lines.append(m.group(0).strip())

            if len(rows) >= 3:
                table_id = f"tbl_{uuid.uuid4().hex[:12]}"
                tables.append(
                    ExtractedTable(
                        table_id=table_id,
                        title="Payment / Milestone Schedule",
                        headers=headers,
                        rows=rows,
                        page_number=page_number,
                        category="payment_schedule",
                        raw_text="\n".join(raw_lines),
                    )
                )

        return tables

    def _extract_aligned_tables(
        self,
        text: str,
        page_number: int | None,
    ) -> list[ExtractedTable]:
        """Extract whitespace-aligned rows with 2+ columns."""
        tables: list[ExtractedTable] = []
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        current_rows: list[list[str]] = []
        raw_lines: list[str] = []
        expected_cols: int | None = None

        for line in lines:
            # Split by 2 or more spaces or tabs
            parts = [p.strip() for p in re.split(r"\t+|\s{3,}", line) if p.strip()]
            if 2 <= len(parts) <= 6:
                if expected_cols is None:
                    expected_cols = len(parts)
                    current_rows.append(parts)
                    raw_lines.append(line)
                elif len(parts) == expected_cols:
                    current_rows.append(parts)
                    raw_lines.append(line)
                else:
                    if len(current_rows) >= 3:
                        tables.append(
                            self._build_table_from_rows(
                                current_rows, raw_lines, page_number
                            )
                        )
                    current_rows = [parts]
                    raw_lines = [line]
                    expected_cols = len(parts)
            else:
                if len(current_rows) >= 3:
                    tables.append(
                        self._build_table_from_rows(
                            current_rows, raw_lines, page_number
                        )
                    )
                current_rows = []
                raw_lines = []
                expected_cols = None

        if len(current_rows) >= 3:
            tables.append(
                self._build_table_from_rows(current_rows, raw_lines, page_number)
            )

        return tables

    def _build_table_from_rows(
        self,
        rows: list[list[str]],
        raw_lines: list[str],
        page_number: int | None,
    ) -> ExtractedTable:
        """Construct an ExtractedTable object, identifying headers and table category."""
        table_id = f"tbl_{uuid.uuid4().hex[:12]}"
        headers = rows[0]
        data_rows = rows[1:]

        # Normalize column counts across rows
        max_cols = max(len(r) for r in rows)
        if len(headers) < max_cols:
            headers = headers + [f"Column {i+1}" for i in range(len(headers), max_cols)]

        normalized_rows: list[list[str]] = []
        for r in data_rows:
            if len(r) < max_cols:
                r = r + [""] * (max_cols - len(r))
            normalized_rows.append(r[:max_cols])

        # Infer category
        category = self._infer_table_category(headers, normalized_rows)
        title = self._infer_table_title(category, headers)

        return ExtractedTable(
            table_id=table_id,
            title=title,
            headers=headers,
            rows=normalized_rows,
            page_number=page_number,
            category=category,
            raw_text="\n".join(raw_lines),
        )

    def _infer_table_category(
        self,
        headers: list[str],
        rows: list[list[str]],
    ) -> str:
        all_text = " ".join(headers + [cell for row in rows for cell in row]).lower()

        if any(w in all_text for w in ("installment", "milestone", "stage of construction", "booking amount", "due date")):
            return "payment_schedule"
        if any(w in all_text for w in ("carpet area", "built-up", "super built", "sq.ft", "sq.mt", "square meters")):
            return "area_measurement"
        if any(w in all_text for w in ("sale consideration", "total price", "base price", "maintenance charges", "stamp duty", "gst")):
            return "financial_consideration"
        if any(w in all_text for w in ("sanction", "approval", "permit", "competent authority", "validity")):
            return "regulatory_approvals"
        return "general"

    def _infer_table_title(self, category: str, headers: list[str]) -> str:
        titles = {
            "payment_schedule": "Payment & Installment Schedule",
            "area_measurement": "Property Area Measurements",
            "financial_consideration": "Financial Terms & Considerations",
            "regulatory_approvals": "Regulatory Approvals & Sanctions",
            "general": f"Table: {headers[0] if headers else 'Data'}",
        }
        return titles.get(category, "Document Table")

