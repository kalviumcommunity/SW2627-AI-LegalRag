import React, { useEffect, useState, useCallback } from 'react';
import {
  Building,
  Plus,
  RefreshCw,
  Search,
  ChevronRight,
  ArrowLeft,
  FileText,
} from 'lucide-react';
import { Card } from '../components/common/Card';
import { Modal } from '../components/common/Modal';
import { PropertyExtractionDashboard } from '../components/property/PropertyExtractionDashboard';
import { propertiesApi } from '../api/properties';
import { useToast } from '../components/common/Toast';
import { useAuth } from '../context/AuthContext';
import type {
  PropertyItem,
  PropertyExtractionResponse,
} from '../api/types';

interface PropertiesPageProps {
  onNavigate: (page: string, params?: { docId?: string; question?: string; propertyId?: string }) => void;
  selectedPropertyId?: string;
}

export const PropertiesPage: React.FC<PropertiesPageProps> = ({
  onNavigate: _onNavigate,
  selectedPropertyId,
}) => {
  const { isAuthenticated, openAuthModal } = useAuth();
  const [properties, setProperties] = useState<PropertyItem[]>([]);
  const [activeProperty, setActiveProperty] = useState<PropertyItem | null>(null);
  const [extraction, setExtraction] = useState<PropertyExtractionResponse | null>(null);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingExtraction, setLoadingExtraction] = useState<boolean>(false);
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

  useEffect(() => {
    if (activeProperty) {
      fetchExtraction(activeProperty.id);
    } else {
      setExtraction(null);
    }
  }, [activeProperty, fetchExtraction]);

  // Trigger extraction
  const handleTriggerExtract = async () => {
    if (!activeProperty) return;
    try {
      setLoadingExtraction(true);
      const res = await propertiesApi.extract(activeProperty.id);
      setExtraction(res);
      showSuccess(`Extracted structured facts for "${activeProperty.name}".`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Extraction failed';
      showError(msg);
    } finally {
      setLoadingExtraction(false);
    }
  };

  // Refresh extraction
  const handleRefreshExtract = async () => {
    if (!activeProperty) return;
    try {
      setLoadingExtraction(true);
      const res = await propertiesApi.refreshExtraction(activeProperty.id);
      setExtraction(res);
      showSuccess(`Refreshed structured extraction for "${activeProperty.name}".`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Refresh failed';
      showError(msg);
    } finally {
      setLoadingExtraction(false);
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
            Property Due Diligence
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#64748B', marginTop: '0.25rem', marginBottom: 0 }}>
            Structured property information extraction, multi-document aggregation, and legal conflict detection.
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

      {/* Main Split Layout: Properties List Selector & Extraction Dashboard */}
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

        {/* Right Column: Structured Extraction Dashboard */}
        {activeProperty ? (
          <PropertyExtractionDashboard
            propertyName={activeProperty.name}
            propertyId={activeProperty.id}
            extractionResponse={extraction}
            loading={loadingExtraction}
            onTriggerExtract={handleTriggerExtract}
            onRefreshExtract={handleRefreshExtract}
          />
        ) : (
          <Card>
            <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
              <Building size={48} color="#94A3B8" style={{ marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#1E293B', marginBottom: '0.5rem' }}>
                Select a Property
              </h3>
              <p style={{ fontSize: '0.875rem', color: '#64748B' }}>
                Choose a property from the left list or create a new property to view extracted facts, financial details, approvals, and legal verification.
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
    </div>
  );
};

