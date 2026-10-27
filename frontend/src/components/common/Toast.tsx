import React, { createContext, useContext, useState, useCallback } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
  showError: (message: string) => void;
  showSuccess: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = 'info') => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => {
        removeToast(id);
      }, 5000);
    },
    [removeToast]
  );

  const showError = useCallback(
    (message: string) => {
      showToast(message, 'error');
    },
    [showToast]
  );

  const showSuccess = useCallback(
    (message: string) => {
      showToast(message, 'success');
    },
    [showToast]
  );

  return (
    <ToastContext.Provider value={{ showToast, showError, showSuccess }}>
      {children}
      {/* Toast container */}
      <div
        style={{
          position: 'fixed',
          bottom: '1.5rem',
          right: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          zIndex: 9999,
          maxWidth: '420px',
        }}
      >
        {toasts.map((toast) => {
          let bg = '#FFFFFF';
          let border = '#E5E7EB';
          let icon = <Info size={18} color="#4F46E5" />;

          if (toast.type === 'error') {
            bg = '#FFF1F2';
            border = '#FECDD3';
            icon = <AlertCircle size={18} color="#E11D48" />;
          } else if (toast.type === 'success') {
            bg = '#F0FDF4';
            border = '#BBF7D0';
            icon = <CheckCircle2 size={18} color="#16A34A" />;
          }

          return (
            <div
              key={toast.id}
              className="editorial-card animate-fade-in"
              style={{
                backgroundColor: bg,
                border: `1px solid ${border}`,
                borderRadius: 'var(--radius-md)',
                padding: '0.85rem 1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                boxShadow: 'var(--shadow-hover)',
              }}
            >
              <div style={{ flexShrink: 0 }}>{icon}</div>
              <div style={{ flex: 1, fontSize: '0.875rem', color: 'var(--text-heading)', fontWeight: 500 }}>
                {toast.message}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                style={{
                  color: 'var(--text-muted)',
                  padding: '0.2rem',
                  display: 'flex',
                  alignItems: 'center',
                }}
                aria-label="Dismiss toast"
              >
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};
