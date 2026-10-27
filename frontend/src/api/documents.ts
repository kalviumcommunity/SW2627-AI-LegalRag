import { apiClient } from './client';
import type {
  DocumentChunkListResponse,
  DocumentDeleteResponse,
  DocumentDetailResponse,
  DocumentListResponse,
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
};
