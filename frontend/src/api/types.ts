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
  owner_id?: string;
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
  owner_id?: string;
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

export type ClaimVerificationStatus =
  | 'supported'
  | 'unsupported'
  | 'contradicted'
  | 'unestablished';

export interface ClaimVerification {
  claim_text: string;
  status: ClaimVerificationStatus;
  cited_source_ids: string[];
  entailment_explanation: string;
  source_quotes: string[];
}

export interface ConflictSource {
  citation_id: string;
  document_id: string;
  filename: string;
  page_number?: number | null;
  quote: string;
}

export interface CrossDocumentConflict {
  source_a: ConflictSource;
  source_b: ConflictSource;
  contradiction_reason: string;
  resolution_note: string;
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
  citation_guarantee?: string;
  claim_support_verified: boolean;
  claim_verifications?: ClaimVerification[];
  conflicts?: CrossDocumentConflict[];
  insufficient_reasons?: string[];
  legal_disclaimer?: string;
}

export interface ApiErrorDetail {
  detail: string | Array<{ loc?: string[]; msg?: string; type?: string }>;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface UserRegisterRequest {
  email: string;
  password: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}
