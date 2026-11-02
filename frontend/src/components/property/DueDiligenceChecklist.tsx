import React from 'react';
import {
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  FileQuestion,
  Info,
  ExternalLink,
} from 'lucide-react';
import { Card } from '../common/Card';
import type {
  PropertyExtractionResponse,
  PropertyRiskAssessmentResponse,
  PropertyRiskFindingResponse,
  ExtractedFieldFact,
  CrossDocumentConflict,
} from '../../api/types';

interface DueDiligenceChecklistProps {
  propertyName: string;
  propertyId: string;
  extraction: PropertyExtractionResponse | null;
  riskAssessment: PropertyRiskAssessmentResponse | null;
  onNavigateToTab?: (tab: 'risk' | 'extraction') => void;
}

interface ChecklistItem {
  id: string;
  category: 'document' | 'verification' | 'conflict' | 'risk_finding' | 'ocr_status';
  title: string;
  description: string;
  status: 'passed' | 'attention' | 'action_required';
  evidenceOrNote?: string;
  targetTab?: 'risk' | 'extraction';
}

function collectAllFacts(extraction: PropertyExtractionResponse | null): ExtractedFieldFact[] {
  if (!extraction?.data) return [];
  const d = extraction.data;
  const groups = [d.identity, d.financial, d.ownership_legal, d.approvals, d.dates_obligations];
  const list: ExtractedFieldFact[] = [];
  for (const g of groups) {
    if (g && typeof g === 'object') {
      for (const f of Object.values(g)) {
        if (f && typeof f === 'object' && 'field_name' in f) {
          list.push(f as ExtractedFieldFact);
        }
      }
    }
  }
  return list;
}

