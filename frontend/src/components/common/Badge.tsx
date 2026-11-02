import { CheckCircle2, Clock, AlertCircle, FileText, HelpCircle } from 'lucide-react';
import type { IngestionStatus, SourceType, EvidenceStatus, DocumentClassificationCategory, DocumentOcrStatus } from '../../api/types';

interface StatusBadgeProps {
  status: IngestionStatus;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const iconSize = size === 'sm' ? 12 : 14;

  if (status === 'processed') {
    return (
      <span className="badge badge-processed" title="Document successfully chunked, embedded, and stored">
        <CheckCircle2 size={iconSize} />
        <span>Processed</span>
      </span>
    );
  }

  if (status === 'ocr_required') {
    return (
      <span className="badge badge-ocr" title="Document contains scanned pages or unreadable text requiring OCR">
        <Clock size={iconSize} />
        <span>OCR Required</span>
      </span>
    );
  }

  return (
    <span className="badge badge-failed" title="Document could not be processed">
      <AlertCircle size={iconSize} />
      <span>Failed</span>
    </span>
  );
};

interface SourceTypeBadgeProps {
  type: SourceType;
}

export const SourceTypeBadge: React.FC<SourceTypeBadgeProps> = ({ type }) => {
  const normalized = (type || '').toLowerCase();
  let colorStyle = {
    bg: '#F3F4F6',
    text: '#374151',
    border: '#E5E7EB',
    label: 'FILE',
  };

  if (normalized === 'pdf') {
    colorStyle = {
      bg: '#FEE2E2',
      text: '#DC2626',
      border: '#FCA5A5',
      label: 'PDF',
    };
  } else if (normalized === 'txt') {
    colorStyle = {
      bg: '#DBEAFE',
      text: '#2563EB',
      border: '#BFDBFE',
      label: 'TXT',
    };
  } else if (normalized === 'markdown' || normalized === 'md') {
    colorStyle = {
      bg: '#EDE9FE',
      text: '#7C3AED',
      border: '#DDD6FE',
      label: 'MD',
    };
  } else if (['image', 'png', 'jpg', 'jpeg'].includes(normalized)) {
    colorStyle = {
      bg: '#FEF3C7',
      text: '#D97706',
      border: '#FDE68A',
      label: 'IMG',
    };
  }

  return (
    <span
      className="badge"
      style={{
        backgroundColor: colorStyle.bg,
        color: colorStyle.text,
        borderColor: colorStyle.border,
        fontWeight: 700,
        letterSpacing: '0.04em',
      }}
    >
      <FileText size={12} />
      <span>{colorStyle.label}</span>
    </span>
  );
};

interface EvidenceStatusBadgeProps {
  status: EvidenceStatus;
}

export const EvidenceStatusBadge: React.FC<EvidenceStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'supported':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#DCFCE7',
            color: '#15803D',
            borderColor: '#86EFAC',
            fontSize: '0.8125rem',
            padding: '0.35rem 0.85rem',
          }}
          title="Answer is strictly supported by retrieved document excerpts with verifiable citations."
        >
          <CheckCircle2 size={15} />
          <span>Supported by Evidence</span>
        </span>
      );
    case 'insufficient_evidence':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEF3C7',
            color: '#B45309',
            borderColor: '#FDE047',
            fontSize: '0.8125rem',
            padding: '0.35rem 0.85rem',
          }}
          title="Documents provide partial information; some aspects could not be grounded."
        >
          <Clock size={15} />
          <span>Insufficient Evidence</span>
        </span>
      );
    case 'conflicting_evidence':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FFEDD5',
            color: '#C2410C',
            borderColor: '#FDBA74',
            fontSize: '0.8125rem',
            padding: '0.35rem 0.85rem',
          }}
          title="Retrieved documents present contradictory statements or conflicting data."
        >
          <AlertCircle size={15} />
          <span>Conflicting Evidence</span>
        </span>
      );
    case 'no_relevant_sources':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEE2E2',
            color: '#DC2626',
            borderColor: '#FCA5A5',
            fontSize: '0.8125rem',
            padding: '0.35rem 0.85rem',
          }}
          title="No uploaded documents match the question keywords or concepts."
        >
          <HelpCircle size={15} />
          <span>No Relevant Sources</span>
        </span>
      );
  }
};

import type { FactVerificationStatus } from '../../api/types';

interface FactVerificationBadgeProps {
  status: FactVerificationStatus;
  size?: 'sm' | 'md';
}

