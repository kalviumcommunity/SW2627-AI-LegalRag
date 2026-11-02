import React, { useState } from 'react';
import {
  FileSearch,
  Quote,
  CheckCircle,
  AlertTriangle,
  Search,
  Filter,
  Layers,
  ArrowRightLeft,
} from 'lucide-react';
import { Card } from '../common/Card';
import type {
  PropertyExtractionResponse,
  ExtractedFieldFact,
  CrossDocumentConflict,
} from '../../api/types';

interface EvidenceExplorerProps {
  extraction: PropertyExtractionResponse | null;
  loading?: boolean;
}

interface FactWithCategory {
  fact: ExtractedFieldFact;
  category: string;
}

function collectFactsWithCategories(extraction: PropertyExtractionResponse | null): FactWithCategory[] {
  if (!extraction?.data) return [];
  const d = extraction.data;
  const groups: [string, object | undefined][] = [
    ['Identity', d.identity],
    ['Financial', d.financial],
    ['Ownership & Legal', d.ownership_legal],
    ['Approvals', d.approvals],
    ['Dates & Obligations', d.dates_obligations],
  ];

  const list: FactWithCategory[] = [];
  for (const [category, g] of groups) {
    if (g && typeof g === 'object') {
      for (const f of Object.values(g)) {
        if (f && typeof f === 'object' && 'field_name' in f) {
          list.push({ fact: f as ExtractedFieldFact, category });
        }
      }
    }
  }
  return list;
}

