# Property Intelligence and Due Diligence

This document describes property aggregation, legal entity mapping, and due diligence reporting across multi-document portfolios.

## 1. Property-Centric Knowledge Graph

Instead of treating legal deeds, title certificates, tax receipts, and mutation extracts as isolated documents, the platform binds them to a single **Property Record**:

```
                         [ Property Record ]
                                   │
      ┌──────────────────┬─────────┴────────┬──────────────────┐
      ▼                  ▼                  ▼                  ▼
[ Sale Deed ]    [ Encumbrance Cert ] [ Tax Receipts ]  [ Khata / Mutation ]
```

---

## 2. Multi-Document Due Diligence

Legal clearance requires cross-document validation:
1. **Chain of Title**: Ensuring the vendor in document $N$ matches the vendee in document $N-1$.
2. **Encumbrance Check**: Confirming no registered mortgages, bank liens, or legal attachments exist for the active period.
3. **Tax & Revenue Clearance**: Verifying property tax and assessment dues are paid up to date.

---

## 3. Scoped RAG for Properties

When an inquiry is made at the property level:
- Queries target all chunks belonging to documents attached to the target `property_id`.
- The RAG engine combines evidence from multiple document types (e.g. cross-referencing survey number between Sale Deed and Khata certificate) to confirm data consistency.
