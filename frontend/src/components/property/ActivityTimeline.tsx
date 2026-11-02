import React, { useEffect, useState, useCallback } from 'react';
import {
  Clock,
  Building,
  FileText,
  FileCheck,
  ShieldAlert,
  CheckCircle,
  RefreshCw,
  AlertCircle,
  MessageSquare,
} from 'lucide-react';
import { Card } from '../common/Card';
import { propertiesApi } from '../../api/properties';
import type { PropertyActivityEvent } from '../../api/types';

interface ActivityTimelineProps {
  propertyId: string;
  propertyName: string;
}

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({
  propertyId,
  propertyName,
}) => {
  const [events, setEvents] = useState<PropertyActivityEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchActivity = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await propertiesApi.getActivity(propertyId);
      setEvents(res.events || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch activity history';
      setError(msg);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => {
    fetchActivity();
  }, [fetchActivity]);

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'property_created':
        return <Building size={16} color="#7C3AED" />;
      case 'document_associated':
        return <FileText size={16} color="#2563EB" />;
      case 'extraction_completed':
        return <FileCheck size={16} color="#059669" />;
      case 'risk_assessed':
        return <ShieldAlert size={16} color="#DC2626" />;
      case 'finding_status_updated':
        return <MessageSquare size={16} color="#D97706" />;
      default:
        return <Clock size={16} color="#64748B" />;
    }
  };

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <Card>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0F172A', margin: 0 }}>
              Activity History & Audit Trail
            </h3>
            <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: '0.25rem 0 0 0' }}>
              Chronological log of document uploads, extraction runs, and risk reviews for "{propertyName}".
            </p>
          </div>

          <button
            onClick={fetchActivity}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.4rem 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              borderRadius: '6px',
              border: '1px solid #CBD5E1',
              backgroundColor: '#FFFFFF',
              color: '#475569',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.875rem' }}>
            <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 0.5rem auto' }} />
            Loading activity timeline...
          </div>
        ) : error ? (
          <div
            style={{
              padding: '1rem',
              backgroundColor: '#FEF2F2',
              border: '1px solid #FECDD3',
              borderRadius: '6px',
              color: '#991B1B',
              fontSize: '0.8125rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <AlertCircle size={16} />
            {error}
          </div>
        ) : events.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8', fontSize: '0.875rem' }}>
            <Clock size={28} style={{ margin: '0 auto 0.5rem auto' }} />
            No activity events recorded yet.
          </div>
        ) : (
          <div style={{ position: 'relative', paddingLeft: '1.5rem', borderLeft: '2px solid #E2E8F0', marginLeft: '0.5rem' }}>
            {events.map((evt, idx) => (
              <div
                key={evt.event_id || idx}
                style={{
                  position: 'relative',
                  marginBottom: idx === events.length - 1 ? 0 : '1.5rem',
                }}
              >
                {/* Event Dot */}
                <div
                  style={{
                    position: 'absolute',
                    left: '-2rem',
                    top: '2px',
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: '#FFFFFF',
                    border: '2px solid #CBD5E1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {getEventIcon(evt.event_type)}
                </div>

                {/* Event Card */}
                <div
                  style={{
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #E2E8F0',
                    borderRadius: '6px',
                    padding: '0.75rem 1rem',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1E293B' }}>
                      {evt.title}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>
                      {formatTimestamp(evt.timestamp)}
                    </span>
                  </div>

                  <p style={{ fontSize: '0.8125rem', color: '#475569', margin: '0.35rem 0 0 0', lineHeight: 1.4 }}>
                    {evt.description}
                  </p>

                  {/* Metadata Chips if present */}
                  {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.35rem',
                        marginTop: '0.5rem',
                      }}
                    >
                      {Object.entries(evt.metadata).map(([k, v]) => (
                        <span
                          key={k}
                          style={{
                            fontSize: '0.6875rem',
                            backgroundColor: '#FFFFFF',
                            border: '1px solid #E2E8F0',
                            padding: '0.1rem 0.4rem',
                            borderRadius: '4px',
                            color: '#64748B',
                          }}
                        >
                          <strong>{k.replace(/_/g, ' ')}:</strong> {String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
};

