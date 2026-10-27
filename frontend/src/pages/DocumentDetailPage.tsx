import React, { useEffect, useState, useCallback } from 'react';
import {
  ArrowLeft,
  FileText,
  Copy,
  Check,
  MessageSquareText,
  Trash2,
  Lock,
  Unlock,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { Card } from '../components/common/Card';
import { StatusBadge, SourceTypeBadge } from '../components/common/Badge';
import { Skeleton, TableSkeleton } from '../components/common/Skeleton';
import { Modal } from '../components/common/Modal';
import { documentsApi } from '../api/documents';
import { useToast } from '../components/common/Toast';
import type { DocumentDetailResponse, DocumentChunkSummary } from '../api/types';

interface DocumentDetailPageProps {
  documentId: string;
  onBack: () => void;
  onAskDoc: (docId: string) => void;
}

export const DocumentDetailPage: React.FC<DocumentDetailPageProps> = ({
  documentId,
  onBack,
  onAskDoc,
}) => {
  const [doc, setDoc] = useState<DocumentDetailResponse | null>(null);
  const [chunks, setChunks] = useState<DocumentChunkSummary[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [chunkPage, setChunkPage] = useState<number>(1);
  const [chunkPageSize] = useState<number>(10);
  const [chunkTotalPages, setChunkTotalPages] = useState<number>(1);
  const [includeText, setIncludeText] = useState<boolean>(true);

  const [loadingDoc, setLoadingDoc] = useState<boolean>(true);
  const [loadingChunks, setLoadingChunks] = useState<boolean>(true);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { showSuccess, showError } = useToast();

  const fetchDocument = useCallback(async () => {
    try {
      setLoadingDoc(true);
      const data = await documentsApi.get(documentId);
      setDoc(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve document details';
      showError(msg);
    } finally {
      setLoadingDoc(false);
    }
  }, [documentId, showError]);

  const fetchChunks = useCallback(async () => {
    try {
      setLoadingChunks(true);
      const res = await documentsApi.getChunks(documentId, {
        page: chunkPage,
        page_size: chunkPageSize,
        include_text: includeText,
      });
      setChunks(res.items || []);
      setTotalChunks(res.total || 0);
      setChunkTotalPages(res.total_pages || 1);
    } catch (err: unknown) {
      console.warn('Failed to load chunks:', err);
    } finally {
      setLoadingChunks(false);
    }
  }, [documentId, chunkPage, chunkPageSize, includeText]);

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  useEffect(() => {
    fetchChunks();
  }, [fetchChunks]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showSuccess('Copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      await documentsApi.delete(documentId);
      showSuccess('Document deleted successfully');
      setShowDeleteModal(false);
      onBack();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Delete failed';
      showError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  if (loadingDoc && !doc) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <button onClick={onBack} className="btn-outline" style={{ alignSelf: 'flex-start' }}>
          <ArrowLeft size={16} />
          <span>Back to Documents</span>
        </button>
        <Card padding="lg">
          <Skeleton width="40%" height="32px" style={{ marginBottom: '1rem' }} />
          <Skeleton width="70%" height="20px" style={{ marginBottom: '1.5rem' }} />
          <TableSkeleton rows={4} />
        </Card>
      </div>
    );
  }

  if (!doc) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <button onClick={onBack} className="btn-outline" style={{ alignSelf: 'flex-start' }}>
          <ArrowLeft size={16} />
          <span>Back to Documents</span>
        </button>
        <Card padding="lg" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
          <AlertTriangle size={36} color="#DC2626" style={{ margin: '0 auto 1rem auto' }} />
          <h2 style={{ fontSize: '1.35rem', marginBottom: '0.5rem' }}>Document Not Found</h2>
          <p style={{ color: '#6B7280', marginBottom: '1.5rem' }}>
            The document ID "{documentId}" could not be located in the database.
          </p>
          <button onClick={onBack} className="btn-primary">
            Return to Documents List
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Top Navigation & Action Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <button onClick={onBack} className="btn-outline" style={{ display: 'inline-flex', gap: '0.5rem' }}>
          <ArrowLeft size={16} />
          <span>Back to Documents</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => onAskDoc(doc.document_id)}
            className="btn-primary"
            style={{ backgroundColor: '#7C3AED' }}
          >
            <MessageSquareText size={16} />
            <span>Ask AI About This</span>
          </button>

          <button
            onClick={() => setShowDeleteModal(true)}
            className="btn-danger"
          >
            <Trash2 size={16} />
            <span>Delete Document</span>
          </button>
        </div>
      </div>

      {/* Main Document Details Card */}
      <Card padding="lg">
        {/* Title & Badges */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            marginBottom: '1.5rem',
            paddingBottom: '1.25rem',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                backgroundColor: '#EDE9FE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6D28D9',
                flexShrink: 0,
              }}
            >
              <FileText size={24} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#18181B' }}>
                {doc.filename}
              </h1>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.8125rem',
                  color: '#6B7280',
                  marginTop: '0.2rem',
                }}
              >
                <span>ID: {doc.document_id}</span>
                <button
                  type="button"
                  onClick={() => handleCopy(doc.document_id, 'doc_id')}
                  style={{ color: '#7C3AED', padding: '0.2rem' }}
                  title="Copy Document ID"
                >
                  {copiedId === 'doc_id' ? <Check size={13} color="#16A34A" /> : <Copy size={13} />}
                </button>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <SourceTypeBadge type={doc.source_type} />
            <StatusBadge status={doc.status} />
          </div>
        </div>

        {/* Status Explanation / Warning Alert */}
        {doc.detail && (
          <div
            style={{
              backgroundColor: doc.status === 'ocr_required' ? '#FEF3C7' : '#FEE2E2',
              border: `1px solid ${doc.status === 'ocr_required' ? '#FDE047' : '#FCA5A5'}`,
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
            }}
          >
            <AlertTriangle size={18} color={doc.status === 'ocr_required' ? '#B45309' : '#DC2626'} />
            <span style={{ fontSize: '0.875rem', color: doc.status === 'ocr_required' ? '#92400E' : '#991B1B' }}>
              <strong>Processing Notice:</strong> {doc.detail}
            </span>
          </div>
        )}

        {/* Metadata Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            gap: '1rem',
          }}
        >
          <div style={{ backgroundColor: '#FAF8F5', padding: '1rem', borderRadius: '12px', border: '1px solid #F0EDE6' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Total Chunks
            </span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#18181B', marginTop: '0.2rem' }}>
              {doc.chunk_count}
            </div>
          </div>

          <div style={{ backgroundColor: '#FAF8F5', padding: '1rem', borderRadius: '12px', border: '1px solid #F0EDE6' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Extracted Chars
            </span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#18181B', marginTop: '0.2rem' }}>
              {doc.extracted_characters.toLocaleString()}
            </div>
          </div>

          <div style={{ backgroundColor: '#FAF8F5', padding: '1rem', borderRadius: '12px', border: '1px solid #F0EDE6' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Page Count
            </span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#18181B', marginTop: '0.2rem' }}>
              {doc.page_count !== null && doc.page_count !== undefined ? doc.page_count : 'N/A'}
            </div>
          </div>

          <div style={{ backgroundColor: '#FAF8F5', padding: '1rem', borderRadius: '12px', border: '1px solid #F0EDE6' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase' }}>
              Ingested At
            </span>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#18181B', marginTop: '0.4rem' }}>
              {doc.created_at ? new Date(doc.created_at).toLocaleString() : '—'}
            </div>
          </div>
        </div>

        {/* SHA-256 fingerprint */}
        <div
          style={{
            marginTop: '1.25rem',
            padding: '0.75rem 1rem',
            backgroundColor: '#F3F4F6',
            borderRadius: '10px',
            fontSize: '0.8125rem',
            color: '#4B5563',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontFamily: 'monospace' }}>
            <strong>SHA-256:</strong> {doc.content_sha256}
          </span>
          <button
            type="button"
            onClick={() => handleCopy(doc.content_sha256, 'sha')}
            style={{ color: '#7C3AED', padding: '0.2rem' }}
            title="Copy SHA-256"
          >
            {copiedId === 'sha' ? <Check size={14} color="#16A34A" /> : <Copy size={14} />}
          </button>
        </div>
      </Card>

      {/* Chunks Inspection Section */}
      <Card padding="lg">
        {/* Chunks Header with Content Protection Toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            marginBottom: '1.5rem',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={20} color="#7C3AED" />
              <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#18181B' }}>
                Chunk Metadata & Content ({totalChunks})
              </h2>
            </div>
            <p style={{ fontSize: '0.875rem', color: '#6B7280', marginTop: '0.2rem' }}>
              Inspect chunk boundaries, PDF page mappings, and embeddings.
            </p>
          </div>

          {/* Include text toggle */}
          <button
            onClick={() => setIncludeText(!includeText)}
            className="btn-outline"
            style={{
              borderColor: includeText ? '#7C3AED' : '#D1D5DB',
              backgroundColor: includeText ? '#FAF8FF' : '#FFFFFF',
              color: includeText ? '#6D28D9' : '#4B5563',
            }}
          >
            {includeText ? <Unlock size={15} color="#7C3AED" /> : <Lock size={15} />}
            <span>{includeText ? 'Chunk Text Visible' : 'Text Protected (Off)'}</span>
          </button>
        </div>

        {/* Chunks List */}
        {loadingChunks ? (
          <TableSkeleton rows={4} />
        ) : chunks.length === 0 ? (
          <div
            style={{
              padding: '2rem',
              textAlign: 'center',
              color: '#6B7280',
              backgroundColor: '#FAF8F5',
              borderRadius: '12px',
            }}
          >
            No chunks stored for this document.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {chunks.map((chunk) => (
              <div
                key={chunk.chunk_id}
                style={{
                  borderRadius: '14px',
                  border: '1px solid #F0EDE6',
                  backgroundColor: '#FFFFFF',
                  padding: '1.15rem',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
                }}
              >
                {/* Chunk Header */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '0.65rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span
                      style={{
                        backgroundColor: '#EDE9FE',
                        color: '#6D28D9',
                        fontWeight: 700,
                        fontSize: '0.785rem',
                        padding: '0.2rem 0.55rem',
                        borderRadius: '6px',
                      }}
                    >
                      Chunk #{chunk.chunk_index}
                    </span>
                    <span style={{ fontSize: '0.8125rem', color: '#6B7280', fontFamily: 'monospace' }}>
                      {chunk.chunk_id}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.8125rem', color: '#6B7280' }}>
                    {chunk.page_number && (
                      <span style={{ backgroundColor: '#FAF8F5', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                        Page {chunk.page_number}
                      </span>
                    )}
                    {chunk.start_offset !== null && chunk.end_offset !== null && (
                      <span style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>
                        Offsets: {chunk.start_offset}–{chunk.end_offset}
                      </span>
                    )}
                  </div>
                </div>

                {/* Chunk text content */}
                {includeText ? (
                  <div
                    style={{
                      backgroundColor: '#FAF8F5',
                      padding: '0.85rem 1rem',
                      borderRadius: '8px',
                      fontSize: '0.875rem',
                      color: '#374151',
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      position: 'relative',
                    }}
                  >
                    {chunk.text || <span style={{ color: '#9CA3AF' }}>No text returned</span>}
                    {chunk.text && (
                      <button
                        onClick={() => handleCopy(chunk.text || '', chunk.chunk_id)}
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          backgroundColor: '#FFFFFF',
                          border: '1px solid #E5E7EB',
                          borderRadius: '6px',
                          padding: '0.25rem 0.45rem',
                          color: '#6B7280',
                        }}
                        title="Copy chunk text"
                      >
                        {copiedId === chunk.chunk_id ? <Check size={13} color="#16A34A" /> : <Copy size={13} />}
                      </button>
                    )}
                  </div>
                ) : (
                  <div
                    style={{
                      backgroundColor: '#F3F4F6',
                      padding: '0.65rem 1rem',
                      borderRadius: '8px',
                      fontSize: '0.8125rem',
                      color: '#6B7280',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <Lock size={14} />
                    <span>Chunk text hidden by content protection policy. Toggle above to inspect text.</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Chunks Pagination */}
        {chunkTotalPages > 1 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: '1.25rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border-light)',
            }}
          >
            <span style={{ fontSize: '0.8125rem', color: '#6B7280' }}>
              Chunk page {chunkPage} of {chunkTotalPages}
            </span>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                onClick={() => setChunkPage((p) => Math.max(1, p - 1))}
                disabled={chunkPage <= 1}
                className="btn-outline"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
              >
                <ChevronLeft size={16} />
                <span>Previous</span>
              </button>

              <button
                onClick={() => setChunkPage((p) => Math.min(chunkTotalPages, p + 1))}
                disabled={chunkPage >= chunkTotalPages}
                className="btn-outline"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
              >
                <span>Next</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => !isDeleting && setShowDeleteModal(false)}
        title="Delete Document"
        subtitle="This action will permanently delete the document record, chunks, and embeddings."
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <p style={{ fontSize: '0.925rem', color: '#374151', lineHeight: 1.5 }}>
            Are you sure you want to permanently delete <strong>"{doc.filename}"</strong>?
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
            This action cascades and completely deletes all {doc.chunk_count} chunks and vector embeddings.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              className="btn-outline"
              disabled={isDeleting}
              onClick={() => setShowDeleteModal(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-danger"
              disabled={isDeleting}
              onClick={handleDelete}
            >
              {isDeleting ? 'Deleting...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
