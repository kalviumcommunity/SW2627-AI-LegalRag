import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PortfolioDashboard } from '../components/dashboard/PortfolioDashboard';
import { DueDiligenceChecklist } from '../components/property/DueDiligenceChecklist';
import { EvidenceExplorer } from '../components/property/EvidenceExplorer';
import { ActivityTimeline } from '../components/property/ActivityTimeline';
import { propertiesApi } from '../api/properties';
import type {
  PortfolioStatsResponse,
  PropertyExtractionResponse,
  PropertyRiskAssessmentResponse,
} from '../api/types';

describe('Phase 14: Portfolio Intelligence & Due Diligence Frontend Tests', () => {
  const mockPortfolioStats: PortfolioStatsResponse = {
    total_properties: 3,
    total_documents: 8,
    processed_documents: 6,
    ocr_or_review_documents: 2,
    pending_assessment_properties: 1,
    critical_findings_count: 2,
    high_findings_count: 1,
    open_findings_count: 3,
    resolved_findings_count: 4,
    properties_requiring_attention: [
      {
        property_id: 'prop-attn-1',
        property_name: 'Skyline Palms',
        reasons: ['2 critical open finding(s)', 'Document(s) require manual review or failed OCR'],
        critical_count: 2,
        high_count: 0,
        has_failed_ocr: true,
        is_assessment_stale: false,
      },
      {
        property_id: 'prop-attn-2',
        property_name: 'Green Meadows',
        reasons: ['1 high severity open finding(s)', 'Risk assessment is stale (documents updated)'],
        critical_count: 0,
        high_count: 1,
        has_failed_ocr: false,
        is_assessment_stale: true,
      },
    ],
  };

  const mockExtraction: PropertyExtractionResponse = {
    property_id: 'prop-123',
    status: 'completed',
    document_count: 2,
    is_stale: false,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-01T10:30:00Z',
    data: {
      property_id: 'prop-123',
      supported_count: 2,
      unverified_count: 1,
      conflicting_count: 1,
      missing_count: 1,
      document_count: 2,
      identity: {
        property_name: {
          field_name: 'property_name',
          display_name: 'Property Name',
          extracted_value: 'Lotus Enclave',
          verification_status: 'supported',
          confidence: 0.98,
          alternative_values: [],
        },
        carpet_area: {
          field_name: 'carpet_area',
          display_name: 'Carpet Area',
          extracted_value: 850.5,
          original_value: '850.5 sq ft',
          normalized_value: 850.5,
          unit: 'sq_ft',
          filename: 'sale_agreement.pdf',
          page_number: 2,
          supporting_text: 'The apartment admeasures an aggregate carpet area of 850.5 sq.ft.',
          verification_status: 'supported',
          confidence: 0.92,
          alternative_values: [],
        },
        property_address: { field_name: 'property_address', display_name: 'Address', verification_status: 'missing', confidence: 0, alternative_values: [] },
        property_type: { field_name: 'property_type', display_name: 'Property Type', verification_status: 'missing', confidence: 0, alternative_values: [] },
        unit_number: { field_name: 'unit_number', display_name: 'Unit Number', verification_status: 'missing', confidence: 0, alternative_values: [] },
        built_up_area: { field_name: 'built_up_area', display_name: 'Built-up Area', verification_status: 'missing', confidence: 0, alternative_values: [] },
        area_unit: { field_name: 'area_unit', display_name: 'Area Unit', verification_status: 'missing', confidence: 0, alternative_values: [] },
      },
      financial: {
        sale_price: {
          field_name: 'sale_price',
          display_name: 'Sale Price',
          extracted_value: 12500000,
          original_value: '1.25 Crore',
          filename: 'sale_agreement.pdf',
          page_number: 3,
          supporting_text: 'The total consideration payable by the Purchaser is Rs. 1,25,00,000.',
          verification_status: 'supported',
          confidence: 0.95,
          alternative_values: [],
        },
        booking_amount: { field_name: 'booking_amount', display_name: 'Booking Amount', verification_status: 'missing', confidence: 0, alternative_values: [] },
        payment_schedule: { field_name: 'payment_schedule', display_name: 'Payment Schedule', verification_status: 'missing', confidence: 0, alternative_values: [] },
        maintenance_charges: { field_name: 'maintenance_charges', display_name: 'Maintenance Charges', verification_status: 'missing', confidence: 0, alternative_values: [] },
        deposits_and_additional_charges: { field_name: 'deposits_and_additional_charges', display_name: 'Deposits', verification_status: 'missing', confidence: 0, alternative_values: [] },
      },
      ownership_legal: {
        named_owner_or_seller: { field_name: 'named_owner_or_seller', display_name: 'Owner / Seller', verification_status: 'missing', confidence: 0, alternative_values: [] },
        title_deed_references: { field_name: 'title_deed_references', display_name: 'Title Deed References', verification_status: 'missing', confidence: 0, alternative_values: [] },
        ownership_claims: { field_name: 'ownership_claims', display_name: 'Ownership Claims', verification_status: 'missing', confidence: 0, alternative_values: [] },
        encumbrance_information: { field_name: 'encumbrance_information', display_name: 'Encumbrance Info', verification_status: 'missing', confidence: 0, alternative_values: [] },
        litigation_references: { field_name: 'litigation_references', display_name: 'Litigation References', verification_status: 'missing', confidence: 0, alternative_values: [] },
      },
      approvals: {
        project_registration_references: { field_name: 'project_registration_references', display_name: 'Project Registration', verification_status: 'missing', confidence: 0, alternative_values: [] },
        building_plan_approvals: { field_name: 'building_plan_approvals', display_name: 'Building Plan Approvals', verification_status: 'missing', confidence: 0, alternative_values: [] },
        completion_certificates: { field_name: 'completion_certificates', display_name: 'Completion Certificates', verification_status: 'missing', confidence: 0, alternative_values: [] },
        occupancy_certificates: { field_name: 'occupancy_certificates', display_name: 'Occupancy Certificates', verification_status: 'missing', confidence: 0, alternative_values: [] },
        fire_and_environmental_approvals: {
          field_name: 'fire_and_environmental_approvals',
          display_name: 'Fire Approvals',
          extracted_value: 'Pending NOC Certificate',
          original_value: 'Fire NOC pending',
          filename: 'brochure.pdf',
          page_number: 1,
          supporting_text: 'Fire approvals applied for.',
          verification_status: 'unverified',
          confidence: 0.4,
          alternative_values: [],
        },
      },
      dates_obligations: {
        agreement_date: { field_name: 'agreement_date', display_name: 'Agreement Date', verification_status: 'missing', confidence: 0, alternative_values: [] },
        possession_date: { field_name: 'possession_date', display_name: 'Possession Date', verification_status: 'missing', confidence: 0, alternative_values: [] },
        payment_deadlines: { field_name: 'payment_deadlines', display_name: 'Payment Deadlines', verification_status: 'missing', confidence: 0, alternative_values: [] },
        renewal_dates: { field_name: 'renewal_dates', display_name: 'Renewal Dates', verification_status: 'missing', confidence: 0, alternative_values: [] },
        contractual_obligations: { field_name: 'contractual_obligations', display_name: 'Contractual Obligations', verification_status: 'missing', confidence: 0, alternative_values: [] },
      },
      conflicts: [
        {
          source_a: {
            citation_id: 'S1',
            document_id: 'doc-1',
            filename: 'sale_agreement.pdf',
            page_number: 5,
            quote: 'Possession shall be delivered on or before 31st December 2025.',
          },
          source_b: {
            citation_id: 'S2',
            document_id: 'doc-2',
            filename: 'allotment_letter.pdf',
            page_number: 2,
            quote: 'Tentative handover by June 2024.',
          },
          contradiction_reason: 'Conflict in expected possession timeline.',
          resolution_note: 'Clarify with developer which timeline governs handover.',
        },
      ],
      missing_fields: ['occupancy_certificates', 'litigation_references'],
    },
  };

  const mockRiskAssessment: PropertyRiskAssessmentResponse = {
    assessment_id: 'assess-123',
    property_id: 'prop-123',
    status: 'completed',
    document_count: 2,
    is_stale: false,
    created_at: '2026-11-01T12:00:00Z',
    updated_at: '2026-11-01T12:30:00Z',
    summary: {
      total_findings: 2,
      critical_count: 1,
      high_count: 1,
      medium_count: 0,
      low_count: 0,
      informational_count: 0,
      open_count: 2,
      under_review_count: 0,
      resolved_count: 0,
      dismissed_count: 0,
    },
    findings: [
      {
        risk_id: 'risk-1',
        property_id: 'prop-123',
        rule_key: 'TITLE_CLAIM_CONFLICT',
        category: 'ownership_title',
        severity: 'critical',
        status: 'open',
        title: 'Conflicting Ownership Claims',
        description: 'Seller identity mismatch across title deed and sale agreement.',
        reason: 'Ownership entity differs in deed.',
        recommended_action: 'Request registered rectification deed.',
        evidence: [],
        affected_facts: ['named_owner_or_seller'],
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:00:00Z',
      },
      {
        risk_id: 'risk-2',
        property_id: 'prop-123',
        rule_key: 'APPROVAL_MISSING_OC',
        category: 'regulatory_approval',
        severity: 'high',
        status: 'open',
        title: 'Missing Occupancy Certificate',
        description: 'No occupancy certificate reference found.',
        reason: 'Building may be incomplete.',
        recommended_action: 'Verify OC status on municipal portal.',
        evidence: [],
        affected_facts: ['occupancy_certificates'],
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:00:00Z',
      },
    ],
  };

  // 1. PortfolioDashboard Tests
  describe('PortfolioDashboard Component', () => {
    it('renders KPI metrics correctly from response data', () => {
      const mockNavigate = vi.fn();
      const mockRefresh = vi.fn();

      render(
        <PortfolioDashboard
          stats={mockPortfolioStats}
          loading={false}
          onRefresh={mockRefresh}
          onNavigate={mockNavigate}
        />
      );

      // Total Properties
      expect(screen.getByText('Total Properties')).toBeInTheDocument();
      expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);

      // Documents
      expect(screen.getByText('Total Documents')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('6 processed')).toBeInTheDocument();

      // OCR Review Queue
      expect(screen.getByText('OCR / Review Queue')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();

      // Critical & High findings (2 + 1 = 3)
      expect(screen.getByText('Critical & High Risks')).toBeInTheDocument();
      expect(screen.getByText('2 critical, 1 high')).toBeInTheDocument();

      // Open vs Resolved
      expect(screen.getByText('Open vs Resolved')).toBeInTheDocument();
      expect(screen.getByText('3 / 4')).toBeInTheDocument();
    });

    it('renders properties requiring attention with alert badges and triggers navigation', () => {
      const mockNavigate = vi.fn();
      const mockRefresh = vi.fn();

      render(
        <PortfolioDashboard
          stats={mockPortfolioStats}
          loading={false}
          onRefresh={mockRefresh}
          onNavigate={mockNavigate}
        />
      );

      expect(screen.getByText('Skyline Palms')).toBeInTheDocument();
      expect(screen.getByText('2 CRITICAL')).toBeInTheDocument();
      expect(screen.getByText('OCR REVIEW')).toBeInTheDocument();

      expect(screen.getByText('Green Meadows')).toBeInTheDocument();
      expect(screen.getByText('1 HIGH')).toBeInTheDocument();
      expect(screen.getByText('STALE')).toBeInTheDocument();

      // Click "Review Property"
      const reviewButtons = screen.getAllByRole('button', { name: /Review Property/i });
      fireEvent.click(reviewButtons[0]);
      expect(mockNavigate).toHaveBeenCalledWith('properties', { propertyId: 'prop-attn-1' });
    });

    it('displays clear standing when no properties require attention', () => {
      const emptyStats: PortfolioStatsResponse = {
        ...mockPortfolioStats,
        critical_findings_count: 0,
        high_findings_count: 0,
        properties_requiring_attention: [],
      };

      render(
        <PortfolioDashboard
          stats={emptyStats}
          loading={false}
          onRefresh={vi.fn()}
          onNavigate={vi.fn()}
        />
      );

      expect(screen.getByText('All properties in good standing')).toBeInTheDocument();
    });

    it('calls onRefresh when Refresh Stats button is clicked', () => {
      const mockRefresh = vi.fn();
      render(
        <PortfolioDashboard
          stats={mockPortfolioStats}
          loading={false}
          onRefresh={mockRefresh}
          onNavigate={vi.fn()}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /Refresh Stats/i }));
      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });
  });

  // 2. DueDiligenceChecklist Tests
  describe('DueDiligenceChecklist Component', () => {
    it('renders statutory gap notice and groups critical checklist items', () => {
      render(
        <DueDiligenceChecklist
          propertyName="Lotus Enclave"
          propertyId="prop-123"
          extraction={mockExtraction}
          riskAssessment={mockRiskAssessment}
          onNavigateToTab={vi.fn()}
        />
      );

      // Informational gap notice
      expect(screen.getByText(/Due Diligence Gap vs Violation Notice/i)).toBeInTheDocument();

      // Action Required findings
      expect(screen.getByText(/Conflicting Ownership Claims/i)).toBeInTheDocument();
      expect(screen.getByText(/Contradiction: sale_agreement.pdf vs allotment_letter.pdf/i)).toBeInTheDocument();

      // Missing document attention item
      expect(screen.getByText(/Occupancy Certificate \(OC\)/i)).toBeInTheDocument();

      // Unverified claims
      expect(screen.getByText(/1 Unverified Fact Claim\(s\)/i)).toBeInTheDocument();
    });

    it('navigates to the corresponding tab when Inspect is clicked', () => {
      const mockTabNav = vi.fn();
      render(
        <DueDiligenceChecklist
          propertyName="Lotus Enclave"
          propertyId="prop-123"
          extraction={mockExtraction}
          riskAssessment={mockRiskAssessment}
          onNavigateToTab={mockTabNav}
        />
      );

      const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
      fireEvent.click(inspectButtons[0]);
      expect(mockTabNav).toHaveBeenCalled();
    });
  });

  // 3. EvidenceExplorer Tests
  describe('EvidenceExplorer Component', () => {
    it('renders verified quotes, citations, and cross-document comparison', () => {
      render(<EvidenceExplorer extraction={mockExtraction} />);

      // Metrics
      expect(screen.getByText('Verified Passages')).toBeInTheDocument();
      expect(screen.getByText('Unverified Claims')).toBeInTheDocument();
      expect(screen.getByText('Cross-Doc Contradictions')).toBeInTheDocument();

      // Cross document conflict side-by-side
      expect(screen.getByText(/Cross-Document Conflict Matrix/i)).toBeInTheDocument();
      expect(screen.getByText(/sale_agreement.pdf vs allotment_letter.pdf/i)).toBeInTheDocument();
      expect(screen.getByText(/Possession shall be delivered on or before 31st December 2025./i)).toBeInTheDocument();
      expect(screen.getByText(/Tentative handover by June 2024./i)).toBeInTheDocument();

      // Verbatim Passage
      expect(
        screen.getByText(/"The total consideration payable by the Purchaser is Rs. 1,25,00,000."/i)
      ).toBeInTheDocument();
      expect(screen.getAllByText('sale_agreement.pdf').length).toBeGreaterThanOrEqual(1);
    });

    it('filters facts dynamically when searching', () => {
      render(<EvidenceExplorer extraction={mockExtraction} />);

      const searchInput = screen.getByPlaceholderText(/Search facts, passages/i);
      fireEvent.change(searchInput, { target: { value: 'carpet_area' } });

      // carpet_area is present
      expect(screen.getAllByText(/Carpet Area/i).length).toBeGreaterThanOrEqual(1);
      // sale_price is filtered out
      expect(screen.queryByText(/Sale Price/i)).not.toBeInTheDocument();
    });
  });

  // 4. ActivityTimeline Tests
  describe('ActivityTimeline Component', () => {
    beforeEach(() => {
      vi.restoreAllMocks();
    });

    it('fetches and displays chronological events with metadata badges', async () => {
      vi.spyOn(propertiesApi, 'getActivity').mockResolvedValue({
        property_id: 'prop-123',
        events: [
          {
            event_id: 'evt-1',
            event_type: 'property_created',
            title: 'Property Created',
            description: "Property 'Lotus Enclave' was created.",
            timestamp: '2026-11-01T10:00:00Z',
            metadata: { name: 'Lotus Enclave' },
          },
          {
            event_id: 'evt-2',
            event_type: 'document_associated',
            title: 'Document Associated',
            description: "File 'sale_agreement.pdf' (PDF) was associated with property.",
            timestamp: '2026-11-01T10:05:00Z',
            metadata: { classification: 'Sale Deed' },
          },
        ],
      });

      render(<ActivityTimeline propertyId="prop-123" propertyName="Lotus Enclave" />);

      await waitFor(() => {
        expect(screen.getByText('Property Created')).toBeInTheDocument();
        expect(screen.getByText('Document Associated')).toBeInTheDocument();
      });

      expect(screen.getByText(/File 'sale_agreement.pdf'/i)).toBeInTheDocument();
      expect(screen.getByText(/classification:/i)).toBeInTheDocument();
    });
  });

  // 5. propertiesApi Tests
  describe('propertiesApi Client Extensions', () => {
    it('defines getPortfolioStats and getActivity', () => {
      expect(typeof propertiesApi.getPortfolioStats).toBe('function');
      expect(typeof propertiesApi.getActivity).toBe('function');
      expect(typeof propertiesApi.downloadReportPdf).toBe('function');
    });
  });
});
