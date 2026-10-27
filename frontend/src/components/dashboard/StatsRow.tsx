import React from 'react';
import { FileText, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { Card } from '../common/Card';
import { Skeleton } from '../common/Skeleton';

export interface DocumentStats {
  total: number;
  processed: number;
  ocrRequired: number;
  failed: number;
}

interface StatsRowProps {
  stats: DocumentStats;
  loading?: boolean;
  onFilterClick?: (status: string | null) => void;
}

export const StatsRow: React.FC<StatsRowProps> = ({ stats, loading = false, onFilterClick }) => {
  const statItems = [
    {
      id: 'total',
      label: 'Total Documents',
      subtext: 'All uploaded files',
      value: stats.total,
      icon: FileText,
      iconColor: '#6D28D9',
      bgColor: '#EDE9FE',
      statusFilter: null,
    },
    {
      id: 'processed',
      label: 'Processed',
      subtext: 'Ready for Q&A',
      value: stats.processed,
      icon: CheckCircle2,
      iconColor: '#16A34A',
      bgColor: '#DCFCE7',
      statusFilter: 'processed',
    },
    {
      id: 'ocr',
      label: 'OCR Required',
      subtext: 'Scanned or no text',
      value: stats.ocrRequired,
      icon: Clock,
      iconColor: '#D97706',
      bgColor: '#FEF3C7',
      statusFilter: 'ocr_required',
    },
    {
      id: 'failed',
      label: 'Failed',
      subtext: 'Could not be processed',
      value: stats.failed,
      icon: AlertCircle,
      iconColor: '#DC2626',
      bgColor: '#FEE2E2',
      statusFilter: 'failed',
    },
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
        gap: '1.25rem',
        marginBottom: '2rem',
      }}
    >
      {statItems.map((item) => {
        const Icon = item.icon;
        return (
          <Card
            key={item.id}
            padding="md"
            onClick={() => onFilterClick && onFilterClick(item.statusFilter)}
            style={{
              cursor: onFilterClick ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
            }}
          >
            {/* Left Icon Square */}
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                backgroundColor: item.bgColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Icon size={24} color={item.iconColor} />
            </div>

            {/* Right Value & Labels */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {loading ? (
                <>
                  <Skeleton width="40px" height="28px" style={{ marginBottom: '4px' }} />
                  <Skeleton width="90px" height="14px" />
                </>
              ) : (
                <>
                  <div
                    style={{
                      fontFamily: 'var(--font-heading)',
                      fontSize: '1.65rem',
                      fontWeight: 700,
                      color: 'var(--text-heading)',
                      lineHeight: 1.1,
                    }}
                  >
                    {item.value}
                  </div>
                  <div
                    style={{
                      fontSize: '0.875rem',
                      fontWeight: 600,
                      color: '#1F2937',
                      marginTop: '0.15rem',
                    }}
                  >
                    {item.label}
                  </div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: '#6B7280',
                      marginTop: '0.1rem',
                    }}
                  >
                    {item.subtext}
                  </div>
                </>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
};
