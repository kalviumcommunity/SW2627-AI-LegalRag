import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RiskSeverityBadge, RiskFindingStatusBadge } from '../components/common/Badge';
import { PropertyRiskDashboard } from '../components/property/PropertyRiskDashboard';
import type { PropertyRiskAssessmentResponse } from '../api/types';

describe('Property Risk Assessment Frontend Tests', () => {
  it('renders RiskSeverityBadge for all 5 severities', () => {
    const { rerender } = render(<RiskSeverityBadge severity="critical" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();

    rerender(<RiskSeverityBadge severity="high" />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();

    rerender(<RiskSeverityBadge severity="medium" />);
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();

    rerender(<RiskSeverityBadge severity="low" />);
    expect(screen.getByText('LOW')).toBeInTheDocument();

    rerender(<RiskSeverityBadge severity="informational" />);
    expect(screen.getByText('INFO')).toBeInTheDocument();
  });

  it('renders RiskFindingStatusBadge for all 4 statuses', () => {
    const { rerender } = render(<RiskFindingStatusBadge status="open" />);
    expect(screen.getByText('Open')).toBeInTheDocument();

    rerender(<RiskFindingStatusBadge status="under_review" />);
    expect(screen.getByText('Under Review')).toBeInTheDocument();

    rerender(<RiskFindingStatusBadge status="resolved" />);
    expect(screen.getByText('Resolved')).toBeInTheDocument();

    rerender(<RiskFindingStatusBadge status="dismissed" />);
    expect(screen.getByText('Dismissed')).toBeInTheDocument();
  });

  const mockRiskAssessment: PropertyRiskAssessmentResponse = {
    assessment_id: 'assess-123',
    property_id: 'prop-123',
    status: 'completed',
    document_count: 2,
    is_stale: false,
    created_at: '2026-11-01T12:00:00Z',
    updated_at: '2026-11-01T12:30:00Z',
    summary: {
      total_findings: 3,
      critical_count: 1,
      high_count: 1,
      medium_count: 1,
      low_count: 0,
      informational_count: 0,
      open_count: 2,
      under_review_count: 0,
      resolved_count: 1,
      dismissed_count: 0,
    },
    findings: [
      {
        risk_id: 'risk-litigation-001',
        property_id: 'prop-123',
        rule_key: 'litigation_reference',
        category: 'legal_dispute',
        title: 'Active Litigation Reference Detected',
        description: 'Document references pending High Court civil suit.',
        severity: 'critical',
        status: 'open',
        reason: 'Litigation poses severe threat to marketable title.',
        affected_facts: ['litigation_references'],
        recommended_action: 'Obtain certified copy of order and obtain title clearance.',
        evidence: [
          {
            document_id: 'doc-1',
            filename: 'sale_deed.pdf',
            page_number: 4,
            supporting_text: 'Subject to pending suit WP 1024/2022 before Bombay High Court.',
            fact_field: 'litigation_references',
            verification_status: 'supported',
          },
        ],
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:00:00Z',
      },
      {
        risk_id: 'risk-financial-002',
        property_id: 'prop-123',
        rule_key: 'financial_price_conflict',
        category: 'financial',
        title: 'Conflicting Sale Consideration Amounts',
        description: 'Values differ: 8,500,000 INR vs 9,200,000 INR across documents.',
        severity: 'high',
        status: 'open',
        reason: 'Material discrepancy in agreed purchase price.',
        affected_facts: ['sale_price'],
        recommended_action: 'Verify bank disbursement schedule and stamped agreement.',
        evidence: [
          {
            document_id: 'doc-1',
            filename: 'sale_deed.pdf',
            page_number: 2,
            supporting_text: 'Total sale price Rs 85,00,000.',
            fact_field: 'sale_price',
            verification_status: 'conflicting',
          },
          {
            document_id: 'doc-2',
            filename: 'allotment.pdf',
            page_number: 1,
            supporting_text: 'Total price Rs 92,00,000.',
            fact_field: 'sale_price',
            verification_status: 'conflicting',
          },
        ],
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:00:00Z',
      },
      {
        risk_id: 'risk-approval-003',
        property_id: 'prop-123',
        rule_key: 'regulatory_oc_missing',
        category: 'regulatory_approval',
        title: 'Occupancy Certificate Missing',
        description: 'No occupancy certificate found among uploaded documents.',
        severity: 'medium',
        status: 'resolved',
        reason: 'Occupancy certificate required for legal handover.',
        affected_facts: ['occupancy_certificate'],
        recommended_action: 'Request OC from developer or local municipal body.',
        evidence: [],
        user_notes: 'Verified physically with builder on Oct 30.',
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:30:00Z',
      },
    ],
  };

  it('renders empty prompt when no assessment exists', () => {
    const handleTrigger = vi.fn();
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={null}
        loading={false}
        onTriggerAssess={handleTrigger}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    expect(screen.getByText('No Risk Assessment Available')).toBeInTheDocument();
    const btn = screen.getByText('Run Risk Assessment');
    fireEvent.click(btn);
    expect(handleTrigger).toHaveBeenCalledTimes(1);
  });

  it('renders loading indicator while assessment is running', () => {
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={null}
        loading={true}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    expect(screen.getByText('Evaluating property due diligence risks across documents...')).toBeInTheDocument();
  });

  it('renders assessment summary metrics, legal disclaimer, and findings', () => {
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={mockRiskAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    // Score and summary counts
    expect(screen.getByText('Critical Risks')).toBeInTheDocument();
    expect(screen.getByText('Active Litigation Reference Detected')).toBeInTheDocument();
    expect(screen.getByText('Conflicting Sale Consideration Amounts')).toBeInTheDocument();
    expect(screen.getByText('Occupancy Certificate Missing')).toBeInTheDocument();

    // Legal notice check
    expect(screen.getByText(/Due Diligence Legal Notice/i)).toBeInTheDocument();
    expect(screen.getByText(/never declare a property legally clear/i)).toBeInTheDocument();

    // Due diligence checklist exists
    expect(screen.getByText('Due Diligence Checklist & Categories')).toBeInTheDocument();
  });

  it('filters findings by severity', () => {
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={mockRiskAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    const severitySelect = screen.getByLabelText(/Severity/i) as HTMLSelectElement;
    fireEvent.change(severitySelect, { target: { value: 'critical' } });

    // Should only show the critical litigation finding
    expect(screen.getByText('Active Litigation Reference Detected')).toBeInTheDocument();
    expect(screen.queryByText('Conflicting Sale Consideration Amounts')).not.toBeInTheDocument();
    expect(screen.queryByText('Occupancy Certificate Missing')).not.toBeInTheDocument();
  });

  it('filters findings by status', () => {
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={mockRiskAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    const statusSelect = screen.getByLabelText(/^Status$/i) as HTMLSelectElement;
    fireEvent.change(statusSelect, { target: { value: 'resolved' } });

    // Should only show the resolved finding
    expect(screen.getByText('Occupancy Certificate Missing')).toBeInTheDocument();
    expect(screen.queryByText('Active Litigation Reference Detected')).not.toBeInTheDocument();
    expect(screen.queryByText('Conflicting Sale Consideration Amounts')).not.toBeInTheDocument();
  });

  it('opens and closes evidence modal when evidence button is clicked', () => {
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={mockRiskAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    // Finding with evidence: click on the first evidence button
    const viewEvidenceBtns = screen.getAllByText(/sale_deed\.pdf/i);
    fireEvent.click(viewEvidenceBtns[0]);

    // Evidence modal header & excerpt should appear
    expect(screen.getByText('Supporting Legal Evidence')).toBeInTheDocument();
    expect(screen.getByText(/Subject to pending suit WP 1024\/2022/i)).toBeInTheDocument();
    expect(screen.getByText('sale_deed.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Page 4/i)).toBeInTheDocument();

    // Close button
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(screen.queryByText('Supporting Legal Evidence')).not.toBeInTheDocument();
  });

  it('opens status update modal and submits status change', async () => {
    const handleUpdate = vi.fn().mockResolvedValue(undefined);

    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={mockRiskAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={vi.fn()}
        onUpdateFindingStatus={handleUpdate}
      />
    );

    // Find "Update Status" buttons - click the first one (for the critical litigation risk)
    const updateButtons = screen.getAllByText('Update Status');
    fireEvent.click(updateButtons[0]);

    // Modal title should appear
    expect(screen.getByText('Update Finding Status')).toBeInTheDocument();

    // Change status select to 'under_review'
    const statusSelect = screen.getByLabelText(/Review Status/i) as HTMLSelectElement;
    fireEvent.change(statusSelect, { target: { value: 'under_review' } });

    // Enter review notes
    const notesInput = screen.getByPlaceholderText(/Add attorney or reviewer notes/i);
    fireEvent.change(notesInput, { target: { value: 'Advocate Verma reviewing court status.' } });

    // Submit form
    const saveBtn = screen.getByText('Save Status');
    fireEvent.click(saveBtn);

    expect(handleUpdate).toHaveBeenCalledTimes(1);
    expect(handleUpdate).toHaveBeenCalledWith(
      'risk-litigation-001',
      'under_review',
      'Advocate Verma reviewing court status.'
    );
  });

  it('displays stale assessment warning banner when documents changed', () => {
    const staleAssessment: PropertyRiskAssessmentResponse = {
      ...mockRiskAssessment,
      is_stale: true,
    };

    const handleRefresh = vi.fn();
    render(
      <PropertyRiskDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        assessmentResponse={staleAssessment}
        loading={false}
        onTriggerAssess={vi.fn()}
        onRefreshAssess={handleRefresh}
        onUpdateFindingStatus={vi.fn()}
      />
    );

    expect(screen.getByText(/Assessment Stale/i)).toBeInTheDocument();
    expect(screen.getByText(/Property documents have been added or updated/i)).toBeInTheDocument();

    const refreshBtn = screen.getByText('Refresh Assessment');
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });
});
