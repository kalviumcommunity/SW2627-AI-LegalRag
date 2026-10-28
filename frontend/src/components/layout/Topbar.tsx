import React, { useState } from 'react';
import { Search, Bell, ChevronDown, LogIn, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface TopbarProps {
  onSearch?: (term: string) => void;
  searchTerm?: string;
}

export const Topbar: React.FC<TopbarProps> = ({ onSearch, searchTerm = '' }) => {
  const [query, setQuery] = useState(searchTerm);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const { user, isAuthenticated, logout, openAuthModal } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearch) onSearch(query);
  };

  const getInitials = (email: string) => {
    return email.charAt(0).toUpperCase();
  };

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1.5rem',
        marginBottom: '2rem',
        paddingBottom: '0.25rem',
      }}
    >
      {/* Search Input Pill */}
      <form
        onSubmit={handleSubmit}
        style={{
          flex: 1,
          maxWidth: '640px',
          position: 'relative',
        }}
      >
        <Search
          size={18}
          color="#9CA3AF"
          style={{
            position: 'absolute',
            left: '1.15rem',
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
          }}
        />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (onSearch) onSearch(e.target.value);
          }}
          placeholder="Search documents, ask a question, or type a keyword..."
          style={{
            width: '100%',
            padding: '0.75rem 1.25rem 0.75rem 2.75rem',
            borderRadius: 'var(--radius-full)',
            border: '1px solid #E5E7EB',
            backgroundColor: '#FFFFFF',
            fontSize: '0.925rem',
            color: 'var(--text-heading)',
            boxShadow: '0 2px 6px rgba(0, 0, 0, 0.02)',
          }}
        />
      </form>

      {/* Right controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', position: 'relative' }}>
        {/* Notification bell */}
        <button
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            border: '1px solid #E5E7EB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#4B5563',
            position: 'relative',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
            cursor: 'pointer',
          }}
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span
            style={{
              position: 'absolute',
              top: '9px',
              right: '10px',
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: '#EF4444',
            }}
          />
        </button>

        {/* User profile or Sign In button */}
        {isAuthenticated && user ? (
          <div style={{ position: 'relative' }}>
            <div
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.65rem',
                cursor: 'pointer',
                padding: '0.35rem 0.75rem 0.35rem 0.35rem',
                borderRadius: 'var(--radius-full)',
                backgroundColor: '#FFFFFF',
                border: '1px solid var(--border-light)',
                boxShadow: 'var(--shadow-sm)',
                transition: 'all 0.2s ease',
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--bg-lavender-active)',
                  color: 'var(--primary-purple-dark)',
                  fontWeight: 800,
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid var(--border-lavender)',
                }}
              >
                {getInitials(user.email)}
              </div>
              <span
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  color: 'var(--text-heading)',
                  maxWidth: '150px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.email.split('@')[0]}
              </span>
              <ChevronDown size={14} color="var(--text-subtle)" />
            </div>

            {isDropdownOpen && (
              <div
                className="editorial-card animate-fade-in"
                style={{
                  position: 'absolute',
                  top: '120%',
                  right: 0,
                  backgroundColor: '#FFFFFF',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-light)',
                  boxShadow: 'var(--shadow-pop)',
                  padding: '0.65rem',
                  minWidth: '240px',
                  zIndex: 200,
                }}
              >
                <div style={{ padding: '0.6rem 0.75rem', borderBottom: '1px solid var(--border-light)', marginBottom: '0.4rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem' }}>
                    <span className="badge badge-purple" style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}>
                      Property Analyst
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-heading)', wordBreak: 'break-all' }}>
                    {user.email}
                  </div>
                </div>
                <button
                  onClick={() => {
                    logout();
                    setIsDropdownOpen(false);
                  }}
                  style={{
                    width: '100%',
                    padding: '0.55rem 0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.55rem',
                    backgroundColor: 'transparent',
                    color: 'var(--accent-red-text)',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--accent-red-bg)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <LogOut size={15} />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => openAuthModal('login')}
            className="btn-purple"
            style={{
              padding: '0.6rem 1.25rem',
              fontSize: '0.875rem',
            }}
          >
            <LogIn size={15} />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
