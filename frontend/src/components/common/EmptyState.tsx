import { FolderOpen } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionText,
  onAction,
  icon,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1.5rem',
        textAlign: 'center',
        borderRadius: 'var(--radius-card)',
        backgroundColor: '#FCFAF7',
        border: '1.5px dashed var(--border-lavender)',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-lavender)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--primary-purple)',
          marginBottom: '1rem',
        }}
      >
        {icon || <FolderOpen size={28} />}
      </div>
      <h4 style={{ fontSize: '1.125rem', marginBottom: '0.4rem', color: 'var(--text-heading)' }}>
        {title}
      </h4>
      <p
        style={{
          fontSize: '0.875rem',
          color: 'var(--text-muted)',
          maxWidth: '380px',
          marginBottom: actionText ? '1.25rem' : '0',
        }}
      >
        {description}
      </p>
      {actionText && onAction && (
        <button onClick={onAction} className="btn-primary" style={{ padding: '0.5rem 1.25rem' }}>
          {actionText}
        </button>
      )}
    </div>
  );
};
