import React from 'react';
import { EvidenceIllustration } from '../common/Illustrations';

export const EvidenceCard: React.FC = () => {
  return (
    <div
      style={{
        backgroundColor: '#E6F7ED',
        borderRadius: 'var(--radius-card)',
        padding: '1.5rem 1.75rem',
        border: '1px solid #A7F3D0',
        display: 'flex',
        alignItems: 'center',
        gap: '1.5rem',
        boxShadow: '0 4px 18px -2px rgba(16, 185, 129, 0.08)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Left Illustration */}
      <div style={{ flexShrink: 0, width: '90px' }}>
        <EvidenceIllustration />
      </div>

      {/* Right Content */}
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.35rem' }}>
          <h3
            style={{
              fontSize: '1.35rem',
              fontWeight: 800,
              color: '#064E3B',
              letterSpacing: '-0.02em',
            }}
          >
            Evidence first.
          </h3>
          <span style={{ color: '#F59E0B', fontSize: '1.2rem', fontWeight: 700 }}>
            //
          </span>
        </div>

        <p
          style={{
            fontSize: '0.875rem',
            color: '#065F46',
            lineHeight: 1.45,
            maxWidth: '340px',
            fontWeight: 500,
          }}
        >
          Every answer includes citations to your original documents so you can verify the source.
        </p>
      </div>
    </div>
  );
};
