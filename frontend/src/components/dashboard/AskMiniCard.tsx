import React, { useState } from 'react';
import { Sparkles, Send, FileText, Layers, ArrowRight } from 'lucide-react';
import { Card } from '../common/Card';
import type { DocumentSummary } from '../../api/types';

interface AskMiniCardProps {
  documents: DocumentSummary[];
  onAsk: (question: string, documentId?: string | null, topK?: number) => void;
}

export const AskMiniCard: React.FC<AskMiniCardProps> = ({ documents, onAsk }) => {
  const [question, setQuestion] = useState('');
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [topK, setTopK] = useState<number>(5);

  const sampleQuestions = [
    'What are the key terms of the lease?',
    'What are the property tax details?',
    'Summarize the inspection report.',
    'Are there any restrictions on this property?',
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    onAsk(question.trim(), selectedDocId || null, topK);
  };

  const handleSelectSample = (sample: string) => {
    setQuestion(sample);
    onAsk(sample, selectedDocId || null, topK);
  };

  return (
    <Card padding="md" style={{ position: 'relative' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.35rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <Sparkles size={20} color="#7C3AED" />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#18181B' }}>
            Ask a question
          </h3>
        </div>
        <span className="badge badge-rag" style={{ fontSize: '0.75rem' }}>
          <span style={{ fontSize: '0.9rem' }}>●</span> RAG Powered
        </span>
      </div>

      <p
        style={{
          fontSize: '0.875rem',
          color: '#6B7280',
          marginBottom: '1rem',
        }}
      >
        Get evidence-grounded answers from your documents.
      </p>

      {/* Input container with send button */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '0.85rem' }}>
        <div
          style={{
            position: 'relative',
            borderRadius: '16px',
            border: '1px solid #E5E7EB',
            backgroundColor: '#FAF8F5',
            padding: '0.65rem 0.85rem',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
          }}
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder="Ask a question about your property documents..."
            rows={2}
            style={{
              width: '100%',
              border: 'none',
              background: 'transparent',
              resize: 'none',
              fontSize: '0.9375rem',
              color: '#18181B',
              paddingRight: '3.5rem',
            }}
          />

          <button
            type="submit"
            disabled={!question.trim()}
            style={{
              position: 'absolute',
              right: '10px',
              bottom: '10px',
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              backgroundColor: question.trim() ? '#7C3AED' : '#C4B5FD',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: question.trim() ? '0 2px 8px rgba(124, 58, 237, 0.35)' : 'none',
            }}
            aria-label="Submit question"
          >
            <Send size={18} />
          </button>
        </div>

        {/* Filter controls row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            marginTop: '0.75rem',
          }}
        >
          {/* Doc filter */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E5E7EB',
              borderRadius: 'var(--radius-md)',
              padding: '0.35rem 0.75rem',
            }}
          >
            <FileText size={15} color="#9CA3AF" />
            <select
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              style={{
                width: '100%',
                border: 'none',
                background: 'transparent',
                fontSize: '0.8125rem',
                color: '#374151',
                cursor: 'pointer',
              }}
            >
              <option value="">Filter by document (optional)</option>
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          </div>

          {/* Top K */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E5E7EB',
              borderRadius: 'var(--radius-md)',
              padding: '0.35rem 0.65rem',
            }}
          >
            <Layers size={14} color="#9CA3AF" />
            <span style={{ fontSize: '0.775rem', color: '#6B7280', whiteSpace: 'nowrap' }}>
              Top K:
            </span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              style={{
                border: 'none',
                background: 'transparent',
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: '#1F2937',
                cursor: 'pointer',
              }}
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={8}>8</option>
              <option value={10}>10</option>
            </select>
          </div>
        </div>
      </form>

      {/* Try these questions */}
      <div style={{ marginTop: '1rem' }}>
        <div
          style={{
            fontSize: '0.8125rem',
            fontWeight: 700,
            color: '#1F2937',
            marginBottom: '0.5rem',
          }}
        >
          Try these questions:
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {sampleQuestions.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSelectSample(sample)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.45rem 0.65rem',
                borderRadius: '8px',
                backgroundColor: '#FAF8F5',
                color: '#4B5563',
                fontSize: '0.8125rem',
                textAlign: 'left',
                border: '1px solid #F0EDE6',
                width: '100%',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#EDE9FE';
                e.currentTarget.style.color = '#6D28D9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#FAF8F5';
                e.currentTarget.style.color = '#4B5563';
              }}
            >
              <ArrowRight size={13} color="#7C3AED" />
              <span>{sample}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Handwritten Annotation at bottom right */}
      <div
        style={{
          position: 'absolute',
          bottom: '15px',
          right: '-15px',
          transform: 'translateX(100%)',
          display: 'none', // Shown in wide desktop or positioned inside
        }}
      />
    </Card>
  );
};
