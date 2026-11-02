import { apiClient, getApiBaseUrl, getAuthToken } from './client';
import type {
  PropertyItem,
  PropertyListResponse,
  PropertyDocumentAssociationResponse,
  PropertyDocumentListResponse,
  PropertyExtractionResponse,
  PropertyExtractionStatusResponse,
  PortfolioStatsResponse,
  PropertyActivityResponse,
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

  /**
   * Retrieve portfolio-level statistics across all owned properties.
   */
  async getPortfolioStats(): Promise<PortfolioStatsResponse> {
    return apiClient<PortfolioStatsResponse>('/properties/portfolio/stats', {
      method: 'GET',
    });
  },

  /**
   * Retrieve chronological activity timeline for a property.
   */
  async getActivity(propertyId: string): Promise<PropertyActivityResponse> {
    return apiClient<PropertyActivityResponse>(
      `/properties/${encodeURIComponent(propertyId)}/activity`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Download evidence-backed due diligence PDF report.
   */
  async downloadReportPdf(propertyId: string, propertyName: string): Promise<void> {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}/properties/${encodeURIComponent(propertyId)}/report/pdf`;
    const token = getAuthToken();
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!response.ok) {
      let detail = `Failed to download report (HTTP ${response.status})`;
      try {
        const json = await response.json();
        if (json.detail) detail = json.detail;
      } catch {
        // use default
      }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const sanitizedName = propertyName.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    a.download = `due_diligence_report_${sanitizedName}_${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(downloadUrl);
  },
  /**
   * List documents associated with a property.
   */
  async getDocuments(
    propertyId: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<PropertyDocumentListResponse> {
    return apiClient<PropertyDocumentListResponse>(
      `/properties/${encodeURIComponent(propertyId)}/documents?page=${page}&page_size=${pageSize}`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Associate a document with a property.
   */
  async associateDocument(
    propertyId: string,
    documentId: string
  ): Promise<PropertyDocumentAssociationResponse> {
    return apiClient<PropertyDocumentAssociationResponse>(
      `/properties/${encodeURIComponent(propertyId)}/documents/${encodeURIComponent(documentId)}/associate`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Disassociate a document from a property.
   */
  async disassociateDocument(
    propertyId: string,
    documentId: string
  ): Promise<PropertyDocumentAssociationResponse> {
    return apiClient<PropertyDocumentAssociationResponse>(
      `/properties/${encodeURIComponent(propertyId)}/documents/${encodeURIComponent(documentId)}/disassociate`,
      {
        method: 'POST',
      }
    );
  },
};