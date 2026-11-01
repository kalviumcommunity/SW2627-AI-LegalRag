import React, { useState } from 'react';
import {
  FileText,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  HelpCircle,
  ExternalLink,
  ShieldAlert,
  Building,
  DollarSign,
  Scale,
  Award,
  Calendar,
  X,
  Layers,
} from 'lucide-react';
import { Card } from '../common/Card';
import { FactVerificationBadge } from '../common/Badge';
import type {
  ExtractedFieldFact,
  PropertyExtractionData,
  PropertyExtractionResponse,
  CrossDocumentConflict,
} from '../../api/types';

interface PropertyExtractionDashboardProps {
  propertyName: string;
  propertyId: string;
  extractionResponse: PropertyExtractionResponse | null;
  loading: boolean;
  onTriggerExtract: () => void;
  onRefreshExtract: () => void;
}

type TabType =
  | 'overview'
  | 'identity'
  | 'financial'
  | 'ownership'
  | 'approvals'
  | 'dates'
  | 'conflicts'
  | 'missing';

export const PropertyExtractionDashboard: React.FC<PropertyExtractionDashboardProps> = ({
  propertyName,
  propertyId,
  extractionResponse,
  loading,
  onTriggerExtract,
  onRefreshExtract,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [selectedCitationFact, setSelectedCitationFact] = useState<ExtractedFieldFact | null>(null);

  const data: PropertyExtractionData | undefined = extractionResponse?.data;
  const isStale = extractionResponse?.is_stale || false;
  const status = extractionResponse?.status || 'not_started';

  // Helper to render a fact card
  const renderFactCard = (fact: ExtractedFieldFact) => {
    const isMissing = fact.verification_status === 'missing' || !fact.extracted_value;

    return (
      <div
        key={fact.field_name}
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1px solid #E2E8F0',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
          transition: 'border-color 0.15s ease',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>
              {fact.display_name}
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700, color: isMissing ? '#94A3B8' : '#0F172A', marginTop: '0.25rem' }}>
              {isMissing ? 'Not Found' : String(fact.extracted_value)}
            </div>
          </div>
          <FactVerificationBadge status={fact.verification_status} size="sm" />
        </div>

        {/* Normalized representation & unit if present */}
        {!isMissing && fact.normalized_value !== undefined && fact.normalized_value !== null && fact.normalized_value !== fact.extracted_value && (
          <div style={{ fontSize: '0.8125rem', color: '#475569', backgroundColor: '#F8FAFC', padding: '0.35rem 0.65rem', borderRadius: '6px' }}>
            <span style={{ fontWeight: 600 }}>Normalized: </span>
            <span>
              {typeof fact.normalized_value === 'number'
                ? fact.normalized_value.toLocaleString()
                : String(fact.normalized_value)}{' '}
              {fact.unit || ''}
            </span>
          </div>
        )}

        {/* Original verbatim representation */}
        {!isMissing && fact.original_value && fact.original_value !== fact.extracted_value && (
          <div style={{ fontSize: '0.75rem', color: '#64748B', fontStyle: 'italic' }}>
            &ldquo;{fact.original_value}&rdquo;
          </div>
        )}

        {/* Citation & Source Pill */}
        {!isMissing && fact.filename && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: '0.5rem', borderTop: '1px solid #F1F5F9' }}>
            <button
              onClick={() => setSelectedCitationFact(fact)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.75rem',
                color: '#7C3AED',
                backgroundColor: '#F3F0FF',
                border: '1px solid #DDD6FE',
                borderRadius: '6px',
                padding: '0.25rem 0.5rem',
                cursor: 'pointer',
                fontWeight: 600,
              }}
              title="Click to view supporting document excerpt"
            >
              <FileText size={12} />
              <span>{fact.filename} {fact.page_number ? `(p. ${fact.page_number})` : ''}</span>
              <ExternalLink size={10} />
            </button>
            <span style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>
              {Math.round((fact.confidence || 0) * 100)}% conf
            </span>
          </div>
        )}

        {/* Uncertainty / Conflict Note */}
        {fact.uncertainty_note && (
          <div style={{ fontSize: '0.75rem', color: '#B45309', backgroundColor: '#FEF3C7', padding: '0.4rem 0.6rem', borderRadius: '6px', display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
            <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{fact.uncertainty_note}</span>
          </div>
        )}

        {/* Alternative conflicting values list */}
        {fact.alternative_values && fact.alternative_values.length > 0 && (
          <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px dashed #FECACA' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#DC2626', marginBottom: '0.35rem' }}>
              Alternative value(s) in other documents:
            </div>
            {fact.alternative_values.map((alt, idx) => (
              <div key={idx} style={{ fontSize: '0.75rem', color: '#991B1B', backgroundColor: '#FEF2F2', padding: '0.35rem 0.5rem', borderRadius: '4px', marginBottom: '0.25rem' }}>
                <span style={{ fontWeight: 600 }}>{String(alt.extracted_value)}</span>
                <span style={{ color: '#64748B' }}> in {alt.filename} {alt.page_number ? `(p. ${alt.page_number})` : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Helper to render cross-document conflicts
  const renderConflictsSection = (conflicts: CrossDocumentConflict[]) => {
    if (!conflicts || conflicts.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
          <CheckCircle2 size={36} color="#10B981" style={{ marginBottom: '0.75rem' }} />
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: '#1E293B', marginBottom: '0.25rem' }}>
            No Document Conflicts Detected
          </h3>
          <p style={{ fontSize: '0.875rem' }}>
            All facts extracted across associated documents are mutually consistent.
          </p>
        </div>
      );
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <ShieldAlert size={24} color="#DC2626" />
          <div>
            <div style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.9375rem' }}>
              {conflicts.length} Cross-Document Discrepancies Found
            </div>
            <div style={{ fontSize: '0.8125rem', color: '#7F1D1D' }}>
              Extracted values differ materially across legal instruments. Both values have been preserved without fabricating resolution.
            </div>
          </div>
        </div>

        {conflicts.map((conf, idx) => (
          <div
            key={idx}
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              border: '1px solid #FECACA',
              padding: '1.25rem',
              boxShadow: '0 1px 3px rgba(220, 38, 38, 0.05)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <AlertTriangle size={18} color="#DC2626" />
              <span style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.9375rem' }}>
                Discrepancy: {conf.contradiction_reason || 'Material conflict between documents'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {/* Source A */}
              <div style={{ backgroundColor: '#F8FAFC', borderRadius: '8px', padding: '0.875rem', border: '1px solid #E2E8F0' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                  Document A: {conf.source_a.filename} {conf.source_a.page_number ? `(p. ${conf.source_a.page_number})` : ''}
                </div>
                <div style={{ fontSize: '0.8125rem', color: '#1E293B', marginTop: '0.5rem', fontStyle: 'italic', backgroundColor: '#FFFFFF', padding: '0.5rem', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                  &ldquo;{conf.source_a.quote}&rdquo;
                </div>
              </div>

              {/* Source B */}
              <div style={{ backgroundColor: '#F8FAFC', borderRadius: '8px', padding: '0.875rem', border: '1px solid #E2E8F0' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                  Document B: {conf.source_b.filename} {conf.source_b.page_number ? `(p. ${conf.source_b.page_number})` : ''}
                </div>
                <div style={{ fontSize: '0.8125rem', color: '#1E293B', marginTop: '0.5rem', fontStyle: 'italic', backgroundColor: '#FFFFFF', padding: '0.5rem', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                  &ldquo;{conf.source_b.quote}&rdquo;
                </div>
              </div>
            </div>

            <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#64748B', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <HelpCircle size={13} />
              <span>Resolution note: {conf.resolution_note}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  // Helper to render missing fields checklist
  const renderMissingFieldsSection = (missingList: string[]) => {
    if (!missingList || missingList.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
          <CheckCircle2 size={36} color="#10B981" style={{ marginBottom: '0.75rem' }} />
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: '#1E293B', marginBottom: '0.25rem' }}>
            Complete Document Coverage
          </h3>
          <p style={{ fontSize: '0.875rem' }}>
            All core real estate diligence attributes were identified in the uploaded documents.
          </p>
        </div>
      );
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '1rem' }}>
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.35rem' }}>
            Due Diligence Gaps ({missingList.length} Missing Attributes)
          </h4>
          <p style={{ fontSize: '0.8125rem', color: '#64748B' }}>
            The following fields were not explicitly established by any uploaded document. Antigravity never hallucinates or fabricates missing information.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '0.75rem' }}>
          {missingList.map((fieldName, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                border: '1px solid #E2E8F0',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
              }}
            >
              <HelpCircle size={16} color="#94A3B8" />
              <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>
                {fieldName}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Extraction Action Header */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h2 style={{ fontSize: '1.375rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                {propertyName}
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
              Property ID: {propertyId} &bull; {data?.document_count || 0} document(s) analyzed
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {status === 'not_started' ? (
              <button
                onClick={onTriggerExtract}
                disabled={loading}
                className="btn btn-primary"
                style={{
                  backgroundColor: '#7C3AED',
                  color: '#FFFFFF',
                  border: 'none',
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
                <span>{loading ? 'Extracting...' : 'Extract Property Facts'}</span>
              </button>
            ) : (
              <button
                onClick={onRefreshExtract}
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
                <span>{loading ? 'Refreshing...' : 'Refresh Extraction'}</span>
              </button>
            )}
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
                Documents have changed since the last extraction. Extracted facts may be outdated.
              </span>
            </div>
            <button
              onClick={onRefreshExtract}
              disabled={loading}
              style={{
                backgroundColor: '#D97706',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                padding: '0.35rem 0.75rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Update Now
            </button>
          </div>
        )}
      </Card>

      {/* KPI / Verification Status Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div style={{ backgroundColor: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#166534' }}>Supported Facts</span>
            <CheckCircle2 size={18} color="#16A34A" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#14532D', marginTop: '0.5rem' }}>
            {data?.supported_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#15803D', marginTop: '0.25rem' }}>
            Corroborated by text passages
          </div>
        </div>

        <div style={{ backgroundColor: '#FEFCE8', border: '1px solid #FEF08A', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#854D0E' }}>Unverified Facts</span>
            <Clock size={18} color="#CA8A04" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#713F12', marginTop: '0.5rem' }}>
            {data?.unverified_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#A16207', marginTop: '0.25rem' }}>
            Require independent validation
          </div>
        </div>

        <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#991B1B' }}>Conflicting Values</span>
            <AlertTriangle size={18} color="#DC2626" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#7F1D1D', marginTop: '0.5rem' }}>
            {data?.conflicting_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#B91C1C', marginTop: '0.25rem' }}>
            Cross-document discrepancies
          </div>
        </div>

        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#475569' }}>Missing Fields</span>
            <HelpCircle size={18} color="#64748B" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#1E293B', marginTop: '0.5rem' }}>
            {data?.missing_count ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.25rem' }}>
            Due diligence document gaps
          </div>
        </div>
      </div>

      {/* Category Navigation Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', gap: '0.5rem', overflowX: 'auto', paddingBottom: '2px' }}>
        {[
          { id: 'overview' as TabType, label: 'Overview', icon: Layers },
          { id: 'identity' as TabType, label: 'Identity', icon: Building },
          { id: 'financial' as TabType, label: 'Financial', icon: DollarSign },
          { id: 'ownership' as TabType, label: 'Ownership & Legal', icon: Scale },
          { id: 'approvals' as TabType, label: 'Approvals', icon: Award },
          { id: 'dates' as TabType, label: 'Dates & Obligations', icon: Calendar },
          { id: 'conflicts' as TabType, label: `Conflicts (${data?.conflicts?.length || 0})`, icon: AlertTriangle },
          { id: 'missing' as TabType, label: `Missing Fields (${data?.missing_fields?.length || 0})`, icon: HelpCircle },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                border: 'none',
                borderBottom: isActive ? '3px solid #7C3AED' : '3px solid transparent',
                backgroundColor: 'transparent',
                color: isActive ? '#7C3AED' : '#64748B',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.875rem',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Tab Content */}
      {data ? (
        <div>
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.75rem' }}>
                  Property Overview
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                  {renderFactCard(data.identity.property_name)}
                  {renderFactCard(data.identity.property_address)}
                  {renderFactCard(data.identity.property_type)}
                  {renderFactCard(data.identity.unit_number)}
                  {renderFactCard(data.identity.carpet_area)}
                  {renderFactCard(data.identity.built_up_area)}
                </div>
              </div>

              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.75rem' }}>
                  Financial Highlights
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                  {renderFactCard(data.financial.sale_price)}
                  {renderFactCard(data.financial.booking_amount)}
                  {renderFactCard(data.financial.payment_schedule)}
                </div>
              </div>

              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.75rem' }}>
                  Title & Ownership
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                  {renderFactCard(data.ownership_legal.named_owner_or_seller)}
                  {renderFactCard(data.ownership_legal.ownership_claims)}
                  {renderFactCard(data.ownership_legal.encumbrance_information)}
                </div>
              </div>

              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.75rem' }}>
                  Key Dates & Regulatory
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                  {renderFactCard(data.dates_obligations.agreement_date)}
                  {renderFactCard(data.dates_obligations.possession_date)}
                  {renderFactCard(data.approvals.project_registration_references)}
                </div>
              </div>
            </div>
          )}

          {/* Identity Tab */}
          {activeTab === 'identity' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {Object.values(data.identity).map((fact) => renderFactCard(fact))}
            </div>
          )}

          {/* Financial Tab */}
          {activeTab === 'financial' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {Object.values(data.financial).map((fact) => renderFactCard(fact))}
            </div>
          )}

          {/* Ownership & Legal Tab */}
          {activeTab === 'ownership' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {Object.values(data.ownership_legal).map((fact) => renderFactCard(fact))}
            </div>
          )}

          {/* Approvals Tab */}
          {activeTab === 'approvals' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {Object.values(data.approvals).map((fact) => renderFactCard(fact))}
            </div>
          )}

          {/* Dates & Obligations Tab */}
          {activeTab === 'dates' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              {Object.values(data.dates_obligations).map((fact) => renderFactCard(fact))}
            </div>
          )}

          {/* Conflicts Tab */}
          {activeTab === 'conflicts' && renderConflictsSection(data.conflicts)}

          {/* Missing Fields Tab */}
          {activeTab === 'missing' && renderMissingFieldsSection(data.missing_fields)}
        </div>
      ) : (
        <Card>
          <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
            <Building size={48} color="#94A3B8" style={{ marginBottom: '1rem' }} />
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.5rem' }}>
              Structured Information Not Yet Extracted
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#64748B', maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
              Extract validated property identity, financial figures, ownership claims, regulatory approvals, and contractual obligations across all associated documents.
            </p>
            <button
              onClick={onTriggerExtract}
              disabled={loading}
              className="btn btn-primary"
              style={{
                backgroundColor: '#7C3AED',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                padding: '0.75rem 1.5rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              <span>{loading ? 'Analyzing Documents...' : 'Extract Property Information'}</span>
            </button>
          </div>
        </Card>
      )}

      {/* Clickable Source Citation Modal */}
      {selectedCitationFact && (
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
          onClick={() => setSelectedCitationFact(null)}
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
                <FileText size={20} color="#7C3AED" />
                <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                  Source Citation: {selectedCitationFact.display_name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedCitationFact(null)}
                aria-label="Close citation modal"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', backgroundColor: '#F8FAFC', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>Source Document</div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1E293B' }}>{selectedCitationFact.filename}</div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>ID: {selectedCitationFact.document_id}</div>
                </div>
                {selectedCitationFact.page_number && (
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>Page</div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1E293B' }}>{selectedCitationFact.page_number}</div>
                  </div>
                )}
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600, marginBottom: '0.25rem' }}>
                  Extracted Value
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#7C3AED' }}>
                  {String(selectedCitationFact.extracted_value)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600, marginBottom: '0.25rem' }}>
                  Supporting Text Passage
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
                  &ldquo;{selectedCitationFact.supporting_text || selectedCitationFact.original_value}&rdquo;
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid #E2E8F0' }}>
                <FactVerificationBadge status={selectedCitationFact.verification_status} />
                <span style={{ fontSize: '0.8125rem', color: '#64748B' }}>
                  Confidence: {Math.round((selectedCitationFact.confidence || 0) * 100)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
