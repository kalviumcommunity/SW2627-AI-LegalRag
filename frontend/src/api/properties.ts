import { apiClient } from './client';
import type {
  PropertyItem,
  PropertyListResponse,
  PropertyExtractionResponse,
  PropertyExtractionStatusResponse,
} from './types';

export const propertiesApi = {
  /**
   * List properties owned by the authenticated user.
   */
  async list(page: number = 1, pageSize: number = 20): Promise<PropertyListResponse> {
    return apiClient<PropertyListResponse>(`/properties?page=${page}&page_size=${pageSize}`, {
      method: 'GET',
    });
  },

  /**
   * Retrieve single property details.
   */
  async get(propertyId: string): Promise<PropertyItem> {
    return apiClient<PropertyItem>(`/properties/${encodeURIComponent(propertyId)}`, {
      method: 'GET',
    });
  },

  /**
   * Create a new property.
   */
  async create(payload: { name: string; address?: string | null }): Promise<PropertyItem> {
    return apiClient<PropertyItem>('/properties', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Trigger structured information extraction across all documents associated with the property.
   */
  async extract(propertyId: string): Promise<PropertyExtractionResponse> {
    return apiClient<PropertyExtractionResponse>(
      `/properties/${encodeURIComponent(propertyId)}/extract`,
      {
        method: 'POST',
        timeoutMs: 90000,
      }
    );
  },

  /**
   * Retrieve extracted property facts and cross-document verification results.
   */
  async getExtraction(propertyId: string): Promise<PropertyExtractionResponse> {
    return apiClient<PropertyExtractionResponse>(
      `/properties/${encodeURIComponent(propertyId)}/extraction`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Retrieve lightweight extraction status and staleness indicator.
   */
  async getExtractionStatus(propertyId: string): Promise<PropertyExtractionStatusResponse> {
    return apiClient<PropertyExtractionStatusResponse>(
      `/properties/${encodeURIComponent(propertyId)}/extraction/status`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Force re-extraction after documents have changed.
   */
  async refreshExtraction(propertyId: string): Promise<PropertyExtractionResponse> {
    return apiClient<PropertyExtractionResponse>(
      `/properties/${encodeURIComponent(propertyId)}/extraction/refresh`,
      {
        method: 'POST',
        timeoutMs: 90000,
      }
    );
  },
};

