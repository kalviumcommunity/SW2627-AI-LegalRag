# Authentication and Security Architecture

This document outlines the security model, token authentication, role-based access control (RBAC), and document-level authorization.

## 1. Security Overview

Property and land legal documents contain sensitive personal and financial data. The platform implements multi-tenant isolation and granular authorization checks before documents can be ingested or queried.

---

## 2. Authentication Flow

- **Bearer JWT Tokens**: Users authenticate via standard JSON Web Tokens signed with HMAC-SHA256 or RS256.
- **Header Format**: `Authorization: Bearer <access_token>`
- **Token Claims**:
  - `sub`: User UUID
  - `role`: Role designation (`admin`, `reviewer`, `buyer`)
  - `exp`: Expiration timestamp

---

## 3. Role-Based Access Control (RBAC)

| Role | Ingest Documents | Delete Documents | Query RAG | View Intelligence Dashboard |
| :--- | :---: | :---: | :---: | :---: |
| **Admin** | Yes | Yes | Yes | Yes |
| **Reviewer / Legal Auditor** | Yes | No | Yes | Yes |
| **Buyer / End User** | No | No | Yes (Scoped) | Yes (Read Only) |

---

## 4. Document-Level Scoping and Tenancy

When executing queries through `POST /api/v1/rag/ask` or `POST /api/v1/retrieval/search`:
- If an unauthorized user attempts to filter by `document_id` or `property_id` outside their tenancy, the database query automatically enforces tenancy scoping:
```sql
WHERE c.document_id IN (
    SELECT id FROM documents WHERE organization_id = :current_user_org_id
)
```
- Raw files uploaded to temporary staging are sanitized with UUIDs and cleaned up immediately after chunking and embedding.
