import React from 'react';

/**
 * Whimsical House Illustration for the Hero Banner matching the screenshot.
 */
export const HeroHouseIllustration: React.FC<{ className?: string }> = ({ className = '' }) => (
  <svg
    viewBox="0 0 540 260"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    style={{ overflow: 'visible', width: '100%', height: 'auto', maxHeight: '230px' }}
    aria-label="Whimsical illustrated modern house with garden"
  >
    <defs>
      <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#C7D2FE" stopOpacity="0.45" />
        <stop offset="100%" stopColor="#DDD6FE" stopOpacity="0" />
      </linearGradient>
      <radialGradient id="sunGrad" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="#FDE047" />
        <stop offset="100%" stopColor="#FBBF24" />
      </radialGradient>
      <filter id="softShadow" x="-10%" y="-10%" width="120%" height="120%">
        <feDropShadow dx="2" dy="4" stdDeviation="3" floodOpacity="0.08" />
      </filter>
    </defs>

    {/* Soft sky / cloud backdrop */}
    <path
      d="M20 180 C 40 100, 120 70, 180 120 C 240 50, 360 40, 410 110 C 480 80, 520 130, 530 190 Z"
      fill="url(#skyGrad)"
    />

    {/* Sun in background */}
    <circle cx="440" cy="115" r="42" fill="url(#sunGrad)" opacity="0.85" />
    <circle cx="440" cy="115" r="50" stroke="#FDE047" strokeWidth="2" strokeDasharray="6 6" opacity="0.6" />

    {/* Soft green trees & rolling shrubs */}
    <circle cx="160" cy="170" r="48" fill="#86EFAC" opacity="0.9" />
    <circle cx="130" cy="185" r="38" fill="#6EE7B7" opacity="0.8" />
    <circle cx="490" cy="185" r="40" fill="#86EFAC" opacity="0.9" />
    <circle cx="510" cy="195" r="30" fill="#6EE7B7" />

    {/* Main House Base (Lavender/White) */}
    {/* Left wing - pitched roof white/lavender structure */}
    <path
      d="M195 210 L195 105 L260 70 L325 105 L325 210 Z"
      fill="#FFFFFF"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinejoin="round"
    />
    {/* Roof pitch line */}
    <path d="M190 108 L260 66 L330 108" stroke="#18181B" strokeWidth="4" strokeLinecap="round" />

    {/* Large second floor modern window */}
    <rect x="235" y="95" width="50" height="70" rx="4" fill="#C7D2FE" stroke="#18181B" strokeWidth="3" />
    <line x1="260" y1="95" x2="260" y2="165" stroke="#18181B" strokeWidth="2.5" />
    <line x1="235" y1="130" x2="285" y2="130" stroke="#18181B" strokeWidth="2.5" />

    {/* Center wing - Butter yellow section */}
    <rect
      x="325"
      y="110"
      width="90"
      height="100"
      fill="#FEF08A"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinejoin="round"
    />
    {/* Center top flat roof parapet */}
    <line x1="320" y1="110" x2="420" y2="110" stroke="#18181B" strokeWidth="4" strokeLinecap="round" />
    {/* Center windows */}
    <rect x="345" y="125" width="22" height="40" rx="3" fill="#C7D2FE" stroke="#18181B" strokeWidth="2.5" />
    <rect x="375" y="125" width="22" height="40" rx="3" fill="#C7D2FE" stroke="#18181B" strokeWidth="2.5" />

    {/* Right wing - Soft Lavender section */}
    <path
      d="M415 210 L415 130 L475 145 L475 210 Z"
      fill="#DDD6FE"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinejoin="round"
    />
    <rect x="430" y="150" width="28" height="35" rx="3" fill="#BFDBFE" stroke="#18181B" strokeWidth="2.5" />

    {/* Ground bushes & flora with ink line details */}
    <path
      d="M100 215 C 130 195, 170 195, 205 215"
      fill="#4ADE80"
      stroke="#18181B"
      strokeWidth="3.5"
    />
    <circle cx="150" cy="205" r="5" fill="#F43F5E" />
    <circle cx="165" cy="200" r="4" fill="#FBBF24" />

    {/* Front garden hedge */}
    <path
      d="M280 215 C 300 200, 340 200, 360 215"
      fill="#34D399"
      stroke="#18181B"
      strokeWidth="3"
    />

    {/* Right garden flowers */}
    <path
      d="M450 215 C 475 195, 510 195, 530 215"
      fill="#4ADE80"
      stroke="#18181B"
      strokeWidth="3.5"
    />

    {/* Ground baseline */}
    <line x1="90" y1="215" x2="535" y2="215" stroke="#18181B" strokeWidth="4" strokeLinecap="round" />

    {/* Playful ink hatchings */}
    <line x1="170" y1="130" x2="175" y2="120" stroke="#18181B" strokeWidth="2" strokeLinecap="round" />
    <line x1="178" y1="135" x2="183" y2="125" stroke="#18181B" strokeWidth="2" strokeLinecap="round" />
    <line x1="480" y1="100" x2="485" y2="90" stroke="#18181B" strokeWidth="2" strokeLinecap="round" />
    <line x1="490" y1="105" x2="495" y2="95" stroke="#18181B" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/**
 * Sidebar Character: Woman reading/decoding with playful sparkles.
 */
export const SidebarCharacterIllustration: React.FC<{ className?: string }> = ({ className = '' }) => (
  <svg
    viewBox="0 0 160 170"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    style={{ width: '100%', height: 'auto' }}
    aria-label="Character analyzing documents"
  >
    {/* Sparkle stars */}
    <path d="M130 20 L132 28 L140 30 L132 32 L130 40 L128 32 L120 30 L128 28 Z" fill="#FDE047" />
    <path d="M25 65 L26 71 L32 72 L26 73 L25 79 L24 73 L18 72 L24 71 Z" fill="#FDE047" />

    {/* Character body: Legs (purple pants) */}
    <path
      d="M75 145 C 75 145, 95 155, 125 150 C 135 148, 145 135, 140 120 C 135 105, 120 108, 105 118"
      fill="#C4B5FD"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M50 148 C 50 148, 65 158, 85 158 C 105 158, 115 140, 110 125"
      fill="#A78BFA"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />

    {/* Torso (butter yellow sweater) */}
    <path
      d="M38 120 C 35 100, 45 80, 68 75 C 80 73, 95 80, 95 100 C 95 115, 80 135, 60 135 C 45 135, 40 130, 38 120 Z"
      fill="#FDE047"
      stroke="#18181B"
      strokeWidth="3.5"
      strokeLinejoin="round"
    />

    {/* Arms holding tablet / file */}
    <path
      d="M68 85 C 75 95, 90 95, 100 88"
      stroke="#18181B"
      strokeWidth="3"
      strokeLinecap="round"
    />
    {/* Tablet/Device */}
    <rect
      x="95"
      y="75"
      width="22"
      height="30"
      rx="3"
      transform="rotate(12 95 75)"
      fill="#FFFFFF"
      stroke="#18181B"
      strokeWidth="3"
    />
    <circle cx="106" cy="98" r="1.5" fill="#18181B" />

    {/* Head & Face */}
    <circle cx="55" cy="50" r="16" fill="#FDE047" stroke="#18181B" strokeWidth="3.5" />
    {/* Dark Hair bun */}
    <path
      d="M38 52 C 38 35, 52 32, 68 38 C 72 32, 65 24, 52 24 C 40 24, 32 32, 34 46 Z"
      fill="#18181B"
    />
    <circle cx="32" cy="42" r="8" fill="#18181B" />

    {/* Cute stylized eye & smile */}
    <circle cx="62" cy="50" r="2" fill="#18181B" />
    <path d="M60 55 C 62 58, 66 58, 68 56" stroke="#18181B" strokeWidth="2" strokeLinecap="round" />

    {/* Ink doodle accents around character */}
    <line x1="125" y1="70" x2="135" y2="65" stroke="#F59E0B" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="128" y1="80" x2="138" y2="80" stroke="#F59E0B" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

/**
 * Evidence First Card Illustration (document + magnifying glass + sparkles).
 */
export const EvidenceIllustration: React.FC<{ className?: string }> = ({ className = '' }) => (
  <svg
    viewBox="0 0 140 130"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    style={{ width: '100%', height: 'auto', maxWidth: '120px' }}
    aria-label="Verified evidence document and magnifying glass"
  >
    {/* Yellow document card */}
    <rect
      x="18"
      y="15"
      width="68"
      height="85"
      rx="8"
      fill="#FEF08A"
      stroke="#18181B"
      strokeWidth="3.5"
    />
    {/* Document lines */}
    <line x1="28" y1="32" x2="68" y2="32" stroke="#18181B" strokeWidth="3" strokeLinecap="round" />
    <line x1="28" y1="44" x2="72" y2="44" stroke="#18181B" strokeWidth="3" strokeLinecap="round" />
    <line x1="28" y1="56" x2="60" y2="56" stroke="#18181B" strokeWidth="3" strokeLinecap="round" />
    <line x1="28" y1="68" x2="70" y2="68" stroke="#18181B" strokeWidth="3" strokeLinecap="round" />
    <line x1="28" y1="80" x2="52" y2="80" stroke="#18181B" strokeWidth="3" strokeLinecap="round" />

    {/* Magnifying Glass */}
    <g transform="translate(42, 38)">
      {/* Glass rim and lens */}
      <circle cx="45" cy="40" r="24" fill="#BAE6FD" fillOpacity="0.75" stroke="#18181B" strokeWidth="4" />
      <circle cx="40" cy="35" r="18" stroke="#FFFFFF" strokeWidth="2" strokeDasharray="14 12" opacity="0.8" />
      {/* Handle */}
      <path
        d="M62 57 L85 80"
        stroke="#18181B"
        strokeWidth="6"
        strokeLinecap="round"
      />
    </g>

    {/* Sparkles */}
    <path d="M102 18 L103 23 L108 24 L103 25 L102 30 L101 25 L96 24 L101 23 Z" fill="#F59E0B" />
    <line x1="115" y1="22" x2="124" y2="18" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" />
    <line x1="118" y1="30" x2="126" y2="32" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/**
 * Editorial Handwritten Doodle Arrow.
 */
export const DoodleArrow: React.FC<{
  direction?: 'down-left' | 'down-right' | 'up-right';
  className?: string;
  color?: string;
}> = ({ direction = 'down-left', className = '', color = '#6366F1' }) => {
  if (direction === 'down-right') {
    return (
      <svg
        viewBox="0 0 60 45"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        style={{ width: '45px', height: '35px', display: 'inline-block' }}
      >
        <path
          d="M8 8 C 25 10, 48 18, 48 35"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M40 33 L49 37 L52 28"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 60 45"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ width: '45px', height: '35px', display: 'inline-block' }}
    >
      <path
        d="M50 8 C 35 12, 12 20, 15 35"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M10 26 L13 37 L24 35"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};
