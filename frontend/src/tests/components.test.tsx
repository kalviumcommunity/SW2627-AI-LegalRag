import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge, SourceTypeBadge, EvidenceStatusBadge } from '../components/common/Badge';
import { CitationCard } from '../components/rag/CitationCard';
import { HeroBanner } from '../components/dashboard/HeroBanner';
import { StatsRow } from '../components/dashboard/StatsRow';
import { EvidenceCard } from '../components/dashboard/EvidenceCard';
import type { RAGCitation } from '../api/types';

describe('Component Unit Tests', () => {
  it('renders StatusBadge variations properly', () => {
    const { rerender } = render(<StatusBadge status="processed" />);
    expect(screen.getByText('Processed')).toBeInTheDocument();

    rerender(<StatusBadge status="ocr_required" />);
    expect(screen.getByText('OCR Required')).toBeInTheDocument();

    rerender(<StatusBadge status="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders SourceTypeBadge correctly', () => {
    const { rerender } = render(<SourceTypeBadge type="pdf" />);
    expect(screen.getByText('PDF')).toBeInTheDocument();

    rerender(<SourceTypeBadge type="txt" />);
    expect(screen.getByText('TXT')).toBeInTheDocument();

    rerender(<SourceTypeBadge type="markdown" />);
    expect(screen.getByText('MD')).toBeInTheDocument();
  });

  it('renders EvidenceStatusBadge with appropriate grounding label', () => {
    const { rerender } = render(<EvidenceStatusBadge status="supported" />);
    expect(screen.getByText('Supported by Evidence')).toBeInTheDocument();

    rerender(<EvidenceStatusBadge status="insufficient_evidence" />);
    expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument();

    rerender(<EvidenceStatusBadge status="conflicting_evidence" />);
    expect(screen.getByText('Conflicting Evidence')).toBeInTheDocument();

    rerender(<EvidenceStatusBadge status="no_relevant_sources" />);
    expect(screen.getByText('No Relevant Sources')).toBeInTheDocument();
  });

  it('renders CitationCard with citation ID, excerpt and page', () => {
    const mockCitation: RAGCitation = {
      citation_id: 'S1',
      chunk_id: 'chunk-99',
      document_id: 'doc-42',
      filename: 'Sample_Deed.pdf',
      source_type: 'pdf',
      page_number: 3,
      page_numbers: [3],
      chunk_index: 2,
      excerpt: 'The northern boundary measures 150 feet along Elm Street.',
    };

    render(<CitationCard citation={mockCitation} />);

    expect(screen.getByText('[S1]')).toBeInTheDocument();
    expect(screen.getByText('Sample_Deed.pdf')).toBeInTheDocument();
    expect(screen.getByText('Page 3')).toBeInTheDocument();
    expect(screen.getByText('Chunk #2')).toBeInTheDocument();
    expect(
      screen.getByText(/"The northern boundary measures 150 feet along Elm Street."/)
    ).toBeInTheDocument();
  });

  it('renders HeroBanner with headline and whimsical welcome annotation', () => {
    render(<HeroBanner />);
    expect(screen.getByText('Welcome back!')).toBeInTheDocument();
    expect(screen.getByText(/Your property files,/)).toBeInTheDocument();
    expect(screen.getByText('decoded.')).toBeInTheDocument();
  });

  it('renders StatsRow with document counts', () => {
    const stats = {
      total: 12,
      processed: 9,
      ocrRequired: 2,
      failed: 1,
    };

    render(<StatsRow stats={stats} />);

    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Total Documents')).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('Processed')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('OCR Required')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders EvidenceCard with title and description', () => {
    render(<EvidenceCard />);
    expect(screen.getByText('Evidence first.')).toBeInTheDocument();
    expect(
      screen.getByText(/Every answer includes citations to your original documents/)
    ).toBeInTheDocument();
  });
});
