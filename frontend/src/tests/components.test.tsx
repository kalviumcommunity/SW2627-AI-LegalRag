import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge, SourceTypeBadge, EvidenceStatusBadge } from '../components/common/Badge';
import { CitationCard } from '../components/rag/CitationCard';
import { AnswerView } from '../components/rag/AnswerView';
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

  it('renders AnswerView with claim-level verification, conflicts, and legal disclaimer', () => {
    const mockResponse: import('../api/types').RAGResponse = {
      question: 'What is the sale price and property area?',
      answer: 'The sale price is ₹1.5 Crores [S1]. The area is 2400 sq ft [S2].',
      evidence_status: 'conflicting_evidence',
      citations: [
        {
          citation_id: 'S1',
          chunk_id: 'chk_1',
          document_id: 'doc_1',
          filename: 'Deed_2024.pdf',
          source_type: 'pdf',
          page_number: 1,
          page_numbers: [1],
          chunk_index: 0,
          excerpt: 'Sale price is ₹1.5 Crores.',
        },
        {
          citation_id: 'S2',
          chunk_id: 'chk_2',
          document_id: 'doc_2',
          filename: 'Agreement_2022.pdf',
          source_type: 'pdf',
          page_number: 2,
          page_numbers: [2],
          chunk_index: 1,
          excerpt: 'Area is 2400 sq ft.',
        },
      ],
      limitations: [],
      retrieved_count: 2,
      used_chunk_count: 2,
      mode: 'semantic',
      claim_support_verified: true,
      claim_verifications: [
        {
          claim_text: 'The sale price is ₹1.5 Crores',
          status: 'supported',
          cited_source_ids: ['S1'],
          entailment_explanation: 'Cited source [S1] explicitly corroborates the sale price.',
          source_quotes: ['Sale price is ₹1.5 Crores.'],
        },
        {
          claim_text: 'The area is 2400 sq ft',
          status: 'contradicted',
          cited_source_ids: ['S2'],
          entailment_explanation: 'Contradicted by another document indicating different area.',
          source_quotes: ['Area is 2400 sq ft.'],
        },
      ],
      conflicts: [
        {
          source_a: {
            citation_id: 'S1',
            document_id: 'doc_1',
            filename: 'Deed_2024.pdf',
            page_number: 1,
            quote: 'Property area is 3000 sq ft.',
          },
          source_b: {
            citation_id: 'S2',
            document_id: 'doc_2',
            filename: 'Agreement_2022.pdf',
            page_number: 2,
            quote: 'Property area is 2400 sq ft.',
          },
          contradiction_reason: 'Documents specify conflicting property area measurements.',
          resolution_note: 'Antigravity RAG does not decide which document is legally authoritative.',
        },
      ],
      insufficient_reasons: [],
      legal_disclaimer:
        'Automated verification is provided for informational due diligence and triage only. It does NOT constitute legal advice or a guarantee of clear property title.',
    };

    render(<AnswerView response={mockResponse} />);

    expect(screen.getByText('What is the sale price and property area?')).toBeInTheDocument();
    expect(screen.getByText('Verified Support')).toBeInTheDocument();
    expect(screen.getByText('Contradicted Claim')).toBeInTheDocument();
    expect(screen.getByText(/Cross-Document Conflicts Detected/)).toBeInTheDocument();
    expect(screen.getByText(/Property area is 3000 sq ft/)).toBeInTheDocument();
    expect(screen.getByText(/Property area is 2400 sq ft/)).toBeInTheDocument();
    expect(screen.getByText(/Legal Due Diligence Notice:/)).toBeInTheDocument();
  });
});
