import { useState, useEffect } from 'react';
import {
  Sparkles,
  Send,
  Loader2,
  FileText,
  Sliders,
  History,
} from 'lucide-react';
import { Card } from '../components/common/Card';
import { AnswerView } from '../components/rag/AnswerView';
import { Skeleton } from '../components/common/Skeleton';
import { documentsApi } from '../api/documents';
import { ragApi } from '../api/rag';
import { useToast } from '../components/common/Toast';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import type {
  DocumentSummary,
  RAGResponse,
  RetrievalMode,
  RAGQuestionRequest,
} from '../api/types';

interface AskQuestionsPageProps {
  initialQuestion?: string;
  initialDocId?: string;
  initialTopK?: number;
  onInspectDocument?: (docId: string) => void;
}

export const AskQuestionsPage: React.FC<AskQuestionsPageProps> = ({
  initialQuestion = '',
  initialDocId = '',
  initialTopK = 5,
  onInspectDocument,
}) => {
  const { isAuthenticated, openAuthModal } = useAuth();
  const [question, setQuestion] = useState<string>(initialQuestion);
  const [selectedDocId, setSelectedDocId] = useState<string>(initialDocId);
  const [mode, setMode] = useState<RetrievalMode>('semantic');
  const [topK, setTopK] = useState<number>(initialTopK);
  const [minScore, setMinScore] = useState<string>(''); // empty or number
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(false);

  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [currentResponse, setCurrentResponse] = useState<RAGResponse | null>(null);
  const [history, setHistory] = useState<Array<{ question: string; response: RAGResponse }>>([]);

  const { showError, showSuccess } = useToast();

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        setIsLoadingDocs(true);
        const res = await documentsApi.list({ page: 1, page_size: 100 });
        setDocuments(res.items || []);
      } catch (err: unknown) {
        console.warn('Could not load documents for filter dropdown:', err);
      } finally {
        setIsLoadingDocs(false);
      }
    };
    fetchDocs();
  }, [isAuthenticated]);

  // Auto-submit if initial question provided
  useEffect(() => {
    if (initialQuestion && !currentResponse && !isAsking && isAuthenticated) {
      handleAsk(initialQuestion, initialDocId, initialTopK);
    }
  }, [initialQuestion, isAuthenticated]);

  const handleAsk = async (
    qToAsk: string,
    docIdFilter: string = selectedDocId,
    kLimit: number = topK
  ) => {
    const trimmed = qToAsk.trim();
    if (!trimmed) return;

    if (!isAuthenticated) {
      showError('Please sign in to ask questions against your documents.');
      openAuthModal('login');
      return;
    }

    try {
      setIsAsking(true);
      const payload: RAGQuestionRequest = {
        question: trimmed,
        mode,
        top_k: kLimit,
      };

      if (docIdFilter) {
        payload.document_id = docIdFilter;
      }

      if (minScore.trim()) {
        const parsed = parseFloat(minScore);
        if (!isNaN(parsed)) {
          payload.min_score = parsed;
        }
      }

      const res = await ragApi.ask(payload);
      setCurrentResponse(res);
      setHistory((prev) => [{ question: trimmed, response: res }, ...prev.slice(0, 8)]);
      showSuccess('Grounded answer generated');
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        showError('Session expired. Please sign in again.');
        openAuthModal('login');
        return;
      }
      const msg = err instanceof Error ? err.message : 'RAG query failed';
      showError(msg);
    } finally {
      setIsAsking(false);
    }
  };

  const sampleQuestions = [
    'What are the key terms and obligations of the lease agreement?',
    'What is the total property tax assessed and due date?',
    'Summarize any environmental hazards or inspection issues reported.',
    'Are there any zoning restrictions, easements, or covenants recorded?',
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Page Title */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Sparkles size={28} color="#7C3AED" />
          <h1 style={{ fontSize: '2.1rem', fontWeight: 800, color: '#18181B' }}>
            Ask Questions with AI
          </h1>
        </div>
        <p style={{ fontSize: '0.95rem', color: '#6B7280', marginTop: '0.2rem' }}>
          Grounded property intelligence with verifiable citations tied to stored document chunks.
        </p>
      </div>

      {/* Main Question & Configuration Form */}
      <Card padding="lg">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk(question);
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
        >
          {/* Question Textarea */}
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: 700,
                color: '#18181B',
                marginBottom: '0.5rem',
              }}
            >
              Your Property Question
            </label>
            <div style={{ position: 'relative' }}>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. What are the boundary conditions and rights of way described in the sale deed?"
                rows={3}
                style={{
                  width: '100%',
                  padding: '1rem 4rem 1rem 1rem',
                  borderRadius: '16px',
                  border: '1.5px solid #DDD6FE',
                  backgroundColor: '#FAF8FF',
                  fontSize: '1rem',
                  color: '#18181B',
                  lineHeight: 1.5,
                }}
              />
              <button
                type="submit"
                disabled={isAsking || !question.trim()}
                className="btn-purple"
                style={{
                  position: 'absolute',
                  right: '12px',
                  bottom: '12px',
                  padding: '0.6rem 1.15rem',
                  borderRadius: '12px',
                }}
              >
                {isAsking ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <>
                    <Send size={16} />
                    <span>Ask AI</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick suggestions pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', color: '#6B7280', fontWeight: 600 }}>
              Suggestions:
            </span>
            {sampleQuestions.map((sq, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setQuestion(sq);
                  handleAsk(sq);
                }}
                style={{
                  backgroundColor: '#FAF8F5',
                  border: '1px solid #E5E7EB',
                  padding: '0.3rem 0.65rem',
                  borderRadius: '9999px',
                  fontSize: '0.785rem',
                  color: '#4B5563',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#EDE9FE';
                  e.currentTarget.style.color = '#6D28D9';
                  e.currentTarget.style.borderColor = '#DDD6FE';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#FAF8F5';
                  e.currentTarget.style.color = '#4B5563';
                  e.currentTarget.style.borderColor = '#E5E7EB';
                }}
              >
                {sq}
              </button>
            ))}
          </div>

          {/* Core Retrieval Controls Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--border-light)',
            }}
          >
            {/* Filter by Document */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: '220px' }}>
              <FileText size={16} color="#7C3AED" />
              <select
                disabled={isLoadingDocs}
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                style={{
                  padding: '0.45rem 0.75rem',
                  fontSize: '0.875rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '10px',
                }}
              >
                <option value="">All Uploaded Documents</option>
                {documents.map((d) => (
                  <option key={d.document_id} value={d.document_id}>
                    {d.filename}
                  </option>
                ))}
              </select>
            </div>

            {/* Retrieval Mode */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#4B5563' }}>
                Mode:
              </span>
              <div
                style={{
                  display: 'flex',
                  backgroundColor: '#FAF8F5',
                  borderRadius: 'var(--radius-full)',
                  padding: '3px',
                  border: '1px solid #E5E7EB',
                }}
              >
                <button
                  type="button"
                  onClick={() => setMode('semantic')}
                  style={{
                    padding: '0.3rem 0.85rem',
                    borderRadius: '9999px',
                    fontSize: '0.785rem',
                    fontWeight: 700,
                    backgroundColor: mode === 'semantic' ? '#7C3AED' : 'transparent',
                    color: mode === 'semantic' ? '#FFFFFF' : '#6B7280',
                  }}
                >
                  Semantic (Cosine)
                </button>
                <button
                  type="button"
                  onClick={() => setMode('hybrid')}
                  style={{
                    padding: '0.3rem 0.85rem',
                    borderRadius: '9999px',
                    fontSize: '0.785rem',
                    fontWeight: 700,
                    backgroundColor: mode === 'hybrid' ? '#7C3AED' : 'transparent',
                    color: mode === 'hybrid' ? '#FFFFFF' : '#6B7280',
                  }}
                >
                  Hybrid (RRF)
                </button>
              </div>
            </div>

            {/* Top K */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#4B5563' }}>
                Top K:
              </span>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                style={{ padding: '0.4rem 0.65rem', fontSize: '0.875rem' }}
              >
                <option value={3}>3 sources</option>
                <option value={5}>5 sources (default)</option>
                <option value={8}>8 sources</option>
                <option value={12}>12 sources</option>
              </select>
            </div>

            {/* Toggle advanced */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                fontSize: '0.8125rem',
                color: '#6D28D9',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontWeight: 600,
              }}
            >
              <Sliders size={14} />
              <span>{showAdvanced ? 'Hide Advanced' : 'Advanced Filters'}</span>
            </button>
          </div>

          {/* Advanced Section */}
          {showAdvanced && (
            <div
              style={{
                backgroundColor: '#FAF8F5',
                borderRadius: '12px',
                padding: '1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '1.5rem',
                border: '1px solid #F0EDE6',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <label style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#374151' }}>
                  Min Semantic Score Threshold:
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="-1.0"
                  max="1.0"
                  placeholder="e.g. 0.35"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                  style={{ width: '100px', padding: '0.35rem 0.6rem', fontSize: '0.8125rem' }}
                />
                <span style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>(-1.0 to 1.0)</span>
              </div>
            </div>
          )}
        </form>
      </Card>

      {/* Answer View or Loading Skeleton */}
      {isAsking && (
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <Loader2 size={24} className="animate-spin" color="#7C3AED" />
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#18181B' }}>
              Retrieving Evidence & Grounding Answer...
            </h3>
          </div>
          <Skeleton width="90%" height="22px" style={{ marginBottom: '0.75rem' }} />
          <Skeleton width="100%" height="90px" style={{ marginBottom: '1.5rem' }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
            <Skeleton height="120px" borderRadius="16px" />
            <Skeleton height="120px" borderRadius="16px" />
          </div>
        </Card>
      )}

      {currentResponse && !isAsking && (
        <AnswerView
          response={currentResponse}
          onInspectDocument={onInspectDocument}
        />
      )}

      {/* Query History */}
      {history.length > 1 && (
        <Card padding="md">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem' }}>
            <History size={18} color="#6B7280" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#18181B' }}>
              Previous Questions in this Session
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {history.slice(1).map((item, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setQuestion(item.question);
                  setCurrentResponse(item.response);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  borderRadius: '10px',
                  backgroundColor: '#FAF8F5',
                  border: '1px solid #F0EDE6',
                  textAlign: 'left',
                  width: '100%',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#EDE9FE')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FAF8F5')}
              >
                <span style={{ fontSize: '0.875rem', color: '#1F2937', fontWeight: 600 }}>
                  {item.question}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                  {item.response.citations.length} citations
                </span>
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
