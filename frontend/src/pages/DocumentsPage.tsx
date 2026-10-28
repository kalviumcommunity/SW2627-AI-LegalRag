import React, { useEffect, useState, useCallback } from 'react';
import {
  FileText,
  Upload,
  Search,
  ChevronLeft,
  ChevronRight,
  Eye,
  MessageSquareText,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { Card } from '../components/common/Card';
import { StatusBadge, SourceTypeBadge } from '../components/common/Badge';
import { TableSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { Modal } from '../components/common/Modal';
import { UploadZone } from '../components/dashboard/UploadZone';
import { documentsApi } from '../api/documents';
import { useToast } from '../components/common/Toast';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import type { DocumentSummary, IngestionStatus, SourceType } from '../api/types';

interface DocumentsPageProps {
  onNavigate: (page: string, params?: { docId?: string; question?: string }) => void;
  initialSearch?: string;
}

export const DocumentsPage: React.FC<DocumentsPageProps> = ({ onNavigate, initialSearch = '' }) => {
  const { isAuthenticated, openAuthModal } = useAuth();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>(initialSearch);

  // Modals
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [deletingDoc, setDeletingDoc] = useState<DocumentSummary | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const { showSuccess, showError } = useToast();

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const params: {
        page: number;
        page_size: number;
        status?: IngestionStatus;
        source_type?: SourceType;
      } = {
        page,
        page_size: pageSize,
      };

      if (statusFilter !== 'all') {
        params.status = statusFilter as IngestionStatus;
      }
      if (sourceTypeFilter !== 'all') {
        params.source_type = sourceTypeFilter as SourceType;
      }

      const res = await documentsApi.list(params);
      setDocuments(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 1);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setDocuments([]);
        setTotal(0);
        setTotalPages(1);
        return;
      }
      const msg = err instanceof Error ? err.message : 'Failed to fetch documents';
      showError(msg);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, sourceTypeFilter, showError]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments, isAuthenticated]);

  const handleOpenUpload = () => {
    if (!isAuthenticated) {
      openAuthModal('login');
      return;
    }
    setIsUploadOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingDoc) return;
    try {
      setIsDeleting(true);
      await documentsApi.delete(deletingDoc.document_id);
      showSuccess(`"${deletingDoc.filename}" deleted.`);
      setDeletingDoc(null);
      fetchDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Deletion failed';
      showError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredDocs = searchQuery.trim()
    ? documents.filter((doc) =>
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : documents;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header & Upload Action */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '2.1rem', fontWeight: 800, color: '#18181B' }}>
            Property Documents
          </h1>
          <p style={{ fontSize: '0.95rem', color: '#6B7280', marginTop: '0.2rem' }}>
            Manage, inspect, and track lifecycle of uploaded deeds, leases, and reports.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => fetchDocuments()}
            className="btn-outline"
            title="Refresh list"
            aria-label="Refresh list"
          >
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>

          <button
            onClick={handleOpenUpload}
            className="btn-primary"
            style={{ backgroundColor: '#7C3AED' }}
          >
            <Upload size={16} />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card padding="sm" style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        {/* Search Input */}
        <div
          style={{
            flex: '1 1 280px',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Search size={16} color="#9CA3AF" style={{ position: 'absolute', left: '0.75rem' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by filename..."
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem 0.5rem 2.25rem',
              fontSize: '0.875rem',
            }}
          />
        </div>

        {/* Status Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#6B7280' }}>
            Status:
          </span>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.875rem' }}
          >
            <option value="all">All Statuses</option>
            <option value="processed">Processed</option>
            <option value="ocr_required">OCR Required</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* Format Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#6B7280' }}>
            Format:
          </span>
          <select
            value={sourceTypeFilter}
            onChange={(e) => {
              setSourceTypeFilter(e.target.value);
              setPage(1);
            }}
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.875rem' }}
          >
            <option value="all">All Formats</option>
            <option value="pdf">PDF</option>
            <option value="txt">Text (.txt)</option>
            <option value="markdown">Markdown (.md)</option>
          </select>
        </div>
      </Card>

      {/* Main Table */}
      <Card padding="none" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '1.5rem' }}>
            <TableSkeleton rows={6} />
          </div>
        ) : filteredDocs.length === 0 ? (
          <div style={{ padding: '2rem' }}>
            <EmptyState
              title="No documents matching filters"
              description="Try adjusting your status or format filters, or upload a new property document."
              actionText="Upload Document"
              onAction={handleOpenUpload}
            />
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr
                  style={{
                    backgroundColor: '#FAF8F5',
                    borderBottom: '1px solid #F0EDE6',
                    color: '#6B7280',
                    fontSize: '0.775rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                  }}
                >
                  <th style={{ padding: '0.85rem 1.25rem' }}>Document</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Type</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Extracted Chars</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Chunks</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Uploaded</th>
                  <th style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => (
                  <tr
                    key={doc.document_id}
                    style={{
                      borderBottom: '1px solid #FAF8F5',
                      transition: 'background-color 0.15s ease',
                      cursor: 'pointer',
                    }}
                    onClick={() => onNavigate('doc-detail', { docId: doc.document_id })}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FCFAF7')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '1rem 1.25rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                          style={{
                            width: '34px',
                            height: '34px',
                            borderRadius: '8px',
                            backgroundColor: '#EDE9FE',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#6D28D9',
                          }}
                        >
                          <FileText size={17} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: '#18181B' }}>
                            {doc.filename}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#9CA3AF', fontFamily: 'monospace' }}>
                            {doc.document_id.substring(0, 16)}...
                          </div>
                        </div>
                      </div>
                    </td>

                    <td style={{ padding: '1rem' }}>
                      <SourceTypeBadge type={doc.source_type} />
                    </td>

                    <td style={{ padding: '1rem' }}>
                      <StatusBadge status={doc.status} />
                    </td>

                    <td style={{ padding: '1rem', color: '#4B5563', fontWeight: 500 }}>
                      {doc.extracted_characters.toLocaleString()}
                    </td>

                    <td style={{ padding: '1rem', color: '#4B5563', fontWeight: 600 }}>
                      {doc.chunk_count}
                    </td>

                    <td style={{ padding: '1rem', color: '#6B7280', fontSize: '0.8125rem' }}>
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}
                    </td>

                    <td
                      style={{ padding: '1rem 1.25rem', textAlign: 'right' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.5rem' }}>
                        <button
                          onClick={() => onNavigate('doc-detail', { docId: doc.document_id })}
                          className="btn-outline"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.775rem' }}
                          title="Inspect chunks and metadata"
                        >
                          <Eye size={14} color="#6D28D9" />
                          <span>Inspect</span>
                        </button>

                        <button
                          onClick={() => onNavigate('ask', { docId: doc.document_id })}
                          className="btn-outline"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.775rem' }}
                          title="Ask question about this document"
                        >
                          <MessageSquareText size={14} color="#16A34A" />
                          <span>Ask AI</span>
                        </button>

                        <button
                          onClick={() => setDeletingDoc(doc)}
                          className="btn-danger"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.775rem' }}
                          title="Delete document"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1rem 1.5rem',
            backgroundColor: '#FAF8F5',
            borderTop: '1px solid #F0EDE6',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: '#6B7280' }}>
            Showing page <strong>{page}</strong> of <strong>{totalPages || 1}</strong> ({total} total documents)
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="btn-outline"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </button>

            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="btn-outline"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </Card>

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="Upload Property Document"
        subtitle="Ingest PDF, TXT, or Markdown documents with automatic chunking and vector storage."
        maxWidth="700px"
      >
        <UploadZone
          onUploadSuccess={() => {
            setIsUploadOpen(false);
            fetchDocuments();
          }}
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingDoc}
        onClose={() => !isDeleting && setDeletingDoc(null)}
        title="Delete Document"
        subtitle="Permanent removal of document record and vector embeddings."
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <p style={{ fontSize: '0.925rem', color: '#374151', lineHeight: 1.5 }}>
            Are you sure you want to permanently delete{' '}
            <strong>"{deletingDoc?.filename}"</strong>?
          </p>

          <div
            style={{
              backgroundColor: '#FEF2F2',
              border: '1px solid #FCA5A5',
              borderRadius: '10px',
              padding: '0.75rem 1rem',
              fontSize: '0.8125rem',
              color: '#991B1B',
            }}
          >
            This action cascades and deletes all associated chunks and vector embeddings from PostgreSQL/pgvector.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              className="btn-outline"
              disabled={isDeleting}
              onClick={() => setDeletingDoc(null)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-danger"
              disabled={isDeleting}
              onClick={handleDeleteConfirm}
            >
              {isDeleting ? 'Deleting...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
