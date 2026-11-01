import { apiClient } from './client';
import type {
  PropertyRiskAssessmentResponse,
  PropertyRiskAssessmentStatusResponse,
  PropertyRiskFindingResponse,
  PropertyRiskFindingUpdateRequest,
} from './types';

export const riskApi = {
  /**
   * Trigger an evidence-backed property risk assessment.
   */
  async assess(propertyId: string): Promise<PropertyRiskAssessmentResponse> {
    return apiClient<PropertyRiskAssessmentResponse>(
      `/properties/${encodeURIComponent(propertyId)}/risk-assessment`,
      {
        method: 'POST',
        timeoutMs: 90000,
      }
    );
  },

  /**
   * Retrieve the latest risk assessment and findings.
   */
  async getAssessment(propertyId: string): Promise<PropertyRiskAssessmentResponse> {
    return apiClient<PropertyRiskAssessmentResponse>(
      `/properties/${encodeURIComponent(propertyId)}/risk-assessment`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Retrieve lightweight risk assessment status and staleness.
   */
  async getStatus(propertyId: string): Promise<PropertyRiskAssessmentStatusResponse> {
    return apiClient<PropertyRiskAssessmentStatusResponse>(
      `/properties/${encodeURIComponent(propertyId)}/risk-assessment/status`,
      {
        method: 'GET',
      }
    );
  },

  /**
   * Update review status or notes for a finding.
   */
  async updateFinding(
    propertyId: string,
    riskId: string,
    payload: PropertyRiskFindingUpdateRequest
  ): Promise<PropertyRiskFindingResponse> {
    return apiClient<PropertyRiskFindingResponse>(
      `/properties/${encodeURIComponent(propertyId)}/risk-assessment/findings/${encodeURIComponent(riskId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }
    );
  },

  /**
   * Force refresh / reassessment across latest property documents.
   */
  async refresh(propertyId: string): Promise<PropertyRiskAssessmentResponse> {
    return apiClient<PropertyRiskAssessmentResponse>(
      `/properties/${encodeURIComponent(propertyId)}/risk-assessment/refresh`,
      {
        method: 'POST',
        timeoutMs: 90000,
      }
    );
  },
};

