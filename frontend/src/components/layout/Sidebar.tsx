import React from 'react';
import { Home, FileText, MessageSquareText, Settings, Sparkles } from 'lucide-react';
import { SidebarCharacterIllustration } from '../common/Illustrations';

export type NavPage = 'home' | 'documents' | 'ask' | 'settings' | 'doc-detail';

interface SidebarProps {
  currentPage: NavPage;
  onNavigate: (page: NavPage) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onNavigate }) => {
  const navItems = [
    { id: 'home' as NavPage, label: 'Home', icon: Home },
    { id: 'documents' as NavPage, label: 'Documents', icon: FileText },
    { id: 'ask' as NavPage, label: 'Ask Questions', icon: MessageSquareText },
    { id: 'settings' as NavPage, label: 'Settings', icon: Settings },
  ];

  return (
    <aside
      style={{
        width: '260px',
        minWidth: '260px',
        backgroundColor: '#F3F0FF',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '1.75rem 1.25rem 1.5rem 1.25rem',
        borderRight: '1px solid #E9D5FF',
        position: 'sticky',
        top: 0,
        height: '100vh',
        boxSizing: 'border-box',
        zIndex: 50,
      }}
    >
      {/* Brand & Nav */}
      <div>
        {/* Brand header */}
        <div
          onClick={() => onNavigate('home')}
          style={{
            cursor: 'pointer',
            marginBottom: '2rem',
            paddingLeft: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '12px',
                backgroundColor: '#7C3AED',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF',
                boxShadow: '0 4px 10px rgba(124, 58, 237, 0.3)',
              }}
            >
              <Sparkles size={20} />
            </div>
            <div>
              <span
                style={{
                  fontFamily: 'var(--font-heading)',
                  fontSize: '1.35rem',
                  fontWeight: 700,
                  color: '#1E1B4B',
                  letterSpacing: '-0.02em',
                }}
              >
                PropIntel
              </span>
            </div>
          </div>
          <p
            style={{
              fontSize: '0.785rem',
              color: '#6B7280',
              marginTop: '0.35rem',
              lineHeight: 1.3,
            }}
          >
            Your property files, decoded by AI.
          </p>
        </div>

        {/* Navigation list */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              currentPage === item.id ||
              (item.id === 'documents' && currentPage === 'doc-detail');

            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: isActive ? '#DDD6FE' : 'transparent',
                  color: isActive ? '#4C1D95' : '#4B5563',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.9375rem',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'rgba(221, 214, 254, 0.45)';
                    e.currentTarget.style.color = '#1E1B4B';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                    e.currentTarget.style.color = '#4B5563';
                  }
                }}
              >
                <Icon size={19} color={isActive ? '#6D28D9' : '#6B7280'} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Playful bottom card */}
      <div
        style={{
          backgroundColor: '#EDE9FE',
          borderRadius: 'var(--radius-card)',
          padding: '1.15rem 1rem 0.75rem 1rem',
          border: '1px solid #DDD6FE',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 2px 10px rgba(124, 58, 237, 0.05)',
        }}
      >
        <div style={{ position: 'relative', zIndex: 2 }}>
          <p
            className="handwritten"
            style={{
              fontSize: '1.25rem',
              lineHeight: 1.15,
              color: '#312E81',
              fontWeight: 700,
              marginBottom: '0.5rem',
            }}
          >
            Turn property documents into clear answers.
          </p>
        </div>
        <div style={{ marginTop: '0.25rem' }}>
          <SidebarCharacterIllustration />
        </div>
      </div>
    </aside>
  );
};
