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


// --- Phase 11: Structured Property Extraction Types ---

export type FactVerificationStatus = 'supported' | 'unverified' | 'conflicting' | 'missing';

export interface AlternativeFieldFact {
  extracted_value?: unknown;
  original_value?: string | null;
  document_id?: string | null;
  filename?: string | null;
  page_number?: number | null;
  supporting_text?: string | null;
  confidence?: number;
}

export interface ExtractedFieldFact {
  field_name: string;
  display_name: string;
  extracted_value?: unknown;
  original_value?: string | null;
  normalized_value?: unknown;
  unit?: string | null;
  document_id?: string | null;
  filename?: string | null;
  page_number?: number | null;
  supporting_text?: string | null;
  verification_status: FactVerificationStatus;
  confidence: number;
  uncertainty_note?: string | null;
  alternative_values: AlternativeFieldFact[];
}

export interface PropertyIdentityFacts {
  property_name: ExtractedFieldFact;
  property_address: ExtractedFieldFact;
  property_type: ExtractedFieldFact;
  unit_number: ExtractedFieldFact;
  carpet_area: ExtractedFieldFact;
  built_up_area: ExtractedFieldFact;
  area_unit: ExtractedFieldFact;
}

export interface FinancialFacts {
  sale_price: ExtractedFieldFact;
  booking_amount: ExtractedFieldFact;
  payment_schedule: ExtractedFieldFact;
  maintenance_charges: ExtractedFieldFact;
  deposits_and_additional_charges: ExtractedFieldFact;
}

export interface OwnershipLegalFacts {
  named_owner_or_seller: ExtractedFieldFact;
  title_deed_references: ExtractedFieldFact;
  ownership_claims: ExtractedFieldFact;
  encumbrance_information: ExtractedFieldFact;
  litigation_references: ExtractedFieldFact;
}

export interface ApprovalFacts {
  project_registration_references: ExtractedFieldFact;
  building_plan_approvals: ExtractedFieldFact;
  completion_certificates: ExtractedFieldFact;
  occupancy_certificates: ExtractedFieldFact;
  fire_and_environmental_approvals: ExtractedFieldFact;
}

export interface DatesObligationsFacts {
  agreement_date: ExtractedFieldFact;
  possession_date: ExtractedFieldFact;
  payment_deadlines: ExtractedFieldFact;
  renewal_dates: ExtractedFieldFact;
  contractual_obligations: ExtractedFieldFact;
}

export interface PropertyExtractionData {
  property_id: string;
  identity: PropertyIdentityFacts;
  financial: FinancialFacts;
  ownership_legal: OwnershipLegalFacts;
  approvals: ApprovalFacts;
  dates_obligations: DatesObligationsFacts;
  conflicts: CrossDocumentConflict[];
  missing_fields: string[];
  supported_count: number;
  unverified_count: number;
  conflicting_count: number;
  missing_count: number;
  document_count: number;
}

export interface PropertyExtractionResponse {
  property_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'stale';
  data: PropertyExtractionData;
  document_count: number;
  is_stale: boolean;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PropertyExtractionStatusResponse {
  property_id: string;
  status: 'not_started' | 'pending' | 'in_progress' | 'completed' | 'failed' | 'stale';
  document_count: number;
  is_stale: boolean;
  last_extracted_at?: string | null;
}

export interface PropertyItem {
  id: string;
  name: string;
  address?: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface PropertyListResponse {
  items: PropertyItem[];
  total: number;
  page: number;
  page_size: number;
}


// --- Phase 12: Property Risk Assessment & Due Diligence Types ---

export type RiskCategory =
  | 'ownership_title'
  | 'regulatory_approval'
  | 'financial'
  | 'property_identity'
  | 'legal_dispute'
  | 'documentation_completeness';

export type RiskSeverity = 'critical' | 'high' | 'medium' | 'low' | 'informational';

export type RiskFindingStatus = 'open' | 'under_review' | 'resolved' | 'dismissed';

export interface RiskEvidenceItem {
  document_id?: string | null;
  filename?: string | null;
  page_number?: number | null;
  supporting_text?: string | null;
  fact_field?: string | null;
  verification_status?: string | null;
  original_value?: string | null;
}

export interface PropertyRiskFindingResponse {
  risk_id: string;
  property_id: string;
  rule_key: string;
  category: RiskCategory;
  severity: RiskSeverity;
  status: RiskFindingStatus;
  title: string;
  description: string;
  reason: string;
  recommended_action: string;
  evidence: RiskEvidenceItem[];
  affected_facts: string[];
  user_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PropertyRiskFindingUpdateRequest {
  status: RiskFindingStatus;
  user_notes?: string | null;
}

export interface PropertyRiskAssessmentSummary {
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  informational_count: number;
  open_count: number;
  under_review_count: number;
  resolved_count: number;
  dismissed_count: number;
}

export interface PropertyRiskAssessmentResponse {
  assessment_id: string;
  property_id: string;
  status: 'completed' | 'pending' | 'failed' | 'stale';
  summary: PropertyRiskAssessmentSummary;
  findings: PropertyRiskFindingResponse[];
  document_count: number;
  is_stale: boolean;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  disclaimer?: string;
}

export interface PropertyRiskAssessmentStatusResponse {
  property_id: string;
  status: 'not_started' | 'pending' | 'completed' | 'failed' | 'stale';
  total_findings: number;
  critical_count: number;
  high_count: number;
  is_stale: boolean;
  last_assessed_at?: string | null;
}
