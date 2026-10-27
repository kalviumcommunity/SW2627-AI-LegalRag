/**
 * TypeScript definitions strictly aligned with FastAPI Pydantic schemas.
 */

export type SourceType = 'pdf' | 'txt' | 'markdown';
export type IngestionStatus = 'processed' | 'ocr_required' | 'failed';
export type EvidenceStatus =
  | 'supported'
  | 'insufficient_evidence'
  | 'conflicting_evidence'
  | 'no_relevant_sources';
export type RetrievalMode = 'semantic' | 'hybrid';

export interface DocumentChunk {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  source_filename: string;
  source_type: SourceType;
  page_number?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  metadata?: Record<string, unknown>;
}

export interface IngestResponse {
  document_id: string;
  filename: string;
  status: IngestionStatus;
  extracted_characters: number;
  chunk_count: number;
  chunks: DocumentChunk[];
  page_count?: number | null;
  warnings: string[];
  detail?: string | null;
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  source_type: SourceType;
  status: IngestionStatus;
  extracted_characters: number;
  chunk_count: number;
  page_count?: number | null;
  warnings: string[];
  detail?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DocumentDetailResponse {
  document_id: string;
  filename: string;
  source_type: SourceType;
  status: IngestionStatus;
  content_sha256: string;
  extracted_characters: number;
  chunk_count: number;
  page_count?: number | null;
  warnings: string[];
  detail?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentChunkSummary {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  source_filename: string;
  source_type: SourceType;
  page_number?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  metadata: Record<string, unknown>;
  text?: string | null;
}

export interface DocumentChunkListResponse {
  document_id: string;
  items: DocumentChunkSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentDeleteResponse {
  document_id: string;
  deleted: boolean;
  message: string;
}

export interface RetrievalFilters {
  source_filename?: string | null;
  source_type?: SourceType | null;
  page_number?: number | null;
}

export interface RAGQuestionRequest {
  question: string;
  top_k?: number | null;
  mode?: RetrievalMode;
  document_id?: string | null;
  filters?: RetrievalFilters;
  min_score?: number | null;
}

export interface RAGCitation {
  citation_id: string; // e.g. "S1", "S2"
  chunk_id: string;
  document_id: string;
  filename: string;
  source?: string | null;
  source_type: SourceType;
  page_number?: number | null;
  page_numbers: number[];
  chunk_index: number;
  excerpt: string;
  document_created_at?: string | null;
}

export interface RAGResponse {
  question: string;
  answer: string;
  evidence_status: EvidenceStatus;
  citations: RAGCitation[];
  limitations: string[];
  retrieved_count: number;
  used_chunk_count: number;
  mode: RetrievalMode;
  citation_guarantee: 'retrieved_source_integrity';
  claim_support_verified: false;
}

export interface ApiErrorDetail {
  detail: string | Array<{ loc?: string[]; msg?: string; type?: string }>;
}
