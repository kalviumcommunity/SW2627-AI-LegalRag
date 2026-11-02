"""Document classification service for real estate documents.

Applies deterministic statutory/legal patterns, heading keywords, and structural
cues with confidence scoring and reasoning. Falls back to LLM assistance when
confidence is low. Never treats uncertain classifications as confirmed legal truth.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.document_intelligence import (
    DocumentClassificationCategory,
    DocumentClassificationResponse,
)
from app.services.llm_service import LLMService

# Deterministic patterns mapping legal document categories to regex signatures
_CLASSIFICATION_RULES: list[dict[str, Any]] = [
    {
        "category": DocumentClassificationCategory.SALE_DEED,
        "primary_patterns": [
            r"\b(?:deed\s+of\s+(?:absolute\s+)?sale|sale\s+deed|conveyance\s+deed)\b",
            r"\b(?:vendor\s+doth\s+hereby\s+grant|absolute\s+owner\s+and\s+vendor|purchaser\s+and\s+vendor)\b",
        ],
        "secondary_patterns": [
            r"\b(?:habendum|schedule\s+of\s+property|consideration\s+paid)\b",
            r"\bsale\b",
        ],
        "reasoning": "Detected definitive Sale Deed / Conveyance preamble, vendor/purchaser covenants, and title transfer habendum.",
    },
    {
        "category": DocumentClassificationCategory.AGREEMENT_TO_SELL,
        "primary_patterns": [
            r"\b(?:agreement\s+(?:for|to)\s+sell|agreement\s+of\s+sale|memorandum\s+of\s+understanding\s+for\s+sale)\b",
            r"\b(?:agrees\s+to\s+sell\s+and\s+the\s+purchaser\s+agrees\s+to\s+purchase)\b",
        ],
        "secondary_patterns": [
            r"\b(?:earnest\s+money|booking\s+advance|balance\s+sale\s+consideration)\b",
        ],
        "reasoning": "Detected Agreement to Sell preamble, mutual agreement to convey, and advance payment covenants.",
    },
    {
        "category": DocumentClassificationCategory.ALLOTMENT_LETTER,
        "primary_patterns": [
            r"\b(?:allotment\s+letter|letter\s+of\s+allotment|provisional\s+allotment\s+letter)\b",
            r"\b(?:allotted\s+(?:the\s+)?(?:apartment|flat|unit|plot))\b",
        ],
        "secondary_patterns": [
            r"\b(?:allottee|promoter|developer|booking\s+reference)\b",
        ],
        "reasoning": "Detected developer Allotment Letter header, allottee designation, and unit allotment clause.",
    },
    {
        "category": DocumentClassificationCategory.ENCUMBRANCE_CERTIFICATE,
        "primary_patterns": [
            r"\b(?:encumbrance\s+certificate|certificate\s+of\s+encumbrance|non[\s-]encumbrance\s+certificate)\b",
            r"\b(?:form\s+no\.?\s*(?:15|16))\b",
        ],
        "secondary_patterns": [
            r"\b(?:sub[\s-]registrar|search\s+period|nil\s+encumbrance)\b",
        ],
        "reasoning": "Detected Sub-Registrar Encumbrance Certificate form reference and search period terminology.",
    },
    {
        "category": DocumentClassificationCategory.OCCUPANCY_CERTIFICATE,
        "primary_patterns": [
            r"\b(?:occupancy\s+certificate|partial\s+occupancy\s+certificate)\b",
            r"\b(?:fit\s+for\s+occupation|permitted\s+to\s+occupy)\b",
        ],
        "secondary_patterns": [
            r"\b(?:municipal\s+corporation|competent\s+authority|building\s+sanction)\b",
        ],
        "reasoning": "Detected statutory Occupancy Certificate issuance from planning authority.",
    },
    {
        "category": DocumentClassificationCategory.COMPLETION_CERTIFICATE,
        "primary_patterns": [
            r"\b(?:completion\s+certificate|building\s+completion\s+certificate)\b",
            r"\b(?:completed\s+according\s+to\s+sanctioned\s+plan)\b",
        ],
        "secondary_patterns": [
            r"\b(?:architect\s+certificate|structural\s+engineer|inspection\s+report)\b",
        ],
        "reasoning": "Detected statutory Building Completion Certificate referencing sanctioned construction completion.",
    },
    {
        "category": DocumentClassificationCategory.BUILDING_PLAN_APPROVAL,
        "primary_patterns": [
            r"\b(?:building\s+plan\s+approval|sanctioned\s+plan|commencement\s+certificate|development\s+permission)\b",
            r"\b(?:sanction\s+order\s+no|ioa\s+approval|intimation\s+of\s+disapproval)\b",
        ],
        "secondary_patterns": [
            r"\b(?:floor\s+space\s+index|fsi|layout\s+sanction)\b",
        ],
        "reasoning": "Detected municipal Building Plan Sanction / Commencement permission identifiers.",
    },
    {
        "category": DocumentClassificationCategory.RERA_REGISTRATION,
        "primary_patterns": [
            r"\b(?:rera\s+registration|real\s+estate\s+regulatory\s+authority)\b",
            r"\b(?:maharera|form\s+['\"]?c['\"]?\s+registration\s+certificate)\b",
            r"\b(?:rera\s+project\s+reg(?:istration)?\s*(?:no|number))\b",
        ],
        "secondary_patterns": [
            r"\b(?:rera\s+act|promoter\s+registration)\b",
        ],
        "reasoning": "Detected state RERA statutory Project Registration Certificate and regulatory authority citations.",
    },
    {
        "category": DocumentClassificationCategory.PROPERTY_TAX_RECEIPT,
        "primary_patterns": [
            r"\b(?:property\s+tax\s+receipt|municipal\s+tax\s+receipt|property\s+tax\s+challan)\b",
            r"\b(?:assessment\s+year|rateable\s+value|property\s+id\s*(?:no|number)?)\b",
        ],
        "secondary_patterns": [
            r"\b(?:ward\s+no|tax\s+paid|rebate|cess)\b",
        ],
        "reasoning": "Detected municipal Property Tax assessment receipt and rateable valuation details.",
    },
    {
        "category": DocumentClassificationCategory.PAYMENT_RECEIPT,
        "primary_patterns": [
            r"\b(?:payment\s+receipt|money\s+receipt|official\s+receipt)\b",
            r"\b(?:received\s+with\s+thanks\s+from|received\s+a\s+sum\s+of\s+rs)\b",
        ],
        "secondary_patterns": [
            r"\b(?:cheque\s+no|demand\s+draft|transaction\s+id|utr\s+no)\b",
        ],
        "reasoning": "Detected acknowledgment of payment transaction, receipt number, and banking transfer reference.",
    },
    {
        "category": DocumentClassificationCategory.LOAN_OR_MORTGAGE,
        "primary_patterns": [
            r"\b(?:mortgage\s+deed|equitable\s+mortgage|simple\s+mortgage|memorandum\s+of\s+deposit\s+of\s+title\s+deeds)\b",
            r"\b(?:home\s+loan\s+agreement|sanction\s+letter\s+for\s+housing\s+loan|hypothecation\s+deed)\b",
        ],
        "secondary_patterns": [
            r"\b(?:mortgagor|mortgagee|borrower|lender|principal\s+sum|equated\s+monthly\s+installment|emi)\b",
        ],
        "reasoning": "Detected Mortgage Deed covenants, lender charge creation, and housing loan security terms.",
    },
    {
        "category": DocumentClassificationCategory.LEGAL_NOTICE,
        "primary_patterns": [
            r"\b(?:legal\s+notice|advocate\s+notice|statutory\s+notice|notice\s+under\s+section\s+\d+)\b",
            r"\b(?:under\s+instructions\s+from\s+my\s+client|call\s+upon\s+you\s+to\s+comply)\b",
        ],
        "secondary_patterns": [
            r"\b(?:failing\s+which\s+legal\s+proceedings|advocate\s+high\s+court)\b",
        ],
        "reasoning": "Detected formal Legal Notice served by an advocate demanding compliance under threat of litigation.",
    },
    {
        "category": DocumentClassificationCategory.LITIGATION_DOCUMENT,
        "primary_patterns": [
            r"\b(?:in\s+the\s+court\s+of|before\s+the\s+hon['\"]?ble|high\s+court\s+of\s+judicature)\b",
            r"\b(?:original\s+suit\s+no|writ\s+petition\s+no|civil\s+suit\s+no|special\s+leave\s+petition)\b",
            r"\b(?:plaintiff\s+versus\s+defendant|petitioner\s+versus\s+respondent)\b",
        ],
        "secondary_patterns": [
            r"\b(?:plaint|written\s+statement|interlocutory\s+application|affidavit|injunction\s+order)\b",
        ],
        "reasoning": "Detected court proceeding cause title, judicial suit number, and adversarial litigation parties.",
    },
    {
        "category": DocumentClassificationCategory.TITLE_DEED,
        "primary_patterns": [
            r"\b(?:title\s+deed|mother\s+deed|link\s+deed|parent\s+deed|root\s+of\s+title)\b",
            r"\b(?:chain\s+of\s+title|original\s+title\s+deeds)\b",
        ],
        "secondary_patterns": [
            r"\b(?:deed\s+of\s+partition|deed\s+of\s+gift|settlement\s+deed|relinquishment\s+deed)\b",
        ],
        "reasoning": "Detected title devolution covenants establishing historic chain of property ownership.",
    },
]


class DocumentClassificationService:
    """Classifies real estate documents using deterministic analysis with optional LLM fallback."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service

    def classify_document(
        self,
        document_id: str,
        text: str,
        filename: str | None = None,
    ) -> DocumentClassificationResponse:
        """Classify document text and filename into a recognized legal category."""
        clean_text = (text or "").strip()
        filename_str = (filename or "").lower()

        # 1. Deterministic classification matching
        match_scores: list[tuple[DocumentClassificationCategory, float, str]] = []

        combined_sample = f"{filename_str}\n{clean_text[:8000]}".lower()

        for rule in _CLASSIFICATION_RULES:
            cat = rule["category"]
            primary_patterns = rule["primary_patterns"]
            secondary_patterns = rule["secondary_patterns"]
            reason = rule["reasoning"]

            primary_hits = sum(1 for p in primary_patterns if re.search(p, combined_sample, re.IGNORECASE))
            secondary_hits = sum(1 for p in secondary_patterns if re.search(p, combined_sample, re.IGNORECASE))

            # Filename bonus
            filename_hit = False
            cat_words = [w.lower() for w in cat.value.split() if len(w) > 3]
            if any(w in filename_str for w in cat_words):
                filename_hit = True

            score = 0.0
            if primary_hits > 0:
                score += 0.65 + min(0.25, primary_hits * 0.12)
            if secondary_hits > 0:
                score += min(0.15, secondary_hits * 0.05)
            if filename_hit:
                score = min(0.98, score + 0.10 if score > 0 else 0.45)

            score = min(0.98, score)

            if score >= 0.50:
                match_scores.append((cat, score, reason))

        # Sort matches by highest confidence score
        match_scores.sort(key=lambda x: x[1], reverse=True)

        if match_scores and match_scores[0][1] >= 0.60:
            top_cat, top_score, top_reason = match_scores[0]
            return DocumentClassificationResponse(
                document_id=document_id,
                category=top_cat.value,
                confidence=round(top_score, 2),
                reasoning=top_reason,
                manually_corrected=False,
                updated_at=datetime.now(timezone.utc),
            )

        # 2. LLM Fallback when confidence is ambiguous (< 0.60) and LLM is available
        if self.llm_service is not None and len(clean_text) > 50:
            llm_result = self._classify_with_llm(document_id, clean_text[:3000], filename)
            if llm_result is not None:
                return llm_result

        # 3. Default to Other / Unknown with clear, non-speculative reasoning
        return DocumentClassificationResponse(
            document_id=document_id,
            category=DocumentClassificationCategory.OTHER_UNKNOWN.value,
            confidence=0.20 if clean_text else 0.0,
            reasoning=(
                "Insufficient legal headings, statutory references, or covenants "
                "detected to classify this document into a standard real estate category."
            ),
            manually_corrected=False,
            updated_at=datetime.now(timezone.utc),
        )

    def _classify_with_llm(
        self,
        document_id: str,
        sample_text: str,
        filename: str | None,
    ) -> DocumentClassificationResponse | None:
        """Query LLM to assist with classifying ambiguous document text."""
        try:
            valid_categories = [c.value for c in DocumentClassificationCategory]
            prompt = (
                f"You are a legal real estate document classifier. Given the following document snippet "
                f"(filename: {filename or 'Unknown'}), select the single best matching category from this list:\n"
                f"{', '.join(valid_categories)}\n\n"
                f"Snippet:\n\"\"\"{sample_text}\"\"\"\n\n"
                f"Respond with ONLY the exact category name and a one-sentence reasoning, formatted as:\n"
                f"Category: <category>\nReasoning: <reasoning>"
            )

            resp = self.llm_service.generate(prompt)
            if not resp or not resp.text:
                return None

            text = resp.text.strip()
            cat_match = re.search(r"Category:\s*([^\n\r]+)", text, re.IGNORECASE)
            reason_match = re.search(r"Reasoning:\s*([^\n\r]+)", text, re.IGNORECASE)

            if cat_match:
                extracted_cat = cat_match.group(1).strip()
                # Find matching enum
                for cat in DocumentClassificationCategory:
                    if cat.value.lower() == extracted_cat.lower():
                        reason = (
                            reason_match.group(1).strip()
                            if reason_match
                            else "Classified via LLM semantic analysis of document clauses."
                        )
                        return DocumentClassificationResponse(
                            document_id=document_id,
                            category=cat.value,
                            confidence=0.75,
                            reasoning=f"LLM Classification: {reason}",
                            manually_corrected=False,
                            updated_at=datetime.now(timezone.utc),
                        )
        except Exception:
            pass
        return None

