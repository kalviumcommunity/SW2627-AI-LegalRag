# Grounded RAG Pipeline and Verification

This document specifies the Grounded RAG Pipeline implementation (`app/api/routes/rag.py` and `app/core/rag_prompt.py`) engineered to eliminate hallucinations in property legal queries.

## 1. Principles of Grounded Generation

In legal and property intelligence, ungrounded extrapolation can lead to severe liability. The system enforces three core rules:
1. **Source Delimitation**: Retrieved documents are injected into the context window wrapped in unique nonce tags (e.g., `<<<SOURCE:S1>>>...<<<END_SOURCE:S1>>>`).
2. **Mandatory Citations**: The model is forbidden from stating any property fact without an explicit bracketed citation (e.g., `[S1]`, `[S2]`).
3. **Explicit Refusal**: If evidence is insufficient, contradictory, or absent, the model explicitly outputs status codes: `insufficient_evidence`, `conflicting_evidence`, or `no_relevant_sources`.

---

## 2. Pipeline Flow

```
User Query + Scope (Property / Document)
                  │
                  ▼
         Retrieval Service
  (Dense Semantic + Lexical FTS via RRF)
                  │
                  ▼
         Evidence Filtering
 (Remove chunks below threshold / deduplicate)
                  │
                  ▼
      Prompt Construction with Nonce Tags
                  │
                  ▼
          Groq LLM Generation
                  │
                  ▼
       Post-Generation Validation
 (Verify cited IDs exist in retrieved chunk list)
                  │
                  ▼
       Structured Response with Citations
```

---

## 3. Evidence Status Outcomes

- **`supported`**: The query is directly and completely answered by the retrieved passages, with valid citation tags for each claim.
- **`insufficient_evidence`**: Partial information exists, but critical legal clauses (e.g. indemnity, mutation status) are missing.
- **`conflicting_evidence`**: Retrieved chunks show contradicting information across different document versions.
- **`no_relevant_sources`**: No retrieved chunks passed the relevance threshold.