export const EvidenceExplorer: React.FC<EvidenceExplorerProps> = ({
  extraction,
  loading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const allItems = collectFactsWithCategories(extraction);
  const supportedFacts = allItems.filter((i) => i.fact.verification_status === 'supported');
  const unverifiedFacts = allItems.filter((i) => i.fact.verification_status === 'unverified');
  const conflicts: CrossDocumentConflict[] = extraction?.data?.conflicts || [];

  const categories = Array.from(new Set(allItems.map((item) => item.category))).sort();

  const filteredFacts = allItems.filter(({ fact, category }) => {
    const term = searchTerm.toLowerCase().trim();
    const matchesSearch =
      term === '' ||
      fact.field_name.toLowerCase().includes(term) ||
      (fact.display_name && fact.display_name.toLowerCase().includes(term)) ||
      String(fact.extracted_value || '').toLowerCase().includes(term) ||
      (fact.supporting_text || '').toLowerCase().includes(term) ||
      (fact.filename || '').toLowerCase().includes(term);

    const matchesCategory = categoryFilter === 'all' || category === categoryFilter;
    const matchesStatus = statusFilter === 'all' || fact.verification_status === statusFilter;

    return matchesSearch && matchesCategory && matchesStatus;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Overview stats */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <CheckCircle size={22} color="#16A34A" />
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A' }}>
                {supportedFacts.length}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Verified Passages</div>
            </div>
          </div>
        </Card>

        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertTriangle size={22} color="#D97706" />
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A' }}>
                {unverifiedFacts.length}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Unverified Claims</div>
            </div>
          </div>
        </Card>

        <Card padding="sm">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <ArrowRightLeft size={22} color="#DC2626" />
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A' }}>
                {conflicts.length}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Cross-Doc Contradictions</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Cross-Document Conflicts Comparison Section */}
      {conflicts.length > 0 && (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ArrowRightLeft size={18} color="#DC2626" />
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#991B1B', margin: 0 }}>
                Cross-Document Conflict Matrix ({conflicts.length})
              </h3>
            </div>
            <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: 0 }}>
              Direct contradictions detected between different uploaded files for the same property.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
              {conflicts.map((c, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#FEF2F2',
                    border: '1px solid #FECDD3',
                    borderRadius: '8px',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#991B1B' }}>
                      Contradiction: {c.source_a?.filename || 'Doc A'} vs {c.source_b?.filename || 'Doc B'}
                    </span>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        backgroundColor: '#DC2626',
                        color: '#FFFFFF',
                        padding: '0.15rem 0.5rem',
                        borderRadius: '4px',
                      }}
                    >
                      CONFLICT
                    </span>
                  </div>

                  <div style={{ fontSize: '0.8125rem', color: '#7F1D1D' }}>
                    {c.contradiction_reason}
                  </div>

                  {/* Side-by-side comparison */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                      gap: '0.75rem',
                      marginTop: '0.25rem',
                    }}
                  >
                    {/* Source A */}
                    <div
                      style={{
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #FCA5A5',
                        borderRadius: '6px',
                        padding: '0.75rem',
                      }}
                    >
                      <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>
                        Source Document A: {c.source_a?.filename || 'Doc A'} {c.source_a?.page_number ? `(Page ${c.source_a.page_number})` : ''}
                      </div>
                      {c.source_a?.quote && (
                        <div
                          style={{
                            fontSize: '0.75rem',
                            color: '#475569',
                            fontStyle: 'italic',
                            backgroundColor: '#F8FAFC',
                            padding: '0.5rem',
                            borderRadius: '4px',
                            borderLeft: '3px solid #EF4444',
                            marginTop: '0.35rem',
                          }}
                        >
                          "{c.source_a.quote}"
                        </div>
                      )}
                    </div>

                    {/* Source B */}
                    <div
                      style={{
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #FCA5A5',
                        borderRadius: '6px',
                        padding: '0.75rem',
                      }}
                    >
                      <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>
                        Source Document B: {c.source_b?.filename || 'Doc B'} {c.source_b?.page_number ? `(Page ${c.source_b.page_number})` : ''}
                      </div>
                      {c.source_b?.quote && (
                        <div
                          style={{
                            fontSize: '0.75rem',
                            color: '#475569',
                            fontStyle: 'italic',
                            backgroundColor: '#F8FAFC',
                            padding: '0.5rem',
                            borderRadius: '4px',
                            borderLeft: '3px solid #EF4444',
                            marginTop: '0.35rem',
                          }}
                        >
                          "{c.source_b.quote}"
                        </div>
                      )}
                    </div>
                  </div>

                  {c.resolution_note && (
                    <div style={{ fontSize: '0.75rem', color: '#991B1B', fontStyle: 'italic' }}>
                      <strong>Resolution Note:</strong> {c.resolution_note}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Filter and Search Bar */}
      <Card padding="sm">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            flexWrap: 'wrap',
          }}
        >
          {/* Search box */}
          <div style={{ position: 'relative', flex: '1 1 200px' }}>
            <Search
              size={15}
              style={{ position: 'absolute', left: '10px', top: '10px', color: '#94A3B8' }}
            />
            <input
              type="text"
              placeholder="Search facts, passages, filenames..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem 0.5rem 0.5rem 2.25rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Category filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Layers size={14} color="#64748B" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              style={{
                padding: '0.5rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
              }}
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Status filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Filter size={14} color="#64748B" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '0.5rem',
                fontSize: '0.8125rem',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
              }}
            >
              <option value="all">All Statuses</option>
              <option value="supported">Verified / Supported</option>
              <option value="unverified">Unverified</option>
              <option value="conflicting">Conflicting</option>
              <option value="missing">Missing</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Evidence Passages & Facts List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {loading ? (
          <Card>
            <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8' }}>
              Loading evidence passages...
            </div>
          </Card>
        ) : filteredFacts.length === 0 ? (
          <Card>
            <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8' }}>
              <FileSearch size={32} style={{ margin: '0 auto 0.5rem auto' }} />
              <div>No evidence passages match your current filter criteria.</div>
            </div>
          </Card>
        ) : (
          filteredFacts.map(({ fact, category }, idx) => {
            const isSupported = fact.verification_status === 'supported';
            return (
              <Card key={idx} padding="md">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {/* Header: Field name + Category + Verification Badge */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#0F172A' }}>
                        {fact.display_name || fact.field_name.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          backgroundColor: '#F1F5F9',
                          color: '#475569',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                        }}
                      >
                        {category}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                          padding: '0.2rem 0.6rem',
                          borderRadius: '4px',
                          backgroundColor: isSupported ? '#DCFCE7' : '#FEF3C7',
                          color: isSupported ? '#166534' : '#92400E',
                        }}
                      >
                        {fact.verification_status.toUpperCase()}
                      </span>
                      {fact.confidence != null && (
                        <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
                          Confidence: {Math.round(fact.confidence * 100)}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Fact Value */}
                  <div
                    style={{
                      fontSize: '1rem',
                      fontWeight: 600,
                      color: '#1E293B',
                      backgroundColor: '#F8FAFC',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '6px',
                      border: '1px solid #E2E8F0',
                    }}
                  >
                    Extracted Value:{' '}
                    <span style={{ color: '#7C3AED' }}>
                      {String(fact.extracted_value ?? fact.original_value ?? 'N/A')}
                    </span>
                    {fact.original_value && String(fact.original_value) !== String(fact.extracted_value) && (
                      <span style={{ fontSize: '0.75rem', color: '#64748B', marginLeft: '0.5rem' }}>
                        (raw: "{fact.original_value}")
                      </span>
                    )}
                  </div>

                  {/* Supporting Passage Quote */}
                  {fact.supporting_text ? (
                    <div
                      style={{
                        position: 'relative',
                        backgroundColor: '#FBFBFE',
                        borderLeft: '4px solid #7C3AED',
                        borderRadius: '0 6px 6px 0',
                        padding: '0.75rem 1rem 0.75rem 2rem',
                        fontSize: '0.8125rem',
                        color: '#334155',
                        lineHeight: 1.5,
                        fontStyle: 'italic',
                      }}
                    >
                      <Quote
                        size={14}
                        color="#7C3AED"
                        style={{ position: 'absolute', left: '8px', top: '12px' }}
                      />
                      "{fact.supporting_text}"
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontStyle: 'italic' }}>
                      No verbatim passage available.
                    </div>
                  )}

                  {/* Document & Page Citation Footer */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '0.75rem',
                      color: '#64748B',
                      borderTop: '1px solid #F1F5F9',
                      paddingTop: '0.5rem',
                    }}
                  >
                    <span>
                      Source: <strong>{fact.filename || 'Unknown Document'}</strong>
                    </span>
                    <span>
                      Page: <strong>{fact.page_number ?? 'N/A'}</strong>
                    </span>
                  </div>
                </div>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
};
