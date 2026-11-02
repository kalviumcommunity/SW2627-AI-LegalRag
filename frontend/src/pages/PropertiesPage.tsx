import React, { useEffect, useState, useCallback } from 'react';
import {
  Building,
  Plus,
  RefreshCw,
  Search,
  ChevronRight,
  FileText,
  ShieldAlert,
  Download,
  CheckSquare,
  FileSearch,
  History,
  FolderOpen,
  Upload,
  Link2,
  Unlink,
  ExternalLink,
} from 'lucide-react';
import { StatusBadge, SourceTypeBadge } from '../components/common/Badge';
import { UploadZone } from '../components/dashboard/UploadZone';
import { documentsApi } from '../api/documents';
import { Card } from '../components/common/Card';
import { Modal } from '../components/common/Modal';
import { PropertyExtractionDashboard } from '../components/property/PropertyExtractionDashboard';
import { PropertyRiskDashboard } from '../components/property/PropertyRiskDashboard';
import { DueDiligenceChecklist } from '../components/property/DueDiligenceChecklist';
import { EvidenceExplorer } from '../components/property/EvidenceExplorer';
import { ActivityTimeline } from '../components/property/ActivityTimeline';
import { propertiesApi } from '../api/properties';
import { riskApi } from '../api/risk';
import { useToast } from '../components/common/Toast';
import { useAuth } from '../context/AuthContext';
import type {
  PropertyItem,
  PropertyExtractionResponse,
  PropertyRiskAssessmentResponse,
  RiskFindingStatus,
  DocumentSummary,
} from '../api/types';

interface PropertiesPageProps {
  onNavigate: (page: string, params?: { docId?: string; question?: string; propertyId?: string }) => void;
  selectedPropertyId?: string;
}

type TabType = 'risk' | 'extraction' | 'checklist' | 'evidence' | 'activity' | 'documents';