export const FactVerificationBadge: React.FC<FactVerificationBadgeProps> = ({
  status,
  size = 'md',
}) => {
  const iconSize = size === 'sm' ? 12 : 14;
  const padding = size === 'sm' ? '0.2rem 0.5rem' : '0.35rem 0.75rem';
  const fontSize = size === 'sm' ? '0.75rem' : '0.8125rem';

  switch (status) {
    case 'supported':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#DCFCE7',
            color: '#15803D',
            borderColor: '#86EFAC',
            fontSize,
            padding,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontWeight: 600,
            borderRadius: '9999px',
            border: '1px solid #86EFAC',
          }}
          title="Extracted fact is supported by verified source passage in document."
        >
          <CheckCircle2 size={iconSize} />
          <span>Supported</span>
        </span>
      );
    case 'unverified':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEF3C7',
            color: '#B45309',
            borderColor: '#FDE047',
            fontSize,
            padding,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontWeight: 600,
            borderRadius: '9999px',
            border: '1px solid #FDE047',
          }}
          title="Extracted fact is not fully corroborated by supporting text."
        >
          <Clock size={iconSize} />
          <span>Unverified</span>
        </span>
      );
    case 'conflicting':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEE2E2',
            color: '#DC2626',
            borderColor: '#FCA5A5',
            fontSize,
            padding,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontWeight: 600,
            borderRadius: '9999px',
            border: '1px solid #FCA5A5',
          }}
          title="Discrepancy detected across multiple associated documents."
        >
          <AlertCircle size={iconSize} />
          <span>Conflicting</span>
        </span>
      );
    case 'missing':
    default:
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#F1F5F9',
            color: '#64748B',
            borderColor: '#CBD5E1',
            fontSize,
            padding,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontWeight: 600,
            borderRadius: '9999px',
            border: '1px solid #CBD5E1',
          }}
          title="Fact not found in any uploaded document."
        >
          <HelpCircle size={iconSize} />
          <span>Missing</span>
        </span>
      );
  }
};


// --- Phase 12: Risk Assessment Badges ---

import type { RiskSeverity, RiskFindingStatus } from '../../api/types';

interface RiskSeverityBadgeProps {
  severity: RiskSeverity;
  size?: 'sm' | 'md';
}

export const RiskSeverityBadge: React.FC<RiskSeverityBadgeProps> = ({
  severity,
  size = 'md',
}) => {
  const iconSize = size === 'sm' ? 12 : 14;
  const padding = size === 'sm' ? '0.2rem 0.5rem' : '0.35rem 0.75rem';
  const fontSize = size === 'sm' ? '0.75rem' : '0.8125rem';

  const configs: Record<
    RiskSeverity,
    { bg: string; text: string; border: string; label: string }
  > = {
    critical: {
      bg: '#FEE2E2',
      text: '#991B1B',
      border: '#F87171',
      label: 'CRITICAL',
    },
    high: {
      bg: '#FFEDD5',
      text: '#C2410C',
      border: '#FB923C',
      label: 'HIGH',
    },
    medium: {
      bg: '#FEF3C7',
      text: '#B45309',
      border: '#FBBF24',
      label: 'MEDIUM',
    },
    low: {
      bg: '#E0F2FE',
      text: '#0369A1',
      border: '#7DD3FC',
      label: 'LOW',
    },
    informational: {
      bg: '#F1F5F9',
      text: '#475569',
      border: '#CBD5E1',
      label: 'INFO',
    },
  };

  const cfg = configs[severity] || configs.informational;

  return (
    <span
      className="badge"
      style={{
        backgroundColor: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.border}`,
        fontSize,
        padding,
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        borderRadius: '6px',
      }}
    >
      <AlertCircle size={iconSize} />
      <span>{cfg.label}</span>
    </span>
  );
};

interface RiskFindingStatusBadgeProps {
  status: RiskFindingStatus;
  size?: 'sm' | 'md';
}

export const RiskFindingStatusBadge: React.FC<RiskFindingStatusBadgeProps> = ({
  status,
  size = 'md',
}) => {
  const iconSize = size === 'sm' ? 12 : 14;
  const padding = size === 'sm' ? '0.2rem 0.5rem' : '0.35rem 0.75rem';
  const fontSize = size === 'sm' ? '0.75rem' : '0.8125rem';

  const configs: Record<
    RiskFindingStatus,
    { bg: string; text: string; border: string; label: string }
  > = {
    open: {
      bg: '#FEF2F2',
      text: '#DC2626',
      border: '#FECACA',
      label: 'Open',
    },
    under_review: {
      bg: '#EFF6FF',
      text: '#2563EB',
      border: '#BFDBFE',
      label: 'Under Review',
    },
    resolved: {
      bg: '#F0FDF4',
      text: '#16A34A',
      border: '#BBF7D0',
      label: 'Resolved',
    },
    dismissed: {
      bg: '#F8FAFC',
      text: '#64748B',
      border: '#E2E8F0',
      label: 'Dismissed',
    },
  };

  const cfg = configs[status] || configs.open;

  return (
    <span
      className="badge"
      style={{
        backgroundColor: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.border}`,
        fontSize,
        padding,
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontWeight: 600,
        borderRadius: '9999px',
      }}
    >
      {status === 'resolved' ? (
        <CheckCircle2 size={iconSize} />
      ) : status === 'under_review' ? (
        <Clock size={iconSize} />
      ) : (
        <AlertCircle size={iconSize} />
      )}
      <span>{cfg.label}</span>
    </span>
  );
};


