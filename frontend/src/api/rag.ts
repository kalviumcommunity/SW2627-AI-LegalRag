import { apiClient } from './client';
import type { RAGQuestionRequest, RAGResponse } from './types';

export const ragApi = {
  /**
   * Request a grounded answer from retrieved document excerpts with citations.
   */
  async ask(payload: RAGQuestionRequest): Promise<RAGResponse> {
    return apiClient<RAGResponse>('/rag/ask', {
      method: 'POST',
      body: JSON.stringify(payload),
      timeoutMs: 60000,
    });
  },
};
