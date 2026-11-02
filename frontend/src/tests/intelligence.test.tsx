import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import {
  DocumentCategoryBadge,
  DocumentOcrStatusBadge,
  SourceTypeBadge,
} from '../components/common/Badge';
import { DocumentIntelligencePanel } from '../components/document/DocumentIntelligencePanel';
import { ToastProvider } from '../components/common/Toast';
import { documentsApi } from '../api/documents';
import type {
  DocumentClassificationResponse,
  DocumentDuplicatesResponse,
  DocumentProcessingStatusResponse,
  ExtractedTablesResponse,
} from '../api/types';

const renderWithToast = (ui: React.ReactElement) => {
  return render(<ToastProvider>{ui}</ToastProvider>);
};

describe('Document Intelligence Frontend Tests', () => {
  it('renders DocumentCategoryBadge with confidence and manual edit indicator', () => {
    const { rerender } = render(
      <DocumentCategoryBadge
        category="Sale Deed"
        confidence={0.95}
        manuallyCorrected={false}
      />
    );
    expect(screen.getByText('Sale Deed')).toBeInTheDocument();
    expect(screen.queryByText('(edited)')).not.toBeInTheDocument();

    rerender(
      <DocumentCategoryBadge
        category="Agreement to Sell"
        confidence={1.0}
        manuallyCorrected={true}
      />
    );
    expect(screen.getByText('Agreement to Sell')).toBeInTheDocument();
    expect(screen.getByText('(edited)')).toBeInTheDocument();
  });

  it('renders DocumentOcrStatusBadge for all 5 OCR lifecycle states', () => {
    const { rerender } = render(<DocumentOcrStatusBadge status="ocr_completed" />);
    expect(screen.getByText('OCR Completed')).toBeInTheDocument();

    rerender(<DocumentOcrStatusBadge status="processing_ocr" />);
    expect(screen.getByText('Processing OCR')).toBeInTheDocument();

    rerender(<DocumentOcrStatusBadge status="pending_ocr" />);
    expect(screen.getByText('Pending OCR')).toBeInTheDocument();

    rerender(<DocumentOcrStatusBadge status="needs_manual_review" />);
    expect(screen.getByText('Needs Manual Review')).toBeInTheDocument();

    rerender(<DocumentOcrStatusBadge status="ocr_failed" />);
    expect(screen.getByText('OCR Failed')).toBeInTheDocument();
  });

  it('renders SourceTypeBadge for image types', () => {
    const { rerender } = render(<SourceTypeBadge type="image" />);
    expect(screen.getByText('IMG')).toBeInTheDocument();

    rerender(<SourceTypeBadge type="png" />);
    expect(screen.getByText('IMG')).toBeInTheDocument();

    rerender(<SourceTypeBadge type="jpg" />);
    expect(screen.getByText('IMG')).toBeInTheDocument();
  });

  describe('DocumentIntelligencePanel Component', () => {
    const mockStatus: DocumentProcessingStatusResponse = {
      document_id: 'doc-123',
      filename: 'deed.pdf',
      status: 'processed',
      ocr_status: 'ocr_completed',
      ocr_page_count: 5,
      page_count: 5,
      extracted_characters: 4500,
      chunk_count: 6,
      classification_category: 'Sale Deed',
      classification_confidence: 0.94,
      classification_reasoning: 'Indenture of sale covenants matched.',
      classification_manually_corrected: false,
      has_duplicates: true,
      table_count: 1,
      warnings: [],
      detail: null,
      created_at: '2026-11-01T10:00:00Z',
      updated_at: '2026-11-01T10:00:00Z',
    };

    const mockDuplicates: DocumentDuplicatesResponse = {
      document_id: 'doc-123',
      has_duplicates: true,
      exact_matches: [
        {
          document_id: 'doc-orig',
          filename: 'original_deed.pdf',
          match_type: 'exact',
          similarity: 1.0,
          reasons: ['Identical SHA-256 hash'],
        },
      ],
      near_matches: [
        {
          document_id: 'doc-near',
          filename: 'draft_deed.pdf',
          match_type: 'near_duplicate',
          similarity: 0.88,
          reasons: ['88% structural overlap'],
        },
      ],
    };

    const mockTables: ExtractedTablesResponse = {
      document_id: 'doc-123',
      table_count: 1,
      tables: [
        {
          table_id: 'tbl-schedule-1',
          title: 'Payment Schedule',
          headers: ['Milestone', 'Amount (INR)'],
          rows: [
            ['Token Advance', '5,00,000'],
            ['On Registration', '45,00,000'],
          ],
          page_number: 3,
          category: 'payment_schedule',
        },
      ],
    };

    beforeEach(() => {
      vi.restoreAllMocks();
      vi.spyOn(documentsApi, 'getProcessingStatus').mockResolvedValue(mockStatus);
      vi.spyOn(documentsApi, 'getDuplicates').mockResolvedValue(mockDuplicates);
      vi.spyOn(documentsApi, 'getTables').mockResolvedValue(mockTables);
      vi.spyOn(documentsApi, 'reprocess').mockResolvedValue({
        document_id: 'doc-123',
        filename: 'deed.pdf',
        status: 'processed',
        extracted_characters: 4500,
        chunk_count: 6,
        chunks: [],
        warnings: [],
      });
      vi.spyOn(documentsApi, 'updateClassification').mockResolvedValue({
        document_id: 'doc-123',
        category: 'Allotment Letter',
        confidence: 1.0,
        reasoning: 'Category manually updated by user.',
        manually_corrected: true,
        updated_at: '2026-11-01T11:00:00Z',
      });
    });

    it('loads and renders classification, OCR status, and extracted tables', async () => {
      renderWithToast(<DocumentIntelligencePanel documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('Advanced Document Intelligence')).toBeInTheDocument();
      });

      // Classification
      expect(screen.getByText('Sale Deed')).toBeInTheDocument();
      expect(screen.getByText('94% confidence')).toBeInTheDocument();
      expect(screen.getByText(/Indenture of sale covenants matched/)).toBeInTheDocument();

      // OCR & Character stats
      expect(screen.getByText('OCR Completed')).toBeInTheDocument();
      expect(screen.getByText('4,500')).toBeInTheDocument();

      // Duplicate banners
      expect(screen.getByTestId('exact-duplicate-warning')).toBeInTheDocument();
      expect(screen.getByText(/original_deed\.pdf/)).toBeInTheDocument();
      expect(screen.getByTestId('near-duplicate-warning')).toBeInTheDocument();
      expect(screen.getByText(/draft_deed\.pdf/)).toBeInTheDocument();

      // Extracted table
      expect(screen.getByText('Extracted Structured Tables (1)')).toBeInTheDocument();
      expect(screen.getByText('Payment Schedule')).toBeInTheDocument();
      expect(screen.getByText('Token Advance')).toBeInTheDocument();
      expect(screen.getByText('5,00,000')).toBeInTheDocument();
    });

    it('supports manual category correction', async () => {
      renderWithToast(<DocumentIntelligencePanel documentId="doc-123" />);

      await waitFor(() => {
        expect(screen.getByText('Correct')).toBeInTheDocument();
      });

      // Click "Correct"
      fireEvent.click(screen.getByText('Correct'));

      // Check dropdown exists
      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();

      // Select "Allotment Letter"
      fireEvent.change(select, { target: { value: 'Allotment Letter' } });

      // Click Save
      fireEvent.click(screen.getByText('Save'));

      await waitFor(() => {
        expect(documentsApi.updateClassification).toHaveBeenCalledWith(
          'doc-123',
          'Allotment Letter'
        );
      });
    });

    it('triggers document reprocessing on click', async () => {
      const onRefresh = vi.fn();
      renderWithToast(<DocumentIntelligencePanel documentId="doc-123" onRefresh={onRefresh} />);

      await waitFor(() => {
        expect(screen.getByText('Reprocess Document')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Reprocess Document'));

      await waitFor(() => {
        expect(documentsApi.reprocess).toHaveBeenCalledWith('doc-123');
        expect(onRefresh).toHaveBeenCalled();
      });
    });
  });
});
