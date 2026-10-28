import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, BookOpen, AlertTriangle, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { Card } from '../common/Card';
import { EvidenceStatusBadge } from '../common/Badge';
import { CitationCard } from './CitationCard';
import type { RAGResponse, ClaimVerificationStatus } from '../../api/types';

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

  const renderClaimStatusBadge = (status: ClaimVerificationStatus) => {
    switch (status) {
      case 'supported':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', fontWeight: 700, color: '#047857', backgroundColor: '#D1FAE5', padding: '0.2rem 0.55rem', borderRadius: '9999px', border: '1px solid #A7F3D0' }}>
            <CheckCircle2 size={13} /> Verified Support
          </span>
        );
      case 'unsupported':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', fontWeight: 700, color: '#B91C1C', backgroundColor: '#FEE2E2', padding: '0.2rem 0.55rem', borderRadius: '9999px', border: '1px solid #FECACA' }}>
            <XCircle size={13} /> Unsupported Claim
          </span>
        );
      case 'contradicted':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', fontWeight: 700, color: '#991B1B', backgroundColor: '#FFE4E6', padding: '0.2rem 0.55rem', borderRadius: '9999px', border: '1px solid #FDA4AF' }}>
            <AlertTriangle size={13} /> Contradicted Claim
          </span>
        );
      case 'unestablished':
      default:
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', fontWeight: 700, color: '#4B5563', backgroundColor: '#F3F4F6', padding: '0.2rem 0.55rem', borderRadius: '9999px', border: '1px solid #E5E7EB' }}>
            <HelpCircle size={13} /> Unestablished
          </span>
        );
    }
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

        {/* Insufficient Evidence Explanations */}
        {response.insufficient_reasons && response.insufficient_reasons.length > 0 && (
          <div
            style={{
              backgroundColor: '#EFF6FF',
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              border: '1px solid #BFDBFE',
              marginBottom: '1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: '#1E40AF', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.35rem' }}>
              <HelpCircle size={16} />
              <span>Evidence Sufficiency Gaps</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8125rem', color: '#1E3A8A' }}>
              {response.insufficient_reasons.map((reason, idx) => (
                <li key={idx} style={{ marginTop: '0.2rem' }}>
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}

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
            stored chunk vectors. Claim-level entailment is rigorously verified.
          </span>
        </div>
      </Card>

      {/* Cross-Document Conflicts */}
      {response.conflicts && response.conflicts.length > 0 && (
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <AlertTriangle size={20} color="#DC2626" />
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#991B1B', margin: 0 }}>
              Cross-Document Conflicts Detected ({response.conflicts.length})
            </h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#6B7280', marginBottom: '1rem' }}>
            The retrieved documents contain conflicting factual claims. Both sources are preserved below for comparative review.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {response.conflicts.map((conflict, idx) => (
              <div
                key={idx}
                style={{
                  border: '1px solid #FECACA',
                  borderRadius: '12px',
                  backgroundColor: '#FFF5F5',
                  padding: '1rem',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#991B1B', marginBottom: '0.75rem' }}>
                  {conflict.contradiction_reason}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                  <div style={{ backgroundColor: '#FFFFFF', padding: '0.85rem', borderRadius: '8px', border: '1px solid #FCA5A5' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.8rem', color: '#B91C1C' }}>
                        Source [{conflict.source_a.citation_id}]: {conflict.source_a.filename}
                      </span>
                      {conflict.source_a.page_number && (
                        <span style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                          Page {conflict.source_a.page_number}
                        </span>
                      )}
                    </div>
                    <blockquote style={{ margin: 0, fontSize: '0.825rem', color: '#374151', fontStyle: 'italic', borderLeft: '3px solid #EF4444', paddingLeft: '0.5rem' }}>
                      &ldquo;{conflict.source_a.quote}&rdquo;
                    </blockquote>
                  </div>

                  <div style={{ backgroundColor: '#FFFFFF', padding: '0.85rem', borderRadius: '8px', border: '1px solid #FCA5A5' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.8rem', color: '#B91C1C' }}>
                        Source [{conflict.source_b.citation_id}]: {conflict.source_b.filename}
                      </span>
                      {conflict.source_b.page_number && (
                        <span style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                          Page {conflict.source_b.page_number}
                        </span>
                      )}
                    </div>
                    <blockquote style={{ margin: 0, fontSize: '0.825rem', color: '#374151', fontStyle: 'italic', borderLeft: '3px solid #EF4444', paddingLeft: '0.5rem' }}>
                      &ldquo;{conflict.source_b.quote}&rdquo;
                    </blockquote>
                  </div>
                </div>

                <div style={{ fontSize: '0.785rem', color: '#6B7280', fontStyle: 'italic' }}>
                  {conflict.resolution_note}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Claim-Level Evidence Verification Breakdown */}
      {response.claim_verifications && response.claim_verifications.length > 0 && (
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <ShieldCheck size={20} color="#059669" />
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#18181B', margin: 0 }}>
              Claim-Level Evidence Verification ({response.claim_verifications.length})
            </h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#6B7280', marginBottom: '1rem' }}>
            Each factual assertion is audited against cited source excerpts to verify semantic entailment and factual grounding.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {response.claim_verifications.map((claim, idx) => (
              <div
                key={idx}
                style={{
                  border: '1px solid var(--border-light)',
                  borderRadius: '12px',
                  padding: '0.9rem',
                  backgroundColor: claim.status === 'supported' ? '#F0FDF4' : claim.status === 'contradicted' ? '#FFF1F2' : '#F9FAFB',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {renderClaimStatusBadge(claim.status)}
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    {claim.cited_source_ids.map((srcId) => (
                      <button
                        key={srcId}
                        type="button"
                        onClick={() => handleCitationClick(srcId)}
                        style={{
                          fontSize: '0.725rem',
                          fontWeight: 700,
                          backgroundColor: '#EDE9FE',
                          color: '#6D28D9',
                          padding: '0.1rem 0.4rem',
                          borderRadius: '6px',
                          border: '1px solid #DDD6FE',
                          cursor: 'pointer',
                        }}
                      >
                        [{srcId}]
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#1F2937', marginBottom: '0.35rem' }}>
                  {claim.claim_text}
                </div>

                <div style={{ fontSize: '0.8125rem', color: '#4B5563' }}>
                  {claim.entailment_explanation}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

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

      {/* Mandatory Legal Disclaimer */}
      <div
        style={{
          border: '1px solid #E2E8F0',
          backgroundColor: '#F8FAFC',
          borderRadius: '12px',
          padding: '1rem 1.25rem',
          fontSize: '0.785rem',
          color: '#64748B',
          lineHeight: 1.5,
          textAlign: 'center',
        }}
      >
        <strong>Legal Due Diligence Notice:</strong>{' '}
        {response.legal_disclaimer ||
          'Automated verification is provided for informational due diligence and triage only. It does NOT constitute legal advice, a title insurance commitment, or a guarantee of clear property title, absence of liens, or marketability. Independent verification by a qualified real estate attorney is required.'}
      </div>
    </div>
  );
};

