# Frontend Architecture and UI Component Design

This document describes the modern web user interface built with Vite, React, and TypeScript located in `frontend/`.

## 1. Technology Stack

- **Framework**: React 18 with TypeScript.
- **Build Tool**: Vite for fast hot module replacement (HMR) and optimized bundles.
- **Styling**: Tailwind CSS for responsive and clean UI styling.
- **Icons**: Lucide React for consistent icon design.
- **HTTP Client**: Axios / Fetch API with centralized request interceptors.

---

## 2. Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── DocumentUpload.tsx       # Drag-and-drop document uploader with progress
│   │   ├── PropertyCard.tsx         # Real estate asset overview card
│   │   ├── RagChatWindow.tsx        # Chat interface with inline citations
│   │   ├── CitationPopover.tsx      # Modal / tooltip displaying chunk verification
│   │   ├── RiskBadge.tsx            # Visual risk scoring indicator
│   │   └── DocumentList.tsx         # Paginated document table with delete controls
│   ├── hooks/
│   │   ├── useDocuments.ts          # SWR/custom hook for document lifecycle
│   │   └── useRagQuery.ts           # State machine for RAG inquiry and streaming
│   ├── types/
│   │   └── api.ts                   # Strongly-typed TypeScript interfaces matching backend
│   ├── App.tsx                      # Main application view and layout routing
│   └── main.tsx                     # React DOM root entry point
```

---

## 3. Grounded Citation Rendering

When the backend returns verified answers containing bracketed source identifiers like `[S1]`, `[S2]`:
- The frontend parses the markdown stream or text response.
- Replaces citation tags with interactive badges.
- Clicking or hovering on a citation badge opens the `CitationPopover`, rendering the exact source snippet, file name, and original page number.
