import React, { useState } from 'react';
import { ArrowRight, MoreHorizontal, Eye, MessageSquareText, Trash2, FileText } from 'lucide-react';
import { Card } from '../common/Card';
import { StatusBadge } from '../common/Badge';
import { TableSkeleton } from '../common/Skeleton';
import { EmptyState } from '../common/EmptyState';
import type { DocumentSummary } from '../../api/types';

interface RecentDocsProps {
  documents: DocumentSummary[];
  loading?: boolean;
  onViewAll: () => void;
  onViewDetails: (docId: string) => void;
  onAskDoc: (docId: string) => void;
  onDeleteDoc: (doc: DocumentSummary) => void;
}

export const RecentDocs: React.FC<RecentDocsProps> = ({
  documents,
  loading = false,
  onViewAll,
  onViewDetails,
  onAskDoc,
  onDeleteDoc,
}) => {
  const [activeMenuDocId, setActiveMenuDocId] = useState<string | null>(null);

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return 'Just now';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const getFileIconColor = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return { bg: '#FEE2E2', color: '#DC2626' };
    if (ext === 'txt') return { bg: '#DBEAFE', color: '#2563EB' };
    return { bg: '#EDE9FE', color: '#7C3AED' };
  };

  return (
    <Card padding="lg" style={{ position: 'relative' }}>
      {/* Card Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.25rem',
        }}
      >
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#18181B' }}>
            Recent Documents
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#6B7280', marginTop: '0.15rem' }}>
            Your latest uploads and their processing status.
          </p>
        </div>

        <button
          onClick={onViewAll}
          className="btn-secondary"
          style={{
            padding: '0.45rem 1rem',
            fontSize: '0.875rem',
            borderRadius: '9999px',
          }}
        >
          <span>View all</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <TableSkeleton rows={4} />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No property documents yet"
          description="Upload your first property deed, inspection report, or lease above to begin."
        />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              textAlign: 'left',
              fontSize: '0.875rem',
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: '1px solid #F0EDE6',
                  color: '#6B7280',
                  fontSize: '0.775rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                <th style={{ padding: '0.75rem 1rem' }}>File Name</th>
                <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Chunks</th>
                <th style={{ padding: '0.75rem 1rem' }}>Uploaded</th>
                <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.slice(0, 6).map((doc) => {
                const iconStyle = getFileIconColor(doc.filename);
                const isMenuOpen = activeMenuDocId === doc.document_id;

                return (
                  <tr
                    key={doc.document_id}
                    style={{
                      borderBottom: '1px solid #FAF8F5',
                      transition: 'background-color 0.15s ease',
                      cursor: 'pointer',
                    }}
                    onClick={() => onViewDetails(doc.document_id)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#FCFAF7';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    {/* Filename with colored icon */}
                    <td style={{ padding: '0.9rem 1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                          style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '8px',
                            backgroundColor: iconStyle.bg,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: iconStyle.color,
                            flexShrink: 0,
                          }}
                        >
                          <FileText size={16} />
                        </div>
                        <span
                          style={{
                            fontWeight: 600,
                            color: '#1F2937',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '240px',
                          }}
                          title={doc.filename}
                        >
                          {doc.filename}
                        </span>
                      </div>
                    </td>

                    {/* Source Type */}
                    <td style={{ padding: '0.9rem 1rem' }}>
                      <span
                        style={{
                          fontWeight: 600,
                          color: '#4B5563',
                          fontSize: '0.8125rem',
                        }}
                      >
                        {(doc.source_type || 'PDF').toUpperCase()}
                      </span>
                    </td>

                    {/* Status Badge */}
                    <td style={{ padding: '0.9rem 1rem' }}>
                      <StatusBadge status={doc.status} size="sm" />
                    </td>

                    {/* Chunks Count */}
                    <td style={{ padding: '0.9rem 1rem', color: '#4B5563', fontWeight: 500 }}>
                      {doc.chunk_count}
                    </td>

                    {/* Upload Date */}
                    <td style={{ padding: '0.9rem 1rem', color: '#6B7280', fontSize: '0.8125rem' }}>
                      {formatDate(doc.created_at)}
                    </td>

                    {/* Actions menu */}
                    <td
                      style={{ padding: '0.9rem 0.5rem', textAlign: 'right', position: 'relative' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setActiveMenuDocId(isMenuOpen ? null : doc.document_id)}
                        style={{
                          padding: '0.4rem',
                          borderRadius: '8px',
                          color: '#9CA3AF',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        aria-label="Actions"
                      >
                        <MoreHorizontal size={18} />
                      </button>

                      {isMenuOpen && (
                        <div
                          className="editorial-card animate-fade-in"
                          style={{
                            position: 'absolute',
                            right: '0',
                            top: '85%',
                            zIndex: 100,
                            backgroundColor: '#FFFFFF',
                            borderRadius: '12px',
                            boxShadow: '0 10px 25px -4px rgba(0, 0, 0, 0.12)',
                            minWidth: '175px',
                            padding: '0.4rem',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.2rem',
                          }}
                        >
                          <button
                            onClick={() => {
                              setActiveMenuDocId(null);
                              onViewDetails(doc.document_id);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              padding: '0.5rem 0.75rem',
                              fontSize: '0.8125rem',
                              color: '#1F2937',
                              borderRadius: '6px',
                              textAlign: 'left',
                              width: '100%',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F3F4F6')}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                          >
                            <Eye size={14} color="#6D28D9" />
                            <span>Inspect Chunks</span>
                          </button>

                          <button
                            onClick={() => {
                              setActiveMenuDocId(null);
                              onAskDoc(doc.document_id);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              padding: '0.5rem 0.75rem',
                              fontSize: '0.8125rem',
                              color: '#1F2937',
                              borderRadius: '6px',
                              textAlign: 'left',
                              width: '100%',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F3F4F6')}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                          >
                            <MessageSquareText size={14} color="#16A34A" />
                            <span>Ask AI about this</span>
                          </button>

                          <button
                            onClick={() => {
                              setActiveMenuDocId(null);
                              onDeleteDoc(doc);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              padding: '0.5rem 0.75rem',
                              fontSize: '0.8125rem',
                              color: '#DC2626',
                              borderRadius: '6px',
                              textAlign: 'left',
                              width: '100%',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FEE2E2')}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                          >
                            <Trash2 size={14} color="#DC2626" />
                            <span>Delete Document</span>
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};
