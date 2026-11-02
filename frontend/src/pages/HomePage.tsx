import React, { useEffect, useState, useCallback } from 'react';
import { HeroBanner } from '../components/dashboard/HeroBanner';
import { PortfolioDashboard } from '../components/dashboard/PortfolioDashboard';
import { UploadZone } from '../components/dashboard/UploadZone';
import { AskMiniCard } from '../components/dashboard/AskMiniCard';
import { RecentDocs } from '../components/dashboard/RecentDocs';
import { EvidenceCard } from '../components/dashboard/EvidenceCard';
import { Modal } from '../components/common/Modal';
import { documentsApi } from '../api/documents';
import { propertiesApi } from '../api/properties';
import { useToast } from '../components/common/Toast';
import { useAuth } from '../context/AuthContext';
import type { DocumentSummary, IngestResponse, PortfolioStatsResponse } from '../api/types';

interface HomePageProps {
  onNavigate: (page: string, params?: { docId?: string; question?: string; topK?: number; propertyId?: string }) => void;
  searchTerm?: string;
}

export const HomePage: React.FC<HomePageProps> = ({ onNavigate, searchTerm = '' }) => {
  const { isAuthenticated } = useAuth();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [portfolioStats, setPortfolioStats] = useState<PortfolioStatsResponse | null>(null);
  const [loadingPortfolio, setLoadingPortfolio] = useState<boolean>(true);
  const [deletingDoc, setDeletingDoc] = useState<DocumentSummary | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const { showSuccess, showError } = useToast();

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await documentsApi.list({ page: 1, page_size: 50 });
      setDocuments(data.items || []);
    } catch (err: unknown) {
      console.warn('Backend fetch error:', err);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPortfolioStats = useCallback(async () => {
    try {
      setLoadingPortfolio(true);
      const stats = await propertiesApi.getPortfolioStats();
      setPortfolioStats(stats);
    } catch (err: unknown) {
      console.warn('Portfolio stats fetch error:', err);
      setPortfolioStats(null);
    } finally {
      setLoadingPortfolio(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    fetchPortfolioStats();
  }, [fetchDashboardData, fetchPortfolioStats, isAuthenticated]);

  const handleUploadSuccess = (_newDoc: IngestResponse) => {
    fetchDashboardData();
    fetchPortfolioStats();
  };

  const handleAskQuestion = (question: string, docId?: string | null, topK?: number) => {
    onNavigate('ask', { question, docId: docId || undefined, topK: topK || 5 });
  };

  const handleDeleteConfirm = async () => {
    if (!deletingDoc) return;
    try {
      setIsDeleting(true);
      await documentsApi.delete(deletingDoc.document_id);
      showSuccess(`Document "${deletingDoc.filename}" deleted successfully.`);
      setDeletingDoc(null);
      fetchDashboardData();
      fetchPortfolioStats();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete document.';
      showError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Filter documents if search term is active
  const displayedDocs = searchTerm.trim()
    ? documents.filter((d) =>
        d.filename.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : documents;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Hero Welcome Banner */}
      <HeroBanner />

      {/* Portfolio Intelligence Dashboard */}
      <PortfolioDashboard
        stats={portfolioStats}
        loading={loadingPortfolio}
        onRefresh={fetchPortfolioStats}
        onNavigate={onNavigate}
      />

      {/* Mid Row: Upload Zone (left 60%) + Ask a Question (right 40%) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.45fr) minmax(0, 1fr)',
          gap: '1.5rem',
          alignItems: 'start',
        }}
      >
        <UploadZone onUploadSuccess={handleUploadSuccess} />
        <AskMiniCard documents={documents} onAsk={handleAskQuestion} />
      </div>

      {/* Bottom Row: Recent Documents (left 65%) + Evidence First Card (right 35%) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)',
          gap: '1.5rem',
          alignItems: 'start',
        }}
      >
        <RecentDocs
          documents={displayedDocs}
          loading={loading}
          onViewAll={() => onNavigate('documents')}
          onViewDetails={(id) => onNavigate('doc-detail', { docId: id })}
          onAskDoc={(id) => onNavigate('ask', { docId: id })}
          onDeleteDoc={(doc) => setDeletingDoc(doc)}
        />
        <EvidenceCard />
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingDoc}
        onClose={() => !isDeleting && setDeletingDoc(null)}
        title="Delete Document"
        subtitle="This action will permanently remove the document, its chunks, and vector embeddings."
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <p style={{ fontSize: '0.925rem', color: '#374151', lineHeight: 1.5 }}>
            Are you sure you want to delete{' '}
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
            Warning: Associated embeddings and retrieval indices will be deleted. Any RAG answers referencing this document will no longer have access to its excerpts.
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