export const DueDiligenceChecklist: React.FC<DueDiligenceChecklistProps> = ({
  propertyName,
  extraction,
  riskAssessment,
  onNavigateToTab,
}) => {
  const extractedData = extraction?.data;
  const allFacts = collectAllFacts(extraction);
  const supportedFacts = allFacts.filter((f) => f.verification_status === 'supported');
  const unverifiedFacts = allFacts.filter((f) => f.verification_status === 'unverified');
  const conflicts: CrossDocumentConflict[] = extractedData?.conflicts || [];
  const missingFields: string[] = extractedData?.missing_fields || [];
  const findings: PropertyRiskFindingResponse[] = riskAssessment?.findings || [];

  // 1. Build checklist items
  const items: ChecklistItem[] = [];

  // A. Essential Real Estate Documents check
  const criticalDocs = [
    { title: 'Sale Deed / Title Document', field: 'title_deed_references' },
    { title: 'Occupancy Certificate (OC)', field: 'occupancy_certificates' },
    { title: 'Completion Certificate (CC)', field: 'completion_certificates' },
    { title: 'Building Plan Approval', field: 'building_plan_approvals' },
    { title: 'Project Registration / RERA', field: 'project_registration_references' },
  ];

  for (const cDoc of criticalDocs) {
    const isMissing = missingFields.includes(cDoc.field);
    const hasFact = supportedFacts.some((f) => f.field_name === cDoc.field && f.extracted_value);
    if (hasFact) {
      items.push({
        id: `doc_${cDoc.field}`,
        category: 'document',
        title: cDoc.title,
        description: 'Document references identified and extracted in property record.',
        status: 'passed',
        evidenceOrNote: 'Extracted with supporting passage',
        targetTab: 'extraction',
      });
    } else if (isMissing) {
      items.push({
        id: `doc_${cDoc.field}`,
        category: 'document',
        title: cDoc.title,
        description: 'No explicit reference found in associated property documents.',
        status: 'attention',
        evidenceOrNote: 'Informational gap: confirm with seller if certificate was issued.',
        targetTab: 'extraction',
      });
    }
  }

  // B. Cross-Document Conflicts Check
  if (conflicts.length === 0) {
    items.push({
      id: 'conflicts_none',
      category: 'conflict',
      title: 'Cross-Document Consistency',
      description: 'No contradictory facts or conflicting clauses detected across uploaded documents.',
      status: 'passed',
      targetTab: 'extraction',
    });
  } else {
    for (let i = 0; i < conflicts.length; i++) {
      const c = conflicts[i];
      items.push({
        id: `conflict_${i}`,
        category: 'conflict',
        title: `Contradiction: ${c.source_a?.filename || 'Doc A'} vs ${c.source_b?.filename || 'Doc B'}`,
        description: c.contradiction_reason || 'Conflicting values asserted across documents.',
        status: 'action_required',
        evidenceOrNote: c.resolution_note || `Contradiction detected in cited passage`,
        targetTab: 'extraction',
      });
    }
  }

  // C. Unverified Facts Check
  if (unverifiedFacts.length > 0) {
    items.push({
      id: 'unverified_claims',
      category: 'verification',
      title: `${unverifiedFacts.length} Unverified Fact Claim(s)`,
      description: 'Extracted facts that lack sufficient corroborating passage evidence or contain ambiguity.',
      status: 'attention',
      evidenceOrNote: unverifiedFacts.map((u) => u.display_name || u.field_name).slice(0, 3).join(', ') +
        (unverifiedFacts.length > 3 ? ` (+${unverifiedFacts.length - 3} more)` : ''),
      targetTab: 'extraction',
    });
  } else if (supportedFacts.length > 0) {
    items.push({
      id: 'facts_all_supported',
      category: 'verification',
      title: 'Corroborated Extracted Facts',
      description: `All ${supportedFacts.length} extracted facts include supporting verbatim evidence passages.`,
      status: 'passed',
      targetTab: 'extraction',
    });
  }

  // D. Risk Findings Check
  const openCritical = findings.filter((f) => f.severity === 'critical' && f.status === 'open');
  const openHigh = findings.filter((f) => f.severity === 'high' && f.status === 'open');
  const openMediumOrLow = findings.filter(
    (f) => (f.severity === 'medium' || f.severity === 'low') && f.status === 'open'
  );
  const resolvedFindings = findings.filter((f) => f.status === 'resolved' || f.status === 'dismissed');

  if (openCritical.length > 0) {
    for (const crit of openCritical) {
      items.push({
        id: `risk_crit_${crit.risk_id}`,
        category: 'risk_finding',
        title: `Critical Finding: ${crit.title}`,
        description: crit.reason,
        status: 'action_required',
        evidenceOrNote: crit.recommended_action,
        targetTab: 'risk',
      });
    }
  }

  if (openHigh.length > 0) {
    for (const high of openHigh) {
      items.push({
        id: `risk_high_${high.risk_id}`,
        category: 'risk_finding',
        title: `High Finding: ${high.title}`,
        description: high.reason,
        status: 'attention',
        evidenceOrNote: high.recommended_action,
        targetTab: 'risk',
      });
    }
  }

  if (openCritical.length === 0 && openHigh.length === 0 && findings.length > 0) {
    items.push({
      id: 'risk_no_high',
      category: 'risk_finding',
      title: 'No Critical or High Risk Findings',
      description: `Risk engine evaluated all categories without detecting severe title or regulatory red flags (${openMediumOrLow.length} minor, ${resolvedFindings.length} resolved).`,
      status: 'passed',
      targetTab: 'risk',
    });
  }

  // Totals
  const actionRequiredCount = items.filter((i) => i.status === 'action_required').length;
  const attentionCount = items.filter((i) => i.status === 'attention').length;
  const passedCount = items.filter((i) => i.status === 'passed').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Notice Banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          backgroundColor: '#EFF6FF',
          border: '1px solid #BFDBFE',
          borderRadius: '8px',
          padding: '0.875rem 1rem',
          fontSize: '0.8125rem',
          color: '#1E40AF',
          lineHeight: 1.5,
        }}
      >
        <Info size={18} color="#2563EB" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>Due Diligence Gap vs Violation Notice:</strong> Missing documentation or unverified claims
          represent informational gaps in the provided records that warrant seller inquiry, not confirmed
          legal defects or dispute rulings.
        </div>
      </div>

      {/* Summary Score Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
        }}
      >
        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertOctagon size={24} color="#DC2626" />
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#DC2626' }}>
                {actionRequiredCount}
              </div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B' }}>
                Action Required
              </div>
            </div>
          </div>
        </Card>

        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertTriangle size={24} color="#D97706" />
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#D97706' }}>
                {attentionCount}
              </div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B' }}>
                Attention / Inquiries
              </div>
            </div>
          </div>
        </Card>

        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <CheckCircle size={24} color="#16A34A" />
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#16A34A' }}>
                {passedCount}
              </div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B' }}>
                Verified / Passed
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Checklist Items List */}
      <Card padding="none">
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid #E2E8F0' }}>
          <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: '#0F172A' }}>
            Verification Checklist for "{propertyName}"
          </h4>
        </div>

        {items.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.875rem' }}>
            <FileQuestion size={32} style={{ margin: '0 auto 0.5rem auto' }} />
            No structured extraction or risk analysis performed yet. Run extraction or risk assessment to populate the checklist.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {items.map((item, idx) => {
              const isLast = idx === items.length - 1;
              const borderStyle = isLast ? 'none' : '1px solid #F1F5F9';
              let badgeBg = '#DCFCE7';
              let badgeColor = '#166534';
              let badgeText = 'PASSED';
              let Icon = CheckCircle;
              let iconColor = '#16A34A';

              if (item.status === 'action_required') {
                badgeBg = '#FEE2E2';
                badgeColor = '#991B1B';
                badgeText = 'ACTION REQUIRED';
                Icon = AlertOctagon;
                iconColor = '#DC2626';
              } else if (item.status === 'attention') {
                badgeBg = '#FEF3C7';
                badgeColor = '#92400E';
                badgeText = 'ATTENTION NEEDED';
                Icon = AlertTriangle;
                iconColor = '#D97706';
              }

              return (
                <div
                  key={item.id}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    padding: '1rem 1.25rem',
                    borderBottom: borderStyle,
                    gap: '1rem',
                    backgroundColor: item.status === 'action_required' ? '#FFF5F5' : '#FFFFFF',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                    <Icon size={18} color={iconColor} style={{ flexShrink: 0, marginTop: '2px' }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1E293B' }}>
                          {item.title}
                        </span>
                        <span
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 700,
                            padding: '0.15rem 0.5rem',
                            borderRadius: '4px',
                            backgroundColor: badgeBg,
                            color: badgeColor,
                          }}
                        >
                          {badgeText}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.8125rem', color: '#475569', lineHeight: 1.4 }}>
                        {item.description}
                      </div>

                      {item.evidenceOrNote && (
                        <div
                          style={{
                            fontSize: '0.75rem',
                            color: '#64748B',
                            backgroundColor: '#F8FAFC',
                            padding: '0.35rem 0.6rem',
                            borderRadius: '4px',
                            border: '1px solid #E2E8F0',
                            marginTop: '0.25rem',
                          }}
                        >
                          <strong>Detail:</strong> {item.evidenceOrNote}
                        </div>
                      )}
                    </div>
                  </div>

                  {item.targetTab && onNavigateToTab && (
                    <button
                      onClick={() => onNavigateToTab(item.targetTab!)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        padding: '0.35rem 0.65rem',
                        borderRadius: '4px',
                        border: '1px solid #CBD5E1',
                        backgroundColor: '#FFFFFF',
                        color: '#475569',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Inspect <ExternalLink size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
};
