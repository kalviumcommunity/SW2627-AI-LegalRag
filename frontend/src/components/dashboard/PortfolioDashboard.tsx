import React from 'react';
import {
  Building2,
  FileText,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Eye,
  RefreshCw,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { Card } from '../common/Card';
import type { PortfolioStatsResponse } from '../../api/types';

interface PortfolioDashboardProps {
  stats: PortfolioStatsResponse | null;
  loading: boolean;
  onRefresh: () => void;
  onNavigate: (page: string, params?: { docId?: string; propertyId?: string }) => void;
}

export const PortfolioDashboard: React.FC<PortfolioDashboardProps> = ({
  stats,
  loading,
  onRefresh,
  onNavigate,
}) => {
  const attentionItems = stats?.properties_requiring_attention || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header bar */}
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
          <h2
            style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              color: '#0F172A',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <Building2 size={22} color="#7C3AED" />
            Portfolio Due Diligence Overview
          </h2>
          <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: '0.25rem 0 0 0' }}>
            Aggregated intelligence, document compliance, and risk findings across your portfolio.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 0.875rem',
            fontSize: '0.8125rem',
            fontWeight: 600,
            borderRadius: '6px',
            border: '1px solid #CBD5E1',
            backgroundColor: '#FFFFFF',
            color: '#334155',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background-color 0.15s ease',
          }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh Stats
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* Total Properties */}
        <Card padding="sm">
          <div
            onClick={() => onNavigate('properties')}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                Total Properties
              </span>
              <Building2 size={16} color="#7C3AED" />
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0F172A' }}>
              {loading ? '-' : stats?.total_properties ?? 0}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#7C3AED', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              View properties <ChevronRight size={12} />
            </div>
          </div>
        </Card>

        {/* Total Documents & Ingestion */}
        <Card padding="sm">
          <div
            onClick={() => onNavigate('documents')}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                Total Documents
              </span>
              <FileText size={16} color="#2563EB" />
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0F172A' }}>
              {loading ? '-' : stats?.total_documents ?? 0}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 500 }}>
              {loading ? '...' : `${stats?.processed_documents ?? 0} processed`}
            </div>
          </div>
        </Card>

        {/* OCR / Manual Review Needed */}
        <Card padding="sm">
          <div
            onClick={() => onNavigate('documents')}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                OCR / Review Queue
              </span>
              <Eye size={16} color={stats?.ocr_or_review_documents ? '#D97706' : '#94A3B8'} />
            </div>
            <div
              style={{
                fontSize: '1.75rem',
                fontWeight: 800,
                color: stats?.ocr_or_review_documents ? '#B45309' : '#0F172A',
              }}
            >
              {loading ? '-' : stats?.ocr_or_review_documents ?? 0}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
              {stats?.ocr_or_review_documents ? 'Attention required' : 'All clear'}
            </div>
          </div>
        </Card>

        {/* Critical & High Findings */}
        <Card padding="sm">
          <div
            onClick={() => onNavigate('properties')}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                Critical & High Risks
              </span>
              <AlertOctagon
                size={16}
                color={
                  (stats?.critical_findings_count ?? 0) + (stats?.high_findings_count ?? 0) > 0
                    ? '#DC2626'
                    : '#10B981'
                }
              />
            </div>
            <div
              style={{
                fontSize: '1.75rem',
                fontWeight: 800,
                color:
                  (stats?.critical_findings_count ?? 0) > 0
                    ? '#DC2626'
                    : (stats?.high_findings_count ?? 0) > 0
                    ? '#EA580C'
                    : '#0F172A',
              }}
            >
              {loading
                ? '-'
                : (stats?.critical_findings_count ?? 0) + (stats?.high_findings_count ?? 0)}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
              {loading
                ? '...'
                : `${stats?.critical_findings_count ?? 0} critical, ${stats?.high_findings_count ?? 0} high`}
            </div>
          </div>
        </Card>

        {/* Open vs Resolved */}
        <Card padding="sm">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                Open vs Resolved
              </span>
              <CheckCircle2 size={16} color="#10B981" />
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0F172A' }}>
              {loading ? '-' : `${stats?.open_findings_count ?? 0} / ${stats?.resolved_findings_count ?? 0}`}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
              {stats?.resolved_findings_count ? 'Mitigated findings' : 'Unresolved findings'}
            </div>
          </div>
        </Card>

        {/* Pending Assessments */}
        <Card padding="sm">
          <div
            onClick={() => onNavigate('properties')}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                Pending Assessments
              </span>
              <Clock size={16} color="#6366F1" />
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0F172A' }}>
              {loading ? '-' : stats?.pending_assessment_properties ?? 0}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Properties unassessed</div>
          </div>
        </Card>
      </div>

      {/* Properties Requiring Attention Section */}
      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldAlert
                size={18}
                color={attentionItems.length > 0 ? '#DC2626' : '#10B981'}
              />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                Properties Requiring Attention
              </h3>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                padding: '0.2rem 0.6rem',
                borderRadius: '9999px',
                backgroundColor: attentionItems.length > 0 ? '#FEE2E2' : '#D1FAE5',
                color: attentionItems.length > 0 ? '#991B1B' : '#065F46',
              }}
            >
              {attentionItems.length} {attentionItems.length === 1 ? 'property' : 'properties'}
            </span>
          </div>

          {loading ? (
            <div style={{ padding: '1.5rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.875rem' }}>
              <RefreshCw size={18} className="animate-spin" style={{ margin: '0 auto 0.5rem auto' }} />
              Loading portfolio findings...
            </div>
          ) : attentionItems.length === 0 ? (
            <div
              style={{
                padding: '1.5rem',
                textAlign: 'center',
                backgroundColor: '#F0FDF4',
                borderRadius: '8px',
                border: '1px solid #BBF7D0',
                color: '#166534',
                fontSize: '0.875rem',
              }}
            >
              <CheckCircle2 size={24} color="#16A34A" style={{ margin: '0 auto 0.5rem auto' }} />
              <div style={{ fontWeight: 600 }}>All properties in good standing</div>
              <div style={{ fontSize: '0.75rem', color: '#15803D', marginTop: '0.25rem' }}>
                No open critical risks, stale assessments, or failed OCR runs across your portfolio.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {attentionItems.map((item) => (
                <div
                  key={item.property_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.875rem 1rem',
                    backgroundColor: '#FFF1F2',
                    border: '1px solid #FECDD3',
                    borderRadius: '8px',
                    gap: '1rem',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#9F1239' }}>
                        {item.property_name}
                      </span>
                      {item.critical_count > 0 && (
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 700,
                            backgroundColor: '#E11D48',
                            color: '#FFFFFF',
                            padding: '0.1rem 0.45rem',
                            borderRadius: '4px',
                          }}
                        >
                          {item.critical_count} CRITICAL
                        </span>
                      )}
                      {item.high_count > 0 && (
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 700,
                            backgroundColor: '#F97316',
                            color: '#FFFFFF',
                            padding: '0.1rem 0.45rem',
                            borderRadius: '4px',
                          }}
                        >
                          {item.high_count} HIGH
                        </span>
                      )}
                      {item.has_failed_ocr && (
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 700,
                            backgroundColor: '#F59E0B',
                            color: '#FFFFFF',
                            padding: '0.1rem 0.45rem',
                            borderRadius: '4px',
                          }}
                        >
                          OCR REVIEW
                        </span>
                      )}
                      {item.is_assessment_stale && (
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 700,
                            backgroundColor: '#6366F1',
                            color: '#FFFFFF',
                            padding: '0.1rem 0.45rem',
                            borderRadius: '4px',
                          }}
                        >
                          STALE
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {item.reasons.map((r, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: '0.75rem',
                            color: '#881337',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                          }}
                        >
                          <AlertTriangle size={12} color="#E11D48" /> {r}
                        </span>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={() => onNavigate('properties', { propertyId: item.property_id })}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      padding: '0.45rem 0.85rem',
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      borderRadius: '6px',
                      backgroundColor: '#FFFFFF',
                      border: '1px solid #FDA4AF',
                      color: '#BE123C',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Review Property <ChevronRight size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