export const PropertiesPage: React.FC<PropertiesPageProps> = ({
  onNavigate: _onNavigate,
  selectedPropertyId,
}) => {
  const { isAuthenticated, openAuthModal } = useAuth();
  const [properties, setProperties] = useState<PropertyItem[]>([]);
  const [activeProperty, setActiveProperty] = useState<PropertyItem | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('risk');

  // Extraction State
  const [extraction, setExtraction] = useState<PropertyExtractionResponse | null>(null);
  const [loadingExtraction, setLoadingExtraction] = useState<boolean>(false);

  // Risk Assessment State
  const [riskAssessment, setRiskAssessment] = useState<PropertyRiskAssessmentResponse | null>(null);
  const [loadingRisk, setLoadingRisk] = useState<boolean>(false);

  // PDF Export State
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);

  // Property Documents State
  const [propertyDocs, setPropertyDocs] = useState<DocumentSummary[]>([]);
  const [loadingPropertyDocs, setLoadingPropertyDocs] = useState<boolean>(false);
  const [isPropertyUploadOpen, setIsPropertyUploadOpen] = useState<boolean>(false);
  const [isAttachExistingOpen, setIsAttachExistingOpen] = useState<boolean>(false);
  const [availableDocsToAttach, setAvailableDocsToAttach] = useState<DocumentSummary[]>([]);
  const [loadingAvailableDocs, setLoadingAvailableDocs] = useState<boolean>(false);
  const [attachingDocId, setAttachingDocId] = useState<string | null>(null);
  const [disassociatingDocId, setDisassociatingDocId] = useState<string | null>(null);

  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Create Property Modal
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [newPropName, setNewPropName] = useState<string>('');
  const [newPropAddress, setNewPropAddress] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const { showSuccess, showError } = useToast();

  // Load properties list
  const fetchProperties = useCallback(async () => {
    try {
      setLoadingList(true);
      const res = await propertiesApi.list(1, 50);
      const items = res.items || [];
      setProperties(items);

      if (selectedPropertyId) {
        const found = items.find((p) => p.id === selectedPropertyId);
        if (found) {
          setActiveProperty(found);
        }
      } else if (items.length > 0 && !activeProperty) {
        setActiveProperty(items[0]);
      }
    } catch (err: unknown) {
      console.warn('Failed to fetch properties:', err);
      setProperties([]);
    } finally {
      setLoadingList(false);
    }
  }, [selectedPropertyId, activeProperty]);

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties, isAuthenticated]);

  // Load documents for active property
  const fetchPropertyDocs = useCallback(async (propertyId: string) => {
    try {
      setLoadingPropertyDocs(true);
      const res = await propertiesApi.getDocuments(propertyId, 1, 100);
      setPropertyDocs(res.items || []);
    } catch (err: unknown) {
      console.warn('Failed to fetch property documents:', err);
      setPropertyDocs([]);
    } finally {
      setLoadingPropertyDocs(false);
    }
  }, []);

  // Associate an existing document from library
  const handleAssociateDocument = async (documentId: string) => {
    if (!activeProperty) return;
    try {
      setAttachingDocId(documentId);
      await propertiesApi.associateDocument(activeProperty.id, documentId);
      showSuccess('Document associated with property successfully.');
      setIsAttachExistingOpen(false);
      await fetchPropertyDocs(activeProperty.id);
      await fetchExtraction(activeProperty.id);
      await fetchRiskAssessment(activeProperty.id);
      await fetchProperties();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Association failed';
      showError(msg);
    } finally {
      setAttachingDocId(null);
    }
  };

  // Disassociate document
  const handleDisassociateDocument = async (documentId: string) => {
    if (!activeProperty) return;
    try {
      setDisassociatingDocId(documentId);
      await propertiesApi.disassociateDocument(activeProperty.id, documentId);
      showSuccess('Document disassociated from property.');
      await fetchPropertyDocs(activeProperty.id);
      await fetchExtraction(activeProperty.id);
      await fetchRiskAssessment(activeProperty.id);
      await fetchProperties();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Disassociation failed';
      showError(msg);
    } finally {
      setDisassociatingDocId(null);
    }
  };

  // Open modal to attach existing unassociated documents
  const handleOpenAttachModal = async () => {
    if (!activeProperty) return;
    setIsAttachExistingOpen(true);
    try {
      setLoadingAvailableDocs(true);
      const res = await documentsApi.list({ page: 1, page_size: 100 });
      const currentIds = new Set(propertyDocs.map((d) => d.document_id));
      const unattached = (res.items || []).filter((d) => !currentIds.has(d.document_id));
      setAvailableDocsToAttach(unattached);
    } catch (err: unknown) {
      console.warn('Failed to load available documents:', err);
      setAvailableDocsToAttach([]);
    } finally {
      setLoadingAvailableDocs(false);
    }
  };

  // Load extraction for active property
  const fetchExtraction = useCallback(async (propertyId: string) => {
    try {
      setLoadingExtraction(true);
      const res = await propertiesApi.getExtraction(propertyId);
      setExtraction(res);
    } catch (err: unknown) {
      console.warn('Failed to fetch extraction:', err);
      setExtraction(null);
    } finally {
      setLoadingExtraction(false);
    }
  }, []);

  // Load risk assessment for active property
  const fetchRiskAssessment = useCallback(async (propertyId: string) => {
    try {
      setLoadingRisk(true);
      const res = await riskApi.getAssessment(propertyId);
      setRiskAssessment(res);
    } catch (err: unknown) {
      console.warn('Failed to fetch risk assessment:', err);
      setRiskAssessment(null);
    } finally {
      setLoadingRisk(false);
    }
  }, []);

  useEffect(() => {
    if (activeProperty) {
      fetchPropertyDocs(activeProperty.id);
      fetchExtraction(activeProperty.id);
      fetchRiskAssessment(activeProperty.id);
    } else {
      setPropertyDocs([]);
      setExtraction(null);
      setRiskAssessment(null);
    }
  }, [activeProperty, fetchPropertyDocs, fetchExtraction, fetchRiskAssessment]);

  // Extraction handlers
  const handleTriggerExtract = async () => {
    if (!activeProperty) return;
    try {
      setLoadingExtraction(true);
      const res = await propertiesApi.extract(activeProperty.id);
      setExtraction(res);
      showSuccess(`Extracted structured facts for "${activeProperty.name}".`);
      fetchRiskAssessment(activeProperty.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Extraction failed';
      showError(msg);
    } finally {
      setLoadingExtraction(false);
    }
  };

  const handleRefreshExtract = async () => {
    if (!activeProperty) return;
    try {
      setLoadingExtraction(true);
      const res = await propertiesApi.refreshExtraction(activeProperty.id);
      setExtraction(res);
      showSuccess(`Refreshed structured extraction for "${activeProperty.name}".`);
      fetchRiskAssessment(activeProperty.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Refresh failed';
      showError(msg);
    } finally {
      setLoadingExtraction(false);
    }
  };

  // Risk Assessment handlers
  const handleTriggerAssess = async () => {
    if (!activeProperty) return;
    try {
      setLoadingRisk(true);
      const res = await riskApi.assess(activeProperty.id);
      setRiskAssessment(res);
      showSuccess(`Due diligence risk assessment completed for "${activeProperty.name}".`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Risk assessment failed';
      showError(msg);
    } finally {
      setLoadingRisk(false);
    }
  };

  const handleRefreshAssess = async () => {
    if (!activeProperty) return;
    try {
      setLoadingRisk(true);
      const res = await riskApi.refresh(activeProperty.id);
      setRiskAssessment(res);
      showSuccess(`Refreshed due diligence assessment for "${activeProperty.name}".`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Refresh failed';
      showError(msg);
    } finally {
      setLoadingRisk(false);
    }
  };

  const handleUpdateFindingStatus = async (
    riskId: string,
    status: RiskFindingStatus,
    notes?: string
  ) => {
    if (!activeProperty) return;
    try {
      const updated = await riskApi.updateFinding(activeProperty.id, riskId, {
        status,
        user_notes: notes,
      });

      // Update in local state
      setRiskAssessment((prev) => {
        if (!prev) return prev;
        const findings = prev.findings.map((f) => (f.risk_id === riskId ? updated : f));
        let openCount = 0;
        let underReviewCount = 0;
        let resolvedCount = 0;
        let dismissedCount = 0;
        for (const f of findings) {
          if (f.status === 'open') openCount++;
          else if (f.status === 'under_review') underReviewCount++;
          else if (f.status === 'resolved') resolvedCount++;
          else if (f.status === 'dismissed') dismissedCount++;
        }
        return {
          ...prev,
          findings,
          summary: {
            ...prev.summary,
            open_count: openCount,
            under_review_count: underReviewCount,
            resolved_count: resolvedCount,
            dismissed_count: dismissedCount,
          },
        };
      });

      showSuccess(`Finding updated to ${status}.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update finding status';
      showError(msg);
      throw err;
    }
  };

  // PDF Export Handler
  const handleExportPdf = async () => {
    if (!activeProperty) return;
    try {
      setIsExportingPdf(true);
      await propertiesApi.downloadReportPdf(activeProperty.id, activeProperty.name);
      showSuccess(`Due diligence report for "${activeProperty.name}" downloaded.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to download report.';
      showError(msg);
    } finally {
      setIsExportingPdf(false);
    }
  };

  // Create property submit
  const handleCreateProperty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPropName.trim()) return;

    try {
      setIsSubmitting(true);
      const created = await propertiesApi.create({
        name: newPropName.trim(),
        address: newPropAddress.trim() || undefined,
      });
      showSuccess(`Property "${created.name}" created successfully.`);
      setIsCreateOpen(false);
      setNewPropName('');
      setNewPropAddress('');
      await fetchProperties();
      setActiveProperty(created);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create property';
      showError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredProperties = properties.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
            Property Due Diligence & Risk Intelligence
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#64748B', marginTop: '0.25rem', marginBottom: 0 }}>
            Evidence-backed legal risk assessment, multi-document conflict analysis, and structured extraction.
          </p>
        </div>

        <button
          onClick={() => {
            if (!isAuthenticated) {
              openAuthModal('login');
              return;
            }
            setIsCreateOpen(true);
          }}
          className="btn btn-primary"
          style={{
            backgroundColor: '#7C3AED',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '8px',
            padding: '0.65rem 1.25rem',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            cursor: 'pointer',
          }}
        >
          <Plus size={18} />
          <span>New Property</span>
        </button>
      </div>

      {/* Main Split Layout: Properties List Selector & Analysis Dashboard */}
      <div style={{ display: 'grid', gridTemplateColumns: activeProperty ? '300px 1fr' : '1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left Column: Properties Sidebar List */}
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0F172A' }}>Properties</span>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>{properties.length} total</span>
            </div>

            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94A3B8' }} />
              <input
                type="text"
                placeholder="Search properties..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.5rem 0.5rem 2rem',
                  fontSize: '0.8125rem',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {loadingList ? (
              <div style={{ padding: '1rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.8125rem' }}>
                <RefreshCw size={16} className="animate-spin" style={{ margin: '0 auto 0.5rem auto' }} />
                Loading properties...
              </div>
            ) : filteredProperties.length === 0 ? (
              <div style={{ padding: '1.5rem 0.5rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.8125rem' }}>
                No properties found.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '500px', overflowY: 'auto' }}>
                {filteredProperties.map((p) => {
                  const isSelected = activeProperty?.id === p.id;
                  return (
                    <div
                      key={p.id}
                      onClick={() => setActiveProperty(p)}
                      style={{
                        padding: '0.75rem',
                        borderRadius: '8px',
                        backgroundColor: isSelected ? '#F3F0FF' : '#F8FAFC',
                        border: isSelected ? '1px solid #C4B5FD' : '1px solid #E2E8F0',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <div style={{ overflow: 'hidden' }}>
                        <div style={{ fontSize: '0.875rem', fontWeight: 600, color: isSelected ? '#7C3AED' : '#1E293B', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {p.name}
                        </div>
                        {p.address && (
                          <div style={{ fontSize: '0.75rem', color: '#64748B', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {p.address}
                          </div>
                        )}
                      </div>
                      <ChevronRight size={16} color={isSelected ? '#7C3AED' : '#94A3B8'} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        {/* Right Column: Tab View for Property Intelligence */}
        {activeProperty ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Property Executive Banner & PDF Export */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1rem 1.25rem',
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                border: '1px solid #E2E8F0',
                gap: '1rem',
                flexWrap: 'wrap',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Building size={20} color="#7C3AED" />
                  <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                    {activeProperty.name}
                  </h2>
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
                    {activeProperty.property_type || 'Residential'}
                  </span>
                </div>
                {activeProperty.address && (
                  <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: '0.25rem 0 0 0' }}>
                    {activeProperty.address}
                  </p>
                )}
              </div>

              <button
                onClick={handleExportPdf}
                disabled={isExportingPdf}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.6rem 1rem',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  backgroundColor: '#0F172A',
                  color: '#FFFFFF',
                  border: 'none',
                  cursor: isExportingPdf ? 'not-allowed' : 'pointer',
                  transition: 'background-color 0.15s ease',
                }}
              >
                <Download size={15} className={isExportingPdf ? 'animate-spin' : ''} />
                {isExportingPdf ? 'Generating PDF...' : 'Export Due Diligence PDF'}
              </button>
            </div>

            {/* Tab Navigation */}
            <div
              style={{
                display: 'flex',
                gap: '0.5rem',
                borderBottom: '2px solid #E2E8F0',
                paddingBottom: '0.25rem',
                flexWrap: 'wrap',
              }}
            >
              {/* Tab 1: Risk Assessment */}
              <button
                onClick={() => setActiveTab('risk')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'risk' ? '3px solid #DC2626' : '3px solid transparent',
                  backgroundColor: activeTab === 'risk' ? '#FEF2F2' : 'transparent',
                  color: activeTab === 'risk' ? '#991B1B' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <ShieldAlert size={16} color={activeTab === 'risk' ? '#DC2626' : '#94A3B8'} />
                Risk Assessment
                {riskAssessment?.summary && riskAssessment.summary.open_count > 0 && (
                  <span
                    style={{
                      backgroundColor: '#DC2626',
                      color: '#FFFFFF',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      borderRadius: '9999px',
                      padding: '0.1rem 0.5rem',
                    }}
                  >
                    {riskAssessment.summary.open_count}
                  </span>
                )}
              </button>

              {/* Tab 2: Extracted Facts */}
              <button
                onClick={() => setActiveTab('extraction')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'extraction' ? '3px solid #7C3AED' : '3px solid transparent',
                  backgroundColor: activeTab === 'extraction' ? '#F3F0FF' : 'transparent',
                  color: activeTab === 'extraction' ? '#6D28D9' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <FileText size={16} color={activeTab === 'extraction' ? '#7C3AED' : '#94A3B8'} />
                Extracted Facts
                {extraction?.data && (
                  <span
                    style={{
                      backgroundColor: '#7C3AED',
                      color: '#FFFFFF',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      borderRadius: '9999px',
                      padding: '0.1rem 0.5rem',
                    }}
                  >
                    {extraction.data.supported_count +
                      extraction.data.unverified_count +
                      extraction.data.conflicting_count}
                  </span>
                )}
              </button>

              {/* Tab 3: Due Diligence Checklist */}
              <button
                onClick={() => setActiveTab('checklist')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'checklist' ? '3px solid #059669' : '3px solid transparent',
                  backgroundColor: activeTab === 'checklist' ? '#ECFDF5' : 'transparent',
                  color: activeTab === 'checklist' ? '#065F46' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <CheckSquare size={16} color={activeTab === 'checklist' ? '#059669' : '#94A3B8'} />
                Due Diligence Checklist
              </button>

              {/* Tab 4: Evidence Explorer */}
              <button
                onClick={() => setActiveTab('evidence')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'evidence' ? '3px solid #2563EB' : '3px solid transparent',
                  backgroundColor: activeTab === 'evidence' ? '#EFF6FF' : 'transparent',
                  color: activeTab === 'evidence' ? '#1E40AF' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <FileSearch size={16} color={activeTab === 'evidence' ? '#2563EB' : '#94A3B8'} />
                Evidence Explorer
              </button>

              {/* Tab 0: Documents */}
              <button
                onClick={() => setActiveTab('documents')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'documents' ? '3px solid #0284C7' : '3px solid transparent',
                  backgroundColor: activeTab === 'documents' ? '#F0F9FF' : 'transparent',
                  color: activeTab === 'documents' ? '#0369A1' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <FolderOpen size={16} color={activeTab === 'documents' ? '#0284C7' : '#94A3B8'} />
                Documents
                <span
                  style={{
                    backgroundColor: activeTab === 'documents' ? '#0284C7' : '#E2E8F0',
                    color: activeTab === 'documents' ? '#FFFFFF' : '#475569',
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    borderRadius: '9999px',
                    padding: '0.1rem 0.5rem',
                  }}
                >
                  {propertyDocs.length}
                </span>
              </button>

              {/* Tab 5: Activity History */}
              <button
                onClick={() => setActiveTab('activity')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.65rem 1.1rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '6px 6px 0 0',
                  border: 'none',
                  borderBottom: activeTab === 'activity' ? '3px solid #475569' : '3px solid transparent',
                  backgroundColor: activeTab === 'activity' ? '#F8FAFC' : 'transparent',
                  color: activeTab === 'activity' ? '#0F172A' : '#64748B',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <History size={16} color={activeTab === 'activity' ? '#475569' : '#94A3B8'} />
                Activity History
              </button>
            </div>

            {/* Active Tab Content */}
            {activeTab === 'risk' && (
              <PropertyRiskDashboard
                propertyName={activeProperty.name}
                propertyId={activeProperty.id}
                assessmentResponse={riskAssessment}
                loading={loadingRisk}
                onTriggerAssess={handleTriggerAssess}
                onRefreshAssess={handleRefreshAssess}
                onUpdateFindingStatus={handleUpdateFindingStatus}
              />
            )}

            {activeTab === 'extraction' && (
              <PropertyExtractionDashboard
                propertyName={activeProperty.name}
                propertyId={activeProperty.id}
                extractionResponse={extraction}
                loading={loadingExtraction}
                onTriggerExtract={handleTriggerExtract}
                onRefreshExtract={handleRefreshExtract}
              />
            )}

            {activeTab === 'checklist' && (
              <DueDiligenceChecklist
                propertyName={activeProperty.name}
                propertyId={activeProperty.id}
                extraction={extraction}
                riskAssessment={riskAssessment}
                onNavigateToTab={(tab) => setActiveTab(tab)}
              />
            )}

            {activeTab === 'evidence' && (
              <EvidenceExplorer
                extraction={extraction}
                loading={loadingExtraction}
              />
            )}

            {activeTab === 'documents' && (
              <Card>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                        Associated Property Documents
                      </h3>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, backgroundColor: '#E0F2FE', color: '#0369A1', padding: '0.15rem 0.5rem', borderRadius: '9999px' }}>
                        {propertyDocs.length}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: '0.25rem 0 0 0' }}>
                      Title deeds, allotment letters, payment receipts, and legal notices associated with this property for diligence analysis.
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={handleOpenAttachModal}
                      className="btn-outline"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.85rem', fontSize: '0.8125rem' }}
                    >
                      <Link2 size={15} />
                      <span>Attach from Library</span>
                    </button>
                    <button
                      onClick={() => setIsPropertyUploadOpen(true)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.85rem', fontSize: '0.8125rem', backgroundColor: '#7C3AED', color: '#FFFFFF', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
                    >
                      <Upload size={15} />
                      <span>Upload Document</span>
                    </button>
                  </div>
                </div>

                {loadingPropertyDocs ? (
                  <div style={{ padding: '2.5rem', textAlign: 'center', color: '#64748B' }}>
                    <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#7C3AED' }} />
                    Loading associated documents...
                  </div>
                ) : propertyDocs.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '3rem 1.5rem', border: '1px dashed #CBD5E1', borderRadius: '12px' }}>
                    <FileText size={40} color="#94A3B8" style={{ margin: '0 auto 0.75rem auto' }} />
                    <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.25rem' }}>
                      No documents associated with this property yet
                    </h4>
                    <p style={{ fontSize: '0.8125rem', color: '#64748B', maxWidth: '420px', margin: '0 auto 1.25rem auto' }}>
                      Attach uploaded deeds, allotment letters, receipts, or upload new files directly to enable structured facts extraction and evidence-backed risk assessment.
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem' }}>
                      <button
                        onClick={handleOpenAttachModal}
                        className="btn-outline"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.85rem', fontSize: '0.8125rem' }}
                      >
                        <Link2 size={15} />
                        <span>Attach Existing Document</span>
                      </button>
                      <button
                        onClick={() => setIsPropertyUploadOpen(true)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.85rem', fontSize: '0.8125rem', backgroundColor: '#7C3AED', color: '#FFFFFF', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
                      >
                        <Upload size={15} />
                        <span>Upload Document</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#FAF8F5', borderBottom: '1px solid #F0EDE6', color: '#6B7280', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase' }}>
                          <th style={{ padding: '0.75rem 1rem' }}>Document</th>
                          <th style={{ padding: '0.75rem 0.75rem' }}>Type</th>
                          <th style={{ padding: '0.75rem 0.75rem' }}>Status</th>
                          <th style={{ padding: '0.75rem 0.75rem' }}>Extracted Chars</th>
                          <th style={{ padding: '0.75rem 0.75rem' }}>Chunks</th>
                          <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {propertyDocs.map((doc) => (
                          <tr key={doc.document_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                            <td style={{ padding: '0.85rem 1rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                <FileText size={16} color="#7C3AED" />
                                <div>
                                  <span style={{ fontWeight: 600, color: '#1E293B', display: 'block' }}>{doc.filename}</span>
                                  <span style={{ fontSize: '0.6875rem', color: '#94A3B8' }}>{doc.document_id}</span>
                                </div>
                              </div>
                            </td>
                            <td style={{ padding: '0.85rem 0.75rem' }}>
                              <SourceTypeBadge type={doc.source_type} />
                            </td>
                            <td style={{ padding: '0.85rem 0.75rem' }}>
                              <StatusBadge status={doc.status} />
                            </td>
                            <td style={{ padding: '0.85rem 0.75rem', color: '#475569' }}>
                              {doc.extracted_characters.toLocaleString()}
                            </td>
                            <td style={{ padding: '0.85rem 0.75rem', color: '#475569' }}>
                              {doc.chunk_count}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>
                              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                                <button
                                  onClick={() => _onNavigate('doc-detail', { docId: doc.document_id })}
                                  title="Inspect Document"
                                  className="btn-outline"
                                  style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                                >
                                  <ExternalLink size={13} />
                                  <span>Inspect</span>
                                </button>
                                <button
                                  onClick={() => handleDisassociateDocument(doc.document_id)}
                                  disabled={disassociatingDocId === doc.document_id}
                                  title="Disassociate from property"
                                  style={{ padding: '0.35rem 0.6rem', border: '1px solid #FCA5A5', borderRadius: '4px', backgroundColor: '#FEF2F2', color: '#DC2626', cursor: disassociatingDocId === doc.document_id ? 'not-allowed' : 'pointer', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontWeight: 600 }}
                                >
                                  <Unlink size={13} />
                                  <span>{disassociatingDocId === doc.document_id ? 'Unlinking...' : 'Disassociate'}</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            )}

            {activeTab === 'activity' && (
              <ActivityTimeline
                propertyId={activeProperty.id}
                propertyName={activeProperty.name}
              />
            )}
          </div>
        ) : (
          <Card>
            <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
              <Building size={48} color="#94A3B8" style={{ marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.5rem' }}>
                Select a Property
              </h3>
              <p style={{ fontSize: '0.875rem', color: '#64748B' }}>
                Choose a property from the left list or create a new property to view due diligence risk assessments, extracted facts, financial details, and approvals.
              </p>
            </div>
          </Card>
        )}
      </div>

      {/* Create Property Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Property"
      >
        <form onSubmit={handleCreateProperty} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#334155', marginBottom: '0.35rem' }}>
              Property Name *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Emerald Heights Tower A"
              value={newPropName}
              onChange={(e) => setNewPropName(e.target.value)}
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

          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#334155', marginBottom: '0.35rem' }}>
              Address / Location (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Sector 15, Kharghar, Navi Mumbai"
              value={newPropAddress}
              onChange={(e) => setNewPropAddress(e.target.value)}
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
              onClick={() => setIsCreateOpen(false)}
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
              disabled={isSubmitting || !newPropName.trim()}
              style={{
                padding: '0.5rem 1.25rem',
                backgroundColor: '#7C3AED',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                opacity: isSubmitting ? 0.7 : 1,
              }}
            >
              {isSubmitting ? 'Creating...' : 'Create Property'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Upload Document to this Property Modal */}
      {activeProperty && (
        <Modal
          isOpen={isPropertyUploadOpen}
          onClose={() => setIsPropertyUploadOpen(false)}
          title={`Upload Document to ${activeProperty.name}`}
          subtitle="Ingest and automatically associate document with this property for due diligence analysis."
          maxWidth="700px"
        >
          <UploadZone
            propertyId={activeProperty.id}
            onUploadSuccess={async () => {
              setIsPropertyUploadOpen(false);
              await fetchPropertyDocs(activeProperty.id);
              await fetchExtraction(activeProperty.id);
              await fetchRiskAssessment(activeProperty.id);
              await fetchProperties();
            }}
          />
        </Modal>
      )}

      {/* Attach Existing Document Modal */}
      {activeProperty && (
        <Modal
          isOpen={isAttachExistingOpen}
          onClose={() => setIsAttachExistingOpen(false)}
          title={`Attach Document to ${activeProperty.name}`}
          subtitle="Select an already uploaded document from your library to associate with this property."
          maxWidth="650px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {loadingAvailableDocs ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#64748B' }}>
                <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#7C3AED' }} />
                Loading your documents...
              </div>
            ) : availableDocsToAttach.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#64748B' }}>
                <p style={{ margin: 0 }}>All your uploaded documents are already associated with this property.</p>
                <button
                  onClick={() => {
                    setIsAttachExistingOpen(false);
                    setIsPropertyUploadOpen(true);
                  }}
                  style={{ marginTop: '1rem', padding: '0.5rem 1rem', backgroundColor: '#7C3AED', color: '#FFFFFF', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8125rem' }}
                >
                  Upload a New Document
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '400px', overflowY: 'auto' }}>
                {availableDocsToAttach.map((doc) => (
                  <div
                    key={doc.document_id}
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      border: '1px solid #E2E8F0',
                      backgroundColor: '#F8FAFC',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1rem',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <FileText size={16} color="#7C3AED" />
                        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#1E293B' }}>{doc.filename}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.2rem' }}>
                        {doc.source_type.toUpperCase()} &bull; {doc.chunk_count} chunk(s) &bull; Status: {doc.status}
                      </div>
                    </div>
                    <button
                      onClick={() => handleAssociateDocument(doc.document_id)}
                      disabled={attachingDocId === doc.document_id}
                      style={{
                        padding: '0.4rem 0.85rem',
                        backgroundColor: '#7C3AED',
                        color: '#FFFFFF',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: attachingDocId === doc.document_id ? 'not-allowed' : 'pointer',
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {attachingDocId === doc.document_id ? 'Attaching...' : 'Attach'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
