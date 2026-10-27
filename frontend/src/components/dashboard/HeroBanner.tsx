import React from 'react';
import { HeroHouseIllustration, DoodleArrow } from '../common/Illustrations';

export const HeroBanner: React.FC = () => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '2rem',
        gap: '2rem',
        position: 'relative',
      }}
    >
      {/* Left Text Block */}
      <div style={{ flex: '1 1 50%', maxWidth: '560px' }}>
        {/* Handwritten greeting */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
          <span
            style={{
              fontSize: '1.2rem',
              color: '#18181B',
              fontWeight: 700,
              transform: 'rotate(-2deg)',
              display: 'inline-block',
            }}
          >
            \ \
          </span>
          <span
            className="handwritten handwritten-indigo"
            style={{ fontSize: '1.65rem' }}
          >
            Welcome back!
          </span>
        </div>

        {/* Main Title */}
        <h1
          style={{
            fontSize: '2.85rem',
            lineHeight: 1.08,
            fontWeight: 800,
            color: '#18181B',
            marginBottom: '0.75rem',
            letterSpacing: '-0.03em',
          }}
        >
          Your property files,{' '}
          <span style={{ color: '#7C3AED', display: 'inline-block' }}>decoded.</span>
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontSize: '1.05rem',
            color: '#4B5563',
            lineHeight: 1.45,
            fontWeight: 400,
          }}
        >
          Upload documents, explore insights, and ask questions with AI.
        </p>
      </div>

      {/* Right Illustration Block */}
      <div
        style={{
          flex: '1 1 45%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          position: 'relative',
        }}
      >
        {/* Handwritten note above house */}
        <div
          style={{
            position: 'absolute',
            top: '-15px',
            right: '25px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            zIndex: 10,
          }}
        >
          <span
            className="handwritten"
            style={{
              color: '#4338CA',
              fontSize: '1.25rem',
              textAlign: 'center',
              lineHeight: 1.1,
              transform: 'rotate(4deg)',
            }}
          >
            Same documents.<br />Clearer answers.
          </span>
          <div style={{ transform: 'rotate(25deg) translateY(-2px)' }}>
            <DoodleArrow direction="down-right" color="#4338CA" />
          </div>
        </div>

        <div style={{ width: '100%', maxWidth: '480px' }}>
          <HeroHouseIllustration />
        </div>
      </div>
    </div>
  );
};
