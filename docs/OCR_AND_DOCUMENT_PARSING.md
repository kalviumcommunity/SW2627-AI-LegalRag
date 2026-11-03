# OCR, Parsing, and Document Classification

This document outlines the optical character recognition (OCR), table extraction, classification, and duplicate detection pipelines for scanned real estate records.

## 1. Document Parsing Workflow

Real estate documents frequently arrive as low-quality scans, photocopies, or complex multi-column legal deeds. The parsing pipeline utilizes multi-stage processing:

```
Uploaded File ──> File Validation (MIME & Magic Bytes)
               ──> Format Detection (Digital PDF vs Scanned PDF)
               ──> [Digital PDF] ──> PyPDF / pdfplumber extraction
               ──> [Scanned PDF] ──> Tesseract / OCR Engine
               ──> Text Normalization & Cleaning
               ──> Table Structure Extraction
               ──> Layout & Page Boundary Preservation
```

---

## 2. Document Classification

Uploaded files are classified into standard legal document categories:
- `SALE_DEED`: Conveyance deeds, transfer of ownership.
- `ENCUMBRANCE_CERTIFICATE`: Non-encumbrance certificates (Form 15/16).
- `MUTATION_RECORD`: Revenue extracts, Patta/Khata documents.
- `TAX_RECEIPT`: Municipal assessment and tax receipts.
- `BUILDING_PLAN`: Sanctioned floor plans and commencement certificates.

---

## 3. Duplicate and Collision Detection

To prevent redundant embeddings and duplicate vector noise:
- Every document is hashed using SHA-256 upon reception.
- If a hash collision occurs within the same organization or property, the previous document ID is returned idempotently without repeating chunking or embedding.