export interface DocumentOcrStatusBadgeProps {
  status?: DocumentOcrStatus | null;
  size?: 'sm' | 'md';
}

export const DocumentOcrStatusBadge: React.FC<DocumentOcrStatusBadgeProps> = ({
  status,
  size = 'md',
}) => {
  if (!status) return null;
  const iconSize = size === 'sm' ? 12 : 14;

  switch (status) {
    case 'ocr_completed':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#DCFCE7',
            color: '#15803D',
            borderColor: '#86EFAC',
            fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
            padding: size === 'sm' ? '0.2rem 0.5rem' : '0.25rem 0.65rem',
          }}
          title="Text successfully extracted from scanned pages via OCR"
        >
          <CheckCircle2 size={iconSize} />
          <span>OCR Completed</span>
        </span>
      );
    case 'processing_ocr':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEF3C7',
            color: '#B45309',
            borderColor: '#FDE047',
            fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
            padding: size === 'sm' ? '0.2rem 0.5rem' : '0.25rem 0.65rem',
          }}
          title="OCR engine is currently processing scanned pages"
        >
          <Clock size={iconSize} />
          <span>Processing OCR</span>
        </span>
      );
    case 'pending_ocr':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#EFF6FF',
            color: '#2563EB',
            borderColor: '#BFDBFE',
            fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
            padding: size === 'sm' ? '0.2rem 0.5rem' : '0.25rem 0.65rem',
          }}
          title="Queued for OCR processing"
        >
          <Clock size={iconSize} />
          <span>Pending OCR</span>
        </span>
      );
    case 'needs_manual_review':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FFF7ED',
            color: '#EA580C',
            borderColor: '#FDBA74',
            fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
            padding: size === 'sm' ? '0.2rem 0.5rem' : '0.25rem 0.65rem',
          }}
          title="Low OCR confidence or empty scanned pages require manual inspection"
        >
          <AlertCircle size={iconSize} />
          <span>Needs Manual Review</span>
        </span>
      );
    case 'ocr_failed':
      return (
        <span
          className="badge"
          style={{
            backgroundColor: '#FEE2E2',
            color: '#DC2626',
            borderColor: '#FCA5A5',
            fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
            padding: size === 'sm' ? '0.2rem 0.5rem' : '0.25rem 0.65rem',
          }}
          title="OCR processing failed for this document"
        >
          <AlertCircle size={iconSize} />
          <span>OCR Failed</span>
        </span>
      );
    default:
      return null;
  }
};

export interface DocumentCategoryBadgeProps {
  category?: DocumentClassificationCategory | string | null;
  confidence?: number | null;
  manuallyCorrected?: boolean;
  size?: 'sm' | 'md';
}

export const DocumentCategoryBadge: React.FC<DocumentCategoryBadgeProps> = ({
  category,
  confidence,
  manuallyCorrected,
  size = 'md',
}) => {
  if (!category) return null;
  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <span
      className="badge"
      style={{
        backgroundColor: '#F3E8FF',
        color: '#6B21A8',
        borderColor: '#D8B4FE',
        fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
        padding: size === 'sm' ? '0.2rem 0.55rem' : '0.25rem 0.7rem',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontWeight: 600,
        borderRadius: '9999px',
      }}
      title={`Classified as ${category}${confidence ? ` (${Math.round(confidence * 100)}% confidence)` : ''}${manuallyCorrected ? ' [Manually Corrected]' : ''}`}
    >
      <FileText size={iconSize} />
      <span>{category}</span>
      {manuallyCorrected && (
        <span style={{ fontSize: '0.65rem', opacity: 0.8 }}>(edited)</span>
      )}
    </span>
  );
};
