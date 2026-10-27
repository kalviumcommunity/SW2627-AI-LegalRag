import React, { useState } from 'react';
import { Search, Bell, ChevronDown } from 'lucide-react';

interface TopbarProps {
  onSearch?: (term: string) => void;
  searchTerm?: string;
}

export const Topbar: React.FC<TopbarProps> = ({ onSearch, searchTerm = '' }) => {
  const [query, setQuery] = useState(searchTerm);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearch) onSearch(query);
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
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

        {/* User profile dropdown */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            cursor: 'pointer',
            padding: '0.35rem 0.65rem 0.35rem 0.35rem',
            borderRadius: 'var(--radius-full)',
            backgroundColor: '#FFFFFF',
            border: '1px solid #E5E7EB',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: '#EDE9FE',
              color: '#6D28D9',
              fontWeight: 700,
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            P
          </div>
          <span
            style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#1F2937',
            }}
          >
            Property Analyst
          </span>
          <ChevronDown size={15} color="#9CA3AF" />
        </div>
      </div>
    </header>
  );
};
