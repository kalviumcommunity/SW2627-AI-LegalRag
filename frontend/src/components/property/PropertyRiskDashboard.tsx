import React, { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ShieldAlert,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  HelpCircle,
  FileText,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  X,
  Filter,
  Layers,
  Building,
  DollarSign,
  Scale,
  Award,
  CheckSquare,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Modal } from '../common/Modal';
import { RiskSeverityBadge, RiskFindingStatusBadge } from '../common/Badge';
import type {
  PropertyRiskAssessmentResponse,
  PropertyRiskFindingResponse,
  RiskCategory,
  RiskSeverity,
  RiskFindingStatus,
  RiskEvidenceItem,
} from '../../api/types';

interface PropertyRiskDashboardProps {
  propertyName: string;
  propertyId: string;
  assessmentResponse: PropertyRiskAssessmentResponse | null;
  loading: boolean;
  onTriggerAssess: () => void;
  onRefreshAssess: () => void;
  onUpdateFindingStatus: (riskId: string, status: RiskFindingStatus, notes?: string) => Promise<void>;
}

export const PropertyRiskDashboard: React.FC<PropertyRiskDashboardProps> = ({
  propertyName,
  propertyId,
  assessmentResponse,
  loading,
  onTriggerAssess,
  onRefreshAssess,
  onUpdateFindingStatus,
}) => {
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState<{
    findingTitle: string;
    evidence: RiskEvidenceItem;
  } | null>(null);

  // Status update modal state
  const [updatingFinding, setUpdatingFinding] = useState<PropertyRiskFindingResponse | null>(null);
  const [newStatus, setNewStatus] = useState<RiskFindingStatus>('open');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [isSubmittingStatus, setIsSubmittingStatus] = useState<boolean>(false);
  const [showChecklist, setShowChecklist] = useState<boolean>(true);

  // Category labels and icons
  const categoryMeta: Record<RiskCategory, { label: string; icon: LucideIcon }> = {
    ownership_title: { label: 'Ownership & Title', icon: Scale },
    regulatory_approval: { label: 'Regulatory & Approvals', icon: Award },
    financial: { label: 'Financial Risks', icon: DollarSign },
    property_identity: { label: 'Identity & Area', icon: Building },
    legal_dispute: { label: 'Legal & Disputes', icon: ShieldAlert },
    documentation_completeness: { label: 'Documentation Completeness', icon: Layers },
  };

  // Loading state when no data exists yet
  if (loading && !assessmentResponse) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '3.5rem 1rem' }}>
          <RefreshCw size={36} className="animate-spin" color="#7C3AED" style={{ margin: '0 auto 1rem auto' }} />
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.35rem' }}>
            Evaluating property due diligence risks across documents...
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#64748B' }}>
            Analyzing ownership titles, regulatory approvals, financial consistency, and legal dispute statements.
          </p>
        </div>
      </Card>
    );
  }

  // Not started state
  if (!assessmentResponse) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <ShieldAlert size={48} color="#94A3B8" style={{ marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.5rem' }}>
            No Risk Assessment Available
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#64748B', maxWidth: '500px', margin: '0 auto 1.5rem auto' }}>
            Run the automated risk assessment engine to identify potential title disputes, conflicting financial terms, and missing regulatory approvals across property documents.
          </p>
          <button
            onClick={onTriggerAssess}
            disabled={loading}
            className="btn btn-primary"
            style={{
              backgroundColor: '#7C3AED',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              padding: '0.65rem 1.25rem',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <ShieldAlert size={18} />
            <span>Run Risk Assessment</span>
          </button>
        </div>
      </Card>
    );
  }

  const findings = assessmentResponse.findings || [];
  const summary = assessmentResponse.summary;
  const isStale = assessmentResponse.is_stale || false;
  const status = assessmentResponse.status || 'not_started';

  // Filter findings
  const filteredFindings = findings.filter((f) => {
    if (selectedSeverity !== 'all' && f.severity !== selectedSeverity) return false;
    if (selectedCategory !== 'all' && f.category !== selectedCategory) return false;
    if (selectedStatus !== 'all' && f.status !== selectedStatus) return false;
    return true;
  });

  const handleOpenStatusModal = (finding: PropertyRiskFindingResponse) => {
    setUpdatingFinding(finding);
    setNewStatus(finding.status);
    setReviewNotes(finding.user_notes || '');
  };

  const handleSaveStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!updatingFinding) return;

    try {
      setIsSubmittingStatus(true);
      await onUpdateFindingStatus(updatingFinding.risk_id, newStatus, reviewNotes.trim() || undefined);
      setUpdatingFinding(null);
    } finally {
      setIsSubmittingStatus(false);
    }
  };

  // Group findings count by category for checklist
  const categoryCounts: Record<RiskCategory, { total: number; criticalHigh: number }> = {
    ownership_title: { total: 0, criticalHigh: 0 },
    regulatory_approval: { total: 0, criticalHigh: 0 },
    financial: { total: 0, criticalHigh: 0 },
    property_identity: { total: 0, criticalHigh: 0 },
    legal_dispute: { total: 0, criticalHigh: 0 },
    documentation_completeness: { total: 0, criticalHigh: 0 },
  };

  for (const f of findings) {
    if (categoryCounts[f.category]) {
      categoryCounts[f.category].total++;
      if (f.severity === 'critical' || f.severity === 'high') {
        categoryCounts[f.category].criticalHigh++;
      }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Assessment Action Header */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h2 style={{ fontSize: '1.375rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                {propertyName} Due Diligence Assessment
              </h2>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '0.25rem 0.5rem',
                  borderRadius: '6px',
                  backgroundColor: status === 'completed' ? '#DCFCE7' : status === 'stale' ? '#FEF3C7' : '#F1F5F9',
                  color: status === 'completed' ? '#15803D' : status === 'stale' ? '#B45309' : '#475569',
                }}
              >
                {status}
              </span>
            </div>
            <p style={{ fontSize: '0.8125rem', color: '#64748B', marginTop: '0.35rem', marginBottom: 0 }}>
              Property ID: {propertyId} &bull; {assessmentResponse?.document_count || 0} document(s) evaluated &bull; Last updated {new Date(assessmentResponse.updated_at).toLocaleDateString()}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={onRefreshAssess}
              disabled={loading}
              className="btn btn-secondary"
              style={{
                backgroundColor: '#FFFFFF',
                color: '#7C3AED',
                border: '1px solid #7C3AED',
                borderRadius: '8px',
                padding: '0.6rem 1.2rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
              }}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              <span>{loading ? 'Refreshing...' : 'Reassess Risks'}</span>
            </button>
          </div>
        </div>

        {/* Staleness Banner */}
        {isStale && (
          <div
            style={{
              marginTop: '1.25rem',
              backgroundColor: '#FFFBEB',
              border: '1px solid #FDE68A',
              borderRadius: '8px',
              padding: '0.75rem 1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertTriangle size={18} color="#D97706" />
              <span style={{ fontSize: '0.875rem', color: '#92400E', fontWeight: 600 }}>
                Assessment Stale: Property documents have been added or updated since this assessment was conducted.
              </span>
            </div>
            <button
              onClick={onRefreshAssess}
              disabled={loading}
              style={{
                backgroundColor: '#D97706',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                padding: '0.4rem 0.85rem',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Refresh Assessment
            </button>
          </div>
        )}

        {/* Informational Legal Notice Banner */}
        <div
          style={{
            marginTop: '1rem',
            backgroundColor: '#F8FAFC',
            border: '1px solid #E2E8F0',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            fontSize: '0.75rem',
            color: '#64748B',
            lineHeight: 1.45,
          }}
        >
          <span style={{ fontWeight: 700, color: '#334155' }}>Due Diligence Legal Notice: </span>
          This engine operates as an informational due diligence assistant evaluating document records and factual consistency.
          It does NOT constitute an advocate title search, title insurance, or structural guarantee.
          Never declare a property legally clear or dispute-free solely on automated findings.
        </div>
      </Card>

      {/* KPI Severity Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#991B1B' }}>Critical Risks</span>
            <ShieldAlert size={18} color="#DC2626" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#7F1D1D', marginTop: '0.5rem' }}>
            {summary?.critical_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#B91C1C', marginTop: '0.25rem' }}>
            Active litigation, mortgage, or title disputes
          </div>
        </div>

        <div style={{ backgroundColor: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#9A3412' }}>High Severity</span>
            <AlertTriangle size={18} color="#EA580C" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#7C2D12', marginTop: '0.5rem' }}>
            {summary?.high_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#C2410C', marginTop: '0.25rem' }}>
            Conflicting consideration, area, or missing deeds
          </div>
        </div>

        <div style={{ backgroundColor: '#FEFCE8', border: '1px solid #FEF08A', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#854D0E' }}>Medium & Low</span>
            <Clock size={18} color="#CA8A04" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#713F12', marginTop: '0.5rem' }}>
            {(summary?.medium_count ?? 0) + (summary?.low_count ?? 0)}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#A16207', marginTop: '0.25rem' }}>
            Missing OC/CC, booking schedule, unverified claims
          </div>
        </div>

        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#475569' }}>Workflow Status</span>
            <CheckSquare size={18} color="#64748B" />
          </div>
          <div style={{ fontSize: '1.125rem', fontWeight: 800, color: '#1E293B', marginTop: '0.5rem' }}>
            {summary?.open_count ?? 0} Open &bull; {summary?.resolved_count ?? 0} Resolved
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
            {summary?.under_review_count ?? 0} under legal review
          </div>
        </div>
      </div>

      {/* Due Diligence Checklist & Categories */}
      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div
            onClick={() => setShowChecklist(!showChecklist)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={18} color="#7C3AED" />
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                Due Diligence Checklist & Categories
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
                {showChecklist ? 'Collapse' : 'Expand'}
              </span>
              {showChecklist ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>

          {showChecklist && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem', marginTop: '0.5rem' }}>
              {(Object.keys(categoryMeta) as RiskCategory[]).map((catKey) => {
                const meta = categoryMeta[catKey];
                const IconComponent = meta.icon;
                const stats = categoryCounts[catKey];
                const hasCritical = stats.criticalHigh > 0;

                return (
                  <div
                    key={catKey}
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      backgroundColor: hasCritical ? '#FEF2F2' : '#F8FAFC',
                      border: `1px solid ${hasCritical ? '#FECACA' : '#E2E8F0'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <div
                        style={{
                          padding: '0.35rem',
                          borderRadius: '6px',
                          backgroundColor: hasCritical ? '#FEE2E2' : '#EDF2F7',
                          color: hasCritical ? '#DC2626' : '#475569',
                        }}
                      >
                        <IconComponent size={16} />
                      </div>
                      <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#1E293B' }}>
                        {meta.label}
                      </span>
                    </div>

                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '9999px',
                        backgroundColor: hasCritical ? '#DC2626' : stats.total > 0 ? '#FEF08A' : '#E2E8F0',
                        color: hasCritical ? '#FFFFFF' : stats.total > 0 ? '#854D0E' : '#64748B',
                      }}
                    >
                      {stats.total} finding{stats.total === 1 ? '' : 's'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      {/* Filter Toolbar */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={16} color="#64748B" />
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1E293B' }}>Filter Findings:</span>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {/* Severity Filter */}
            <select
              aria-label="Severity"
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              style={{
                padding: '0.45rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '0.8125rem',
                color: '#334155',
                backgroundColor: '#FFFFFF',
              }}
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="informational">Informational</option>
            </select>

            {/* Category Filter */}
            <select
              aria-label="Category"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                padding: '0.45rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '0.8125rem',
                color: '#334155',
                backgroundColor: '#FFFFFF',
              }}
            >
              <option value="all">All Categories</option>
              <option value="ownership_title">Ownership & Title</option>
              <option value="regulatory_approval">Regulatory & Approvals</option>
              <option value="financial">Financial</option>
              <option value="property_identity">Identity & Area</option>
              <option value="legal_dispute">Legal & Disputes</option>
              <option value="documentation_completeness">Completeness</option>
            </select>

            {/* Status Filter */}
            <select
              aria-label="Status"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={{
                padding: '0.45rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                fontSize: '0.8125rem',
                color: '#334155',
                backgroundColor: '#FFFFFF',
              }}
            >
              <option value="all">All Statuses</option>
              <option value="open">Open</option>
              <option value="under_review">Under Review</option>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Findings List */}
      {filteredFindings.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
            <CheckCircle2 size={48} color="#10B981" style={{ marginBottom: '1rem' }} />
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.35rem' }}>
              No Findings Matching Current Filter
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#64748B', maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
              Try adjusting the severity, category, or workflow status filter.
            </p>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {filteredFindings.map((finding) => {
            const CatIcon = categoryMeta[finding.category]?.icon || AlertCircle;
            const catLabel = categoryMeta[finding.category]?.label || finding.category;

            return (
              <div
                key={finding.risk_id}
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: `1px solid ${
                    finding.severity === 'critical'
                      ? '#FCA5A5'
                      : finding.severity === 'high'
                      ? '#FDBA74'
                      : '#E2E8F0'
                  }`,
                  padding: '1.5rem',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1rem',
                }}
              >
                {/* Header: Category, Severity, Status */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <div
                      style={{
                        padding: '0.4rem',
                        borderRadius: '8px',
                        backgroundColor: '#F3F0FF',
                        color: '#7C3AED',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <CatIcon size={18} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
                        {catLabel}
                      </div>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0F172A', margin: '0.15rem 0 0 0' }}>
                        {finding.title}
                      </h3>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <RiskSeverityBadge severity={finding.severity} />
                    <RiskFindingStatusBadge status={finding.status} />
                    <button
                      onClick={() => handleOpenStatusModal(finding)}
                      style={{
                        padding: '0.35rem 0.65rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: '#7C3AED',
                        backgroundColor: '#F3F0FF',
                        border: '1px solid #DDD6FE',
                        borderRadius: '6px',
                        cursor: 'pointer',
                      }}
                    >
                      Update Status
                    </button>
                  </div>
                </div>

                {/* Description & Reason */}
                <div style={{ fontSize: '0.875rem', color: '#334155', lineHeight: 1.5 }}>
                  {finding.description}
                </div>

                <div
                  style={{
                    backgroundColor: '#F8FAFC',
                    borderLeft: '4px solid #CBD5E1',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '0 6px 6px 0',
                    fontSize: '0.8125rem',
                    color: '#475569',
                  }}
                >
                  <span style={{ fontWeight: 600 }}>Why Flagged: </span>
                  <span>{finding.reason}</span>
                </div>

                {/* Traceable Evidence */}
                {finding.evidence && finding.evidence.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                      Supporting Document Evidence ({finding.evidence.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {finding.evidence.map((ev, idx) => (
                        <button
                          key={idx}
                          onClick={() =>
                            setSelectedEvidenceItem({
                              findingTitle: finding.title,
                              evidence: ev,
                            })
                          }
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            fontSize: '0.75rem',
                            color: '#7C3AED',
                            backgroundColor: '#F5F3FF',
                            border: '1px solid #DDD6FE',
                            borderRadius: '6px',
                            padding: '0.3rem 0.6rem',
                            cursor: 'pointer',
                            fontWeight: 600,
                          }}
                          title="Click to view supporting text excerpt"
                        >
                          <FileText size={12} />
                          <span>
                            {ev.filename || 'Document'} {ev.page_number ? `(p. ${ev.page_number})` : ''}
                          </span>
                          <ExternalLink size={10} />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended Action */}
                <div
                  style={{
                    backgroundColor: '#F0FDF4',
                    border: '1px solid #BBF7D0',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.6rem',
                  }}
                >
                  <CheckCircle2 size={16} color="#16A34A" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#166534', textTransform: 'uppercase' }}>
                      Recommended Due Diligence Action
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: '#14532D', marginTop: '0.2rem', lineHeight: 1.45 }}>
                      {finding.recommended_action}
                    </div>
                  </div>
                </div>

                {/* User Notes */}
                {finding.user_notes && (
                  <div style={{ fontSize: '0.75rem', color: '#64748B', fontStyle: 'italic', paddingTop: '0.5rem', borderTop: '1px dashed #E2E8F0' }}>
                    <span style={{ fontWeight: 600 }}>Reviewer Note: </span>
                    <span>&ldquo;{finding.user_notes}&rdquo;</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Evidence Viewer Modal */}
      {selectedEvidenceItem && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={() => setSelectedEvidenceItem(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              maxWidth: '600px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={18} color="#7C3AED" />
                <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                  Supporting Legal Evidence
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvidenceItem(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
              >
                Close
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div style={{ fontSize: '0.875rem', color: '#64748B' }}>
                <span style={{ fontWeight: 600, color: '#334155' }}>Finding: </span>
                <span>{selectedEvidenceItem.findingTitle}</span>
              </div>

              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8125rem', color: '#475569' }}>
                <div>
                  <span style={{ fontWeight: 600 }}>Document: </span>
                  <span>{selectedEvidenceItem.evidence.filename || 'Unknown Document'}</span>
                </div>
                {selectedEvidenceItem.evidence.page_number && (
                  <div>
                    <span style={{ fontWeight: 600 }}>Page: </span>
                    <span>Page {selectedEvidenceItem.evidence.page_number}</span>
                  </div>
                )}
                {selectedEvidenceItem.evidence.verification_status && (
                  <div>
                    <span style={{ fontWeight: 600 }}>Verification: </span>
                    <span style={{ textTransform: 'capitalize' }}>
                      {selectedEvidenceItem.evidence.verification_status}
                    </span>
                  </div>
                )}
              </div>

              <div style={{ marginTop: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                  Document Excerpt
                </div>
                <div
                  style={{
                    backgroundColor: '#F8FAFC',
                    borderLeft: '4px solid #7C3AED',
                    padding: '0.75rem 1rem',
                    fontSize: '0.875rem',
                    color: '#334155',
                    fontStyle: 'italic',
                    borderRadius: '0 8px 8px 0',
                    lineHeight: 1.5,
                  }}
                >
                  &ldquo;{selectedEvidenceItem.evidence.supporting_text || selectedEvidenceItem.evidence.original_value || 'No verbatim excerpt recorded.'}&rdquo;
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Status Update Modal */}
      {updatingFinding && (
        <Modal
          isOpen={true}
          onClose={() => setUpdatingFinding(null)}
          title="Update Finding Status"
        >
          <form onSubmit={handleSaveStatusUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label
                htmlFor="finding-status-select"
                style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#334155', marginBottom: '0.35rem' }}
              >
                Review Status *
              </label>
              <select
                id="finding-status-select"
                aria-label="Review Status"
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value as RiskFindingStatus)}
                style={{
                  width: '100%',
                  padding: '0.6rem 0.75rem',
                  fontSize: '0.875rem',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#FFFFFF',
                }}
              >
                <option value="open">Open</option>
                <option value="under_review">Under Review</option>
                <option value="resolved">Resolved</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="review-notes-input"
                style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#334155', marginBottom: '0.35rem' }}
              >
                Review Notes
              </label>
              <textarea
                id="review-notes-input"
                aria-label="Review Notes"
                rows={3}
                placeholder="Add attorney or reviewer notes..."
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.6rem 0.75rem',
                  fontSize: '0.875rem',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
              <button
                type="button"
                onClick={() => setUpdatingFinding(null)}
                style={{
                  padding: '0.5rem 1rem',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  color: '#475569',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmittingStatus}
                style={{
                  padding: '0.5rem 1.25rem',
                  backgroundColor: '#7C3AED',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: isSubmittingStatus ? 'not-allowed' : 'pointer',
                  fontWeight: 600,
                  opacity: isSubmittingStatus ? 0.7 : 1,
                }}
              >
                {isSubmittingStatus ? 'Saving...' : 'Save Status'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
