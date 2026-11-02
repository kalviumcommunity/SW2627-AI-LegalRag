import { apiClient } from './client';
import type {
  DocumentChunkListResponse,
  DocumentClassificationCategory,
  DocumentClassificationResponse,
  DocumentDeleteResponse,
  DocumentDetailResponse,
  DocumentDuplicatesResponse,
  DocumentListResponse,
  DocumentProcessingStatusResponse,
  ExtractedTablesResponse,
  IngestResponse,
  IngestionStatus,
  SourceType,
} from './types';

export interface ListDocumentsParams {
  page?: number;
  page_size?: number;
  status?: IngestionStatus;
  source_type?: SourceType;
}

export interface ListChunksParams {
  page?: number;
  page_size?: number;
  include_text?: boolean;
}

export const documentsApi = {
  /**
   * Upload, chunk, embed, and persist a property document.
   */
  async ingest(file: File): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient<IngestResponse>('/documents/ingest', {
      method: 'POST',
      body: formData,
      timeoutMs: 60000, // Document embedding can take a moment
    });
  },

  /**
   * List ingested documents with pagination and optional filters.
   */
  async list(params: ListDocumentsParams = {}): Promise<DocumentListResponse> {
    const query = new URLSearchParams();
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
    if (params.status) query.set('status', params.status);
    if (params.source_type) query.set('source_type', params.source_type);

    const queryString = query.toString();
    const endpoint = queryString ? `/documents?${queryString}` : '/documents';
    return apiClient<DocumentListResponse>(endpoint, { method: 'GET' });
  },

  /**
   * Retrieve document metadata and processing status.
   */
  async get(documentId: string): Promise<DocumentDetailResponse> {
    return apiClient<DocumentDetailResponse>(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'GET',
    });
  },

  /**
   * Retrieve paginated chunk metadata for inspection.
   */
  async getChunks(
    documentId: string,
    params: ListChunksParams = {}
  ): Promise<DocumentChunkListResponse> {
    const query = new URLSearchParams();
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
    if (params.include_text !== undefined) query.set('include_text', String(params.include_text));

    const queryString = query.toString();
    const endpoint = `/documents/${encodeURIComponent(documentId)}/chunks${
      queryString ? `?${queryString}` : ''
    }`;
    return apiClient<DocumentChunkListResponse>(endpoint, { method: 'GET' });
  },

  /**
   * Delete a document and its cascading chunks/embeddings.
   */
  async delete(documentId: string): Promise<DocumentDeleteResponse> {
    return apiClient<DocumentDeleteResponse>(`/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
    });
  },

  /**
   * Re-process a document through the advanced ingestion pipeline (OCR, classification, tables).
   */
  async reprocess(documentId: string): Promise<IngestResponse> {
    return apiClient<IngestResponse>(`/documents/${encodeURIComponent(documentId)}/process`, {
      method: 'POST',
      timeoutMs: 60000,
    });
  },

  /**
   * Retrieve document processing, OCR, and extraction status.
   */
  async getProcessingStatus(documentId: string): Promise<DocumentProcessingStatusResponse> {
    return apiClient<DocumentProcessingStatusResponse>(
      `/documents/${encodeURIComponent(documentId)}/processing-status`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve document classification and deterministic reasoning.
   */
  async getClassification(documentId: string): Promise<DocumentClassificationResponse> {
    return apiClient<DocumentClassificationResponse>(
      `/documents/${encodeURIComponent(documentId)}/classification`,
      { method: 'GET' }
    );
  },

  /**
   * Manually correct a document classification category.
   */
  async updateClassification(
    documentId: string,
    category: DocumentClassificationCategory
  ): Promise<DocumentClassificationResponse> {
    return apiClient<DocumentClassificationResponse>(
      `/documents/${encodeURIComponent(documentId)}/classification`,
      {
        method: 'PATCH',
        body: JSON.stringify({ category }),
      }
    );
  },

  /**
   * Retrieve extracted structured tables with row/header provenance.
   */
  async getTables(documentId: string): Promise<ExtractedTablesResponse> {
    return apiClient<ExtractedTablesResponse>(
      `/documents/${encodeURIComponent(documentId)}/tables`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve exact or near-duplicate matches for a document.
   */
  async getDuplicates(documentId: string): Promise<DocumentDuplicatesResponse> {
    return apiClient<DocumentDuplicatesResponse>(
      `/documents/${encodeURIComponent(documentId)}/duplicates`,
      { method: 'GET' }
    );
  },
};
