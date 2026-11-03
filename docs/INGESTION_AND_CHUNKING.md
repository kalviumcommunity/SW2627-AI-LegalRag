# Document Ingestion & Chunking Pipeline

## 1. Overview

The ingestion engine transforms raw legal files (PDF, TXT, MD) into clean, normalized, and semantically segmented chunks suitable for embedding and indexing. In legal documents, preserving clause structure, section breaks, and page references is critical for auditability.

---

## 2. Validation & Security Controls (`document_validation.py`)

Every uploaded file undergoes multi-stage validation before being written to disk:
1. **Filename Validation**: Strips path traversal sequences (`../`, `..\\`) and prevents hidden files.
2. **MIME-Type & Magic Byte Inspection**:
   - PDF: Magic signature `%PDF-` with `application/pdf`.
   - Markdown: `text/markdown` or `text/plain`.
   - Plain Text: Valid UTF-8 byte stream.
3. **Payload Size Limit**: Strict 10MB upper bound per document to prevent memory exhaustion and DoS attacks.
4. **Temporary Storage Isolation**: Uploads are staged in isolated, ephemeral temp files (`temp_storage.py`) with deterministic context manager cleanup upon failure or completion.

---

## 3. Text Extraction (`text_extraction.py`)

- **PDF Extraction**: Uses `pypdf` to extract page-by-page text while recording explicit `page_number` ranges for each extracted segment.
- **Markdown & Plaintext**: Extracts text while preserving code fences and blockquote structures.
- **Normalization & Cleaning (`text_cleaning.py`)**:
  - Replaces non-standard Unicode spaces and line separators.
  - Strips null bytes and non-printable control characters.
  - Retains indentation, paragraph breaks, and punctuation vital to legal clauses.

---

## 4. Boundary-Aware Chunking Strategy (`chunking.py`)

The chunker is designed to prefer natural legal document boundaries before falling back to hard cuts:

### Boundary Hierarchy:
1. **Paragraph Breaks**: `\n[ \t]*\n+` (highest precedence).
2. **Sentence Breaks**: Regex lookbehind `(?<=[.!?])\s+`.
3. **Line Breaks**: Single `\n`.
4. **Whitespace**: Fallback word-level boundary.
5. **Hard Character Cut**: Only applied if no split point exists within the valid candidate range.

### Configuration Specification (`ChunkingConfig`)
| Parameter | Default | Description |
| :--- | :--- | :--- |
| `chunk_size_chars` | `1000` | Target size of each chunk in characters (~200–250 tokens). |
| `overlap_chars` | `200` | Overlap between adjacent chunks to maintain clause context. |
| `min_split_ratio` | `0.5` | Minimum ratio of `chunk_size_chars` before a candidate boundary is chosen. |

### Chunk Traceability Metadata
Every produced chunk is tagged with:
- `chunk_index`: 0-indexed position within document.
- `start_char_offset` / `end_char_offset`: Absolute character slice in the cleaned document text.
- `page_start` / `page_end`: Page boundaries spanning the chunk.
- `token_count`: Estimated or exact token count.
