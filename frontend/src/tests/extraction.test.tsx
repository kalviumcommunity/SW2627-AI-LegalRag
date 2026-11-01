import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FactVerificationBadge } from '../components/common/Badge';
import { PropertyExtractionDashboard } from '../components/property/PropertyExtractionDashboard';
import type { PropertyExtractionResponse } from '../api/types';

describe('Property Extraction Frontend Tests', () => {
  it('renders FactVerificationBadge for all 4 statuses', () => {
    const { rerender } = render(<FactVerificationBadge status="supported" />);
    expect(screen.getByText('Supported')).toBeInTheDocument();

    rerender(<FactVerificationBadge status="unverified" />);
    expect(screen.getByText('Unverified')).toBeInTheDocument();

    rerender(<FactVerificationBadge status="conflicting" />);
    expect(screen.getByText('Conflicting')).toBeInTheDocument();

    rerender(<FactVerificationBadge status="missing" />);
    expect(screen.getByText('Missing')).toBeInTheDocument();
  });

  const mockExtractionResponse: PropertyExtractionResponse = {
    property_id: 'prop-123',
    status: 'completed',
    document_count: 2,
    is_stale: false,
    created_at: '2026-11-01T12:00:00Z',
    updated_at: '2026-11-01T12:00:00Z',
    data: {
      property_id: 'prop-123',
      document_count: 2,
      supported_count: 5,
      unverified_count: 2,
      conflicting_count: 1,
      missing_count: 3,
      missing_fields: [
        'Occupancy Certificate',
        'Fire Safety Certificate',
        'Encumbrance Certificate',
      ],
      conflicts: [
        {
          contradiction_reason: 'different monetary figures (8,500,000 vs 9,200,000)',
          resolution_note: 'Values preserved from distinct legal documents.',
          source_a: {
            citation_id: 'Primary',
            document_id: 'doc-1',
            filename: 'sale_deed.pdf',
            page_number: 2,
            quote: 'Total consideration of Rs. 85,00,000 paid by purchaser.',
          },
          source_b: {
            citation_id: 'Alternative',
            document_id: 'doc-2',
            filename: 'allotment_letter.pdf',
            page_number: 1,
            quote: 'Revised basic sale consideration fixed at Rs. 92,00,000.',
          },
        },
      ],
      identity: {
        property_name: {
          field_name: 'property_name',
          display_name: 'Property Name',
          extracted_value: 'Emerald Heights',
          original_value: 'Emerald Heights Apartments',
          verification_status: 'supported',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 1,
          supporting_text: 'Emerald Heights Apartments situated at Plot 42.',
          alternative_values: [],
        },
        property_address: {
          field_name: 'property_address',
          display_name: 'Property Address',
          extracted_value: 'Plot 42, Sector 5, Navi Mumbai',
          original_value: 'Plot 42, Sector 5, Kharghar, Navi Mumbai',
          verification_status: 'supported',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 1,
          supporting_text: 'situated at Plot 42, Sector 5, Kharghar, Navi Mumbai',
          alternative_values: [],
        },
        property_type: {
          field_name: 'property_type',
          display_name: 'Property Type',
          extracted_value: 'Residential Apartment',
          verification_status: 'supported',
          confidence: 0.9,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 1,
          supporting_text: 'Residential apartment unit No. 402',
          alternative_values: [],
        },
        unit_number: {
          field_name: 'unit_number',
          display_name: 'Unit Number',
          extracted_value: 'Flat 402',
          verification_status: 'supported',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 1,
          supporting_text: 'Flat No. 402, 4th Floor',
          alternative_values: [],
        },
        carpet_area: {
          field_name: 'carpet_area',
          display_name: 'Carpet Area',
          extracted_value: '1250 sq ft',
          original_value: '1,250 sq.ft.',
          normalized_value: 1250.0,
          unit: 'sq ft',
          verification_status: 'supported',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 2,
          supporting_text: 'having a carpet area of 1,250 sq.ft.',
          alternative_values: [],
        },
        built_up_area: {
          field_name: 'built_up_area',
          display_name: 'Built-up Area',
          extracted_value: '1500 sq ft',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        area_unit: {
          field_name: 'area_unit',
          display_name: 'Area Unit',
          extracted_value: 'sq ft',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
      },
      financial: {
        sale_price: {
          field_name: 'sale_price',
          display_name: 'Sale Price / Consideration',
          extracted_value: 'Rs. 85,00,000',
          original_value: 'Rs. 85,00,000',
          normalized_value: 8500000.0,
          unit: 'INR',
          verification_status: 'conflicting',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 2,
          supporting_text: 'Total consideration of Rs. 85,00,000 paid by purchaser.',
          uncertainty_note: 'Conflicting values detected across distinct documents (1 alternative(s)).',
          alternative_values: [
            {
              extracted_value: 'Rs. 92,00,000',
              original_value: 'Rs. 92,00,000',
              document_id: 'doc-2',
              filename: 'allotment_letter.pdf',
              page_number: 1,
              supporting_text: 'Revised basic sale consideration fixed at Rs. 92,00,000.',
            },
          ],
        },
        booking_amount: {
          field_name: 'booking_amount',
          display_name: 'Booking Amount',
          extracted_value: 'Rs. 5,00,000',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        payment_schedule: {
          field_name: 'payment_schedule',
          display_name: 'Payment Schedule',
          extracted_value: 'Construction linked 5-stage plan',
          verification_status: 'unverified',
          confidence: 0.7,
          alternative_values: [],
        },
        maintenance_charges: {
          field_name: 'maintenance_charges',
          display_name: 'Maintenance Charges',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
        deposits_and_additional_charges: {
          field_name: 'deposits_and_additional_charges',
          display_name: 'Deposits & Additional Charges',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
      },
      ownership_legal: {
        named_owner_or_seller: {
          field_name: 'named_owner_or_seller',
          display_name: 'Named Owner / Seller',
          extracted_value: 'Rajesh Kumar Sharma',
          verification_status: 'supported',
          confidence: 0.95,
          document_id: 'doc-1',
          filename: 'sale_deed.pdf',
          page_number: 1,
          supporting_text: 'Between Rajesh Kumar Sharma (Vendor) and ...',
          alternative_values: [],
        },
        title_deed_references: {
          field_name: 'title_deed_references',
          display_name: 'Title Deed References',
          extracted_value: 'Deed No. 2022/4512',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        ownership_claims: {
          field_name: 'ownership_claims',
          display_name: 'Ownership Claims',
          extracted_value: 'Sole absolute ownership with marketable title',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        encumbrance_information: {
          field_name: 'encumbrance_information',
          display_name: 'Encumbrance Information',
          extracted_value: 'Free from all encumbrances',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        litigation_references: {
          field_name: 'litigation_references',
          display_name: 'Litigation References',
          extracted_value: 'No pending litigation reported',
          verification_status: 'unverified',
          confidence: 0.65,
          alternative_values: [],
        },
      },
      approvals: {
        project_registration_references: {
          field_name: 'project_registration_references',
          display_name: 'Project Registration (RERA)',
          extracted_value: 'P51700012345',
          verification_status: 'supported',
          confidence: 0.95,
          alternative_values: [],
        },
        building_plan_approvals: {
          field_name: 'building_plan_approvals',
          display_name: 'Building Plan Approvals',
          extracted_value: 'CC/2021/890',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        completion_certificates: {
          field_name: 'completion_certificates',
          display_name: 'Completion Certificate',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
        occupancy_certificates: {
          field_name: 'occupancy_certificates',
          display_name: 'Occupancy Certificate',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
        fire_and_environmental_approvals: {
          field_name: 'fire_and_environmental_approvals',
          display_name: 'Fire & Environmental Approvals',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
      },
      dates_obligations: {
        agreement_date: {
          field_name: 'agreement_date',
          display_name: 'Agreement Date',
          extracted_value: '10th April 2022',
          normalized_value: '2022-04-10',
          verification_status: 'supported',
          confidence: 0.95,
          alternative_values: [],
        },
        possession_date: {
          field_name: 'possession_date',
          display_name: 'Possession Date',
          extracted_value: '31st December 2024',
          normalized_value: '2024-12-31',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
        payment_deadlines: {
          field_name: 'payment_deadlines',
          display_name: 'Payment Deadlines',
          extracted_value: 'Within 30 days of each slab completion',
          verification_status: 'supported',
          confidence: 0.85,
          alternative_values: [],
        },
        renewal_dates: {
          field_name: 'renewal_dates',
          display_name: 'Renewal Dates',
          extracted_value: null,
          verification_status: 'missing',
          confidence: 0.0,
          alternative_values: [],
        },
        contractual_obligations: {
          field_name: 'contractual_obligations',
          display_name: 'Contractual Obligations',
          extracted_value: 'Defect liability period of 5 years',
          verification_status: 'supported',
          confidence: 0.9,
          alternative_values: [],
        },
      },
    },
  };

  it('renders extraction dashboard with property overview and status KPI metrics', () => {
    const handleTrigger = vi.fn();
    const handleRefresh = vi.fn();

    render(
      <PropertyExtractionDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        extractionResponse={mockExtractionResponse}
        loading={false}
        onTriggerExtract={handleTrigger}
        onRefreshExtract={handleRefresh}
      />
    );

    // Verify header and metrics
    expect(screen.getByRole('heading', { level: 2, name: 'Emerald Heights' })).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument(); // supported count
    expect(screen.getByText('2')).toBeInTheDocument(); // unverified count
    expect(screen.getByText('1')).toBeInTheDocument(); // conflicting count
    expect(screen.getByText('3')).toBeInTheDocument(); // missing count

    // Verify key fields on Overview tab
    expect(screen.getByText('Flat 402')).toBeInTheDocument();
    expect(screen.getByText('1250 sq ft')).toBeInTheDocument();
  });

  it('opens citation modal when citation button is clicked and closes on dismiss', () => {
    render(
      <PropertyExtractionDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        extractionResponse={mockExtractionResponse}
        loading={false}
        onTriggerExtract={vi.fn()}
        onRefreshExtract={vi.fn()}
      />
    );

    // Find citation button for sale_deed.pdf
    const citationButtons = screen.getAllByTitle('Click to view supporting document excerpt');
    expect(citationButtons.length).toBeGreaterThan(0);

    // Click first citation button
    fireEvent.click(citationButtons[0]);

    // Modal should appear with citation title and supporting text
    expect(screen.getByText(/Source Citation:/)).toBeInTheDocument();
    expect(screen.getByText('Supporting Text Passage')).toBeInTheDocument();

    // Close button
    const closeBtn = screen.getByLabelText('Close citation modal');
    fireEvent.click(closeBtn);

    // Modal should close
    expect(screen.queryByText('Supporting Text Passage')).not.toBeInTheDocument();
  });

  it('switches to Conflicts tab and renders cross-document conflict details', () => {
    render(
      <PropertyExtractionDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        extractionResponse={mockExtractionResponse}
        loading={false}
        onTriggerExtract={vi.fn()}
        onRefreshExtract={vi.fn()}
      />
    );

    // Click Conflicts tab
    const conflictsTab = screen.getByText(/Conflicts \(1\)/);
    fireEvent.click(conflictsTab);

    // Should display discrepancy details
    expect(screen.getByText(/1 Cross-Document Discrepancies Found/)).toBeInTheDocument();
    expect(screen.getByText(/different monetary figures/)).toBeInTheDocument();
    expect(screen.getByText(/Total consideration of Rs. 85,00,000/)).toBeInTheDocument();
    expect(screen.getByText(/Revised basic sale consideration/)).toBeInTheDocument();
  });

  it('switches to Missing Fields tab and renders diligence gaps checklist', () => {
    render(
      <PropertyExtractionDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        extractionResponse={mockExtractionResponse}
        loading={false}
        onTriggerExtract={vi.fn()}
        onRefreshExtract={vi.fn()}
      />
    );

    // Click Missing Fields tab
    const missingTab = screen.getByText(/Missing Fields \(3\)/);
    fireEvent.click(missingTab);

    // Should display missing fields
    expect(screen.getByText(/Due Diligence Gaps \(3 Missing Attributes\)/)).toBeInTheDocument();
    expect(screen.getByText('Occupancy Certificate')).toBeInTheDocument();
    expect(screen.getByText('Fire Safety Certificate')).toBeInTheDocument();
    expect(screen.getByText('Encumbrance Certificate')).toBeInTheDocument();
  });

  it('triggers refresh callback when Refresh Extraction is clicked', () => {
    const handleRefresh = vi.fn();

    render(
      <PropertyExtractionDashboard
        propertyName="Emerald Heights"
        propertyId="prop-123"
        extractionResponse={mockExtractionResponse}
        loading={false}
        onTriggerExtract={vi.fn()}
        onRefreshExtract={handleRefresh}
      />
    );

    const refreshBtn = screen.getByText('Refresh Extraction');
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalledTimes(1);
  });
});
