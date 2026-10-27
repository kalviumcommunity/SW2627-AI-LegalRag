import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, BookOpen } from 'lucide-react';
import { Card } from '../common/Card';
import { EvidenceStatusBadge } from '../common/Badge';
import { CitationCard } from './CitationCard';
import type { RAGResponse } from '../../api/types';

interface AnswerViewProps {
  response: RAGResponse;
  onInspectDocument?: (docId: string) => void;
}

export const AnswerView: React.FC<AnswerViewProps> = ({ response, onInspectDocument }) => {
  const [highlightedCitationId, setHighlightedCitationId] = useState<string | null>(null);

  const handleCitationClick = (citationId: string) => {
    setHighlightedCitationId(citationId);
    const element = document.getElementById(`citation-${citationId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  /**
   * Renders the answer markdown/text and makes [S1], [S2] markers interactive
   */
  const renderInteractiveAnswer = (text: string) => {
    // Regex matching [S1], [S2], [S12], etc.
    const parts = text.split(/(\[S[1-9][0-9]*\])/g);

    return parts.map((part, index) => {
      const match = part.match(/^\[(S[1-9][0-9]*)\]$/);
      if (match) {
        const citationId = match[1];
        const isSelected = highlightedCitationId === citationId;
        return (
          <button
            key={index}
            type="button"
            onClick={() => handleCitationClick(citationId)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              margin: '0 0.15rem',
              padding: '0.1rem 0.45rem',
              borderRadius: '9999px',
              backgroundColor: isSelected ? '#7C3AED' : '#EDE9FE',
              color: isSelected ? '#FFFFFF' : '#6D28D9',
              fontSize: '0.785rem',
              fontWeight: 700,
              border: '1px solid #DDD6FE',
              verticalAlign: 'baseline',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            title={`View evidence citation ${citationId}`}
          >
            {part}
          </button>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Primary Answer Card */}
      <Card padding="lg">
        {/* Status & Meta Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            marginBottom: '1.25rem',
            paddingBottom: '1rem',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <EvidenceStatusBadge status={response.evidence_status} />
            <span
              style={{
                fontSize: '0.8125rem',
                color: '#6B7280',
                backgroundColor: '#F3F4F6',
                padding: '0.25rem 0.65rem',
                borderRadius: '9999px',
                fontWeight: 600,
              }}
            >
              Mode: {response.mode.toUpperCase()}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8125rem', color: '#6B7280' }}>
            <span>
              <strong>{response.used_chunk_count}</strong> of {response.retrieved_count} chunks used
            </span>
            <span>
              <strong>{response.citations.length}</strong> citations
            </span>
          </div>
        </div>

        {/* Question echo */}
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase' }}>
            Question
          </span>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#18181B', marginTop: '0.2rem' }}>
            {response.question}
          </h2>
        </div>

        {/* Answer Content */}
        <div
          style={{
            backgroundColor: '#FCFAF7',
            padding: '1.5rem',
            borderRadius: '16px',
            border: '1px solid #F0EDE6',
            fontSize: '1rem',
            lineHeight: 1.65,
            color: '#1F2937',
            whiteSpace: 'pre-wrap',
            marginBottom: '1.25rem',
          }}
        >
          {renderInteractiveAnswer(response.answer)}
        </div>

        {/* Limitations if provided */}
        {response.limitations && response.limitations.length > 0 && (
          <div
            style={{
              backgroundColor: '#FEF3C7',
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              border: '1px solid #FDE047',
              marginBottom: '1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#B45309', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.35rem' }}>
              <AlertCircle size={16} />
              <span>Evidence Limitations</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8125rem', color: '#92400E' }}>
              {response.limitations.map((lim, idx) => (
                <li key={idx} style={{ marginTop: '0.2rem' }}>
                  {lim}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Guarantee disclaimer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.785rem',
            color: '#6B7280',
            backgroundColor: '#F3F4F6',
            padding: '0.65rem 0.85rem',
            borderRadius: '10px',
          }}
        >
          <ShieldCheck size={16} color="#059669" />
          <span>
            <strong>Retrieved source integrity:</strong> Every citation is strictly validated against
            stored chunk vectors. Claim-level entailment is not independently verified.
          </span>
        </div>
      </Card>

      {/* Citations Grid */}
      {response.citations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <BookOpen size={20} color="#7C3AED" />
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#18181B' }}>
              Source Evidence ({response.citations.length})
            </h3>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '1rem',
            }}
          >
            {response.citations.map((citation) => (
              <CitationCard
                key={citation.citation_id}
                citation={citation}
                isSelected={highlightedCitationId === citation.citation_id}
                onSelect={() => setHighlightedCitationId(citation.citation_id)}
                onInspectDocument={onInspectDocument}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
