import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getApiBaseUrl, apiClient } from '../api/client';
import { documentsApi } from '../api/documents';
import { ragApi } from '../api/rag';

describe('API Client & Contract Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses default API base URL http://localhost:8000/api/v1', () => {
    const url = getApiBaseUrl();
    expect(url).toBe('http://localhost:8000/api/v1');
  });

  it('handles successful JSON response', async () => {
    const mockData = { status: 'healthy', app_name: 'test-app' };
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    } as Response);

    const res = await apiClient<{ status: string }>('/health');
    expect(res).toEqual(mockData);
  });

  it('extracts detail string from HTTP error response', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => JSON.stringify({ detail: 'Document not found.' }),
    } as Response);

    await expect(apiClient('/documents/invalid-id')).rejects.toThrow(
      'Document not found.'
    );
  });

  it('extracts structured detail array from validation errors', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: async () =>
        JSON.stringify({
          detail: [{ msg: 'Field required' }, { msg: 'Value too short' }],
        }),
    } as Response);

    await expect(apiClient('/rag/ask')).rejects.toThrow(
      'Field required, Value too short'
    );
  });

  it('documentsApi.list appends pagination and filter query params', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        items: [],
        total: 0,
        page: 2,
        page_size: 10,
        total_pages: 0,
      }),
    } as Response);

    await documentsApi.list({
      page: 2,
      page_size: 10,
      status: 'processed',
      source_type: 'pdf',
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/documents?page=2&page_size=10&status=processed&source_type=pdf',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('documentsApi.get calls single document endpoint', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ document_id: 'doc-123', filename: 'deed.pdf' }),
    } as Response);

    await documentsApi.get('doc-123');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/documents/doc-123',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('documentsApi.delete issues DELETE request', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ document_id: 'doc-123', deleted: true, message: 'Deleted' }),
    } as Response);

    await documentsApi.delete('doc-123');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/documents/doc-123',
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('ragApi.ask posts JSON payload with question and options', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        question: 'What are the boundaries?',
        answer: 'North boundary is Road 4.',
        evidence_status: 'supported',
        citations: [],
        limitations: [],
        retrieved_count: 5,
        used_chunk_count: 2,
        mode: 'semantic',
        citation_guarantee: 'retrieved_source_integrity',
        claim_support_verified: false,
      }),
    } as Response);

    await ragApi.ask({
      question: 'What are the boundaries?',
      mode: 'semantic',
      top_k: 5,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/rag/ask',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          question: 'What are the boundaries?',
          mode: 'semantic',
          top_k: 5,
        }),
      })
    );
  });
});
