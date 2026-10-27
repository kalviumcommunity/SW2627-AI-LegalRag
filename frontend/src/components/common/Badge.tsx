import { CheckCircle2, Clock, AlertCircle, FileText, HelpCircle } from 'lucide-react';
import type { IngestionStatus, SourceType, EvidenceStatus } from '../../api/types';

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
