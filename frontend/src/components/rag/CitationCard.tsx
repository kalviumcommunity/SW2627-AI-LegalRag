import React from 'react';
import { ExternalLink } from 'lucide-react';
import { SourceTypeBadge } from '../common/Badge';
import type { RAGCitation } from '../../api/types';

interface CitationCardProps {
  citation: RAGCitation;
  isSelected?: boolean;
  onSelect?: () => void;
  onInspectDocument?: (docId: string) => void;
}

export const CitationCard: React.FC<CitationCardProps> = ({
  citation,
  isSelected = false,
  onSelect,
  onInspectDocument,
}) => {
  const pageLabel = citation.page_number
    ? `Page ${citation.page_number}`
    : citation.page_numbers && citation.page_numbers.length > 0
    ? `Pages ${citation.page_numbers.join(', ')}`
    : null;

  return (
    <div
      id={`citation-${citation.citation_id}`}
      onClick={onSelect}
      style={{
        borderRadius: '16px',
        border: `1.5px solid ${isSelected ? '#7C3AED' : '#E5E7EB'}`,
        backgroundColor: isSelected ? '#FAF8FF' : '#FFFFFF',
        padding: '1.1rem',
        boxShadow: isSelected
          ? '0 6px 20px rgba(124, 58, 237, 0.15)'
          : '0 2px 8px rgba(0, 0, 0, 0.03)',
        transition: 'all 0.2s ease',
        cursor: 'pointer',
      }}
    >
      {/* Top row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.65rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Citation ID badge */}
          <span
            style={{
              backgroundColor: '#EDE9FE',
              color: '#6D28D9',
              padding: '0.2rem 0.6rem',
              borderRadius: '9999px',
              fontSize: '0.8125rem',
              fontWeight: 800,
              border: '1px solid #DDD6FE',
            }}
          >
            [{citation.citation_id}]
          </span>

          <span
            style={{
              fontWeight: 700,
              fontSize: '0.9rem',
              color: '#18181B',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: '220px',
            }}
            title={citation.filename}
          >
            {citation.filename}
          </span>
        </div>

        <SourceTypeBadge type={citation.source_type} />
      </div>

      {/* Excerpt */}
      <div
        style={{
          backgroundColor: '#FAF8F5',
          borderLeft: '3px solid #7C3AED',
          padding: '0.65rem 0.85rem',
          borderRadius: '4px',
          fontSize: '0.85rem',
          color: '#374151',
          lineHeight: 1.5,
          fontStyle: 'italic',
          marginBottom: '0.75rem',
        }}
      >
        "{citation.excerpt}"
      </div>

      {/* Metadata footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.775rem',
          color: '#6B7280',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {pageLabel && <span>{pageLabel}</span>}
          <span>Chunk #{citation.chunk_index}</span>
        </div>

        {onInspectDocument && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onInspectDocument(citation.document_id);
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              color: '#6D28D9',
              fontWeight: 600,
              fontSize: '0.775rem',
            }}
          >
            <span>View Doc</span>
            <ExternalLink size={12} />
          </button>
        )}
      </div>
    </div>
  );
};
