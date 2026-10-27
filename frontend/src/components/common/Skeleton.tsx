import React from 'react';

export const Skeleton: React.FC<{
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
  style?: React.CSSProperties;
}> = ({
  width = '100%',
  height = '1.25rem',
  borderRadius = 'var(--radius-sm)',
  className = '',
  style = {},
}) => {
  return (
    <div
      className={`animate-pulse ${className}`}
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: '#EAE6DF',
        ...style,
      }}
    />
  );
};

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 4 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
    {Array.from({ length: rows }).map((_, i) => (
      <div
        key={i}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1.25rem',
          padding: '1rem',
          backgroundColor: '#FAF8F5',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <Skeleton width="32px" height="32px" borderRadius="8px" />
        <Skeleton width="35%" height="16px" />
        <Skeleton width="15%" height="16px" />
        <Skeleton width="18%" height="16px" />
        <Skeleton width="12%" height="16px" />
      </div>
    ))}
  </div>
);
