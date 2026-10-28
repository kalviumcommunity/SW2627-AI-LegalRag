import React, { useState, useEffect } from 'react';
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  X,
  AlertCircle,
  ArrowRight,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { ApiError } from '../../api/client';

export const AuthModal: React.FC = () => {
  const {
    isAuthModalOpen,
    closeAuthModal,
    authModalMode,
    setAuthModalMode,
    login,
    register,
  } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Keyboard navigation: Escape key closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isAuthModalOpen) {
        closeAuthModal();
      }
    };
    if (isAuthModalOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isAuthModalOpen, closeAuthModal]);

  if (!isAuthModalOpen) return null;

  const isLogin = authModalMode === 'login';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError('Please enter your email address.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (!isLogin && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      if (isLogin) {
        await login({ email: trimmedEmail, password });
      } else {
        await register({ email: trimmedEmail, password });
      }
      setEmail('');
      setPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError('Too many attempts. Please wait a moment and try again.');
        } else {
          setError(err.message || 'Authentication failed. Please verify your credentials.');
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSwitchMode = (mode: 'login' | 'register') => {
    setAuthModalMode(mode);
    setError(null);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(24, 24, 27, 0.45)',
        backdropFilter: 'blur(5px)',
        padding: '1.25rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeAuthModal();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="editorial-card animate-fade-in"
        style={{
          width: '100%',
          maxWidth: '460px',
          backgroundColor: '#FFFFFF',
          borderRadius: 'var(--radius-card)',
          boxShadow: 'var(--shadow-pop)',
          border: '1px solid var(--border-light)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Soft Funky Editorial Header Banner */}
        <div
          style={{
            padding: '1.75rem 1.75rem 1.25rem 1.75rem',
            backgroundColor: 'var(--bg-canvas)',
            borderBottom: '1px solid var(--border-light)',
            position: 'relative',
          }}
        >
          {/* Close button pill */}
          <button
            onClick={closeAuthModal}
            style={{
              position: 'absolute',
              top: '1.25rem',
              right: '1.25rem',
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: '#FFFFFF',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              boxShadow: 'var(--shadow-sm)',
            }}
            title="Close"
            aria-label="Close authentication modal"
          >
            <X size={16} />
          </button>

          {/* Badge & Handwritten Tagline */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.65rem' }}>
            <span className="badge badge-purple" style={{ padding: '0.3rem 0.75rem' }}>
              <ShieldCheck size={14} color="#7C3AED" />
              <span>PropIntel Secure</span>
            </span>
            <span
              className="handwritten handwritten-purple"
              style={{ fontSize: '1.35rem', transform: 'rotate(-2deg)' }}
            >
              {isLogin ? 'welcome back ~' : 'instant access ~'}
            </span>
          </div>

          {/* Modal Title */}
          <h2
            style={{
              fontSize: '1.65rem',
              fontWeight: 800,
              color: 'var(--text-heading)',
              letterSpacing: '-0.025em',
              lineHeight: 1.15,
              marginBottom: '0.35rem',
            }}
          >
            {isLogin ? (
              <>
                Sign in to <span style={{ color: 'var(--primary-purple)' }}>PropIntel</span>
              </>
            ) : (
              <>
                Create your <span style={{ color: 'var(--primary-purple)' }}>workspace</span>
              </>
            )}
          </h2>

          <p
            style={{
              fontSize: '0.9rem',
              color: 'var(--text-body)',
              lineHeight: 1.4,
            }}
          >
            {isLogin
              ? 'Access your private agreements, title records, and grounded AI insights.'
              : 'Secure, isolated property intelligence with document-level authorization.'}
          </p>
        </div>

        {/* Pill-shaped Segmented Tab Switcher */}
        <div style={{ padding: '1.25rem 1.75rem 0 1.75rem' }}>
          <div
            style={{
              display: 'flex',
              backgroundColor: 'var(--bg-lavender)',
              padding: '4px',
              borderRadius: 'var(--radius-full)',
              border: '1px solid var(--border-lavender)',
            }}
          >
            <button
              type="button"
              onClick={() => handleSwitchMode('login')}
              style={{
                flex: 1,
                padding: '0.55rem 0',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.875rem',
                fontWeight: isLogin ? 700 : 500,
                color: isLogin ? 'var(--primary-purple-dark)' : 'var(--text-muted)',
                backgroundColor: isLogin ? '#FFFFFF' : 'transparent',
                boxShadow: isLogin ? '0 2px 6px rgba(124, 58, 237, 0.12)' : 'none',
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('register')}
              style={{
                flex: 1,
                padding: '0.55rem 0',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.875rem',
                fontWeight: !isLogin ? 700 : 500,
                color: !isLogin ? 'var(--primary-purple-dark)' : 'var(--text-muted)',
                backgroundColor: !isLogin ? '#FFFFFF' : 'transparent',
                boxShadow: !isLogin ? '0 2px 6px rgba(124, 58, 237, 0.12)' : 'none',
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              Create Account
            </button>
          </div>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem 1.75rem 1.75rem 1.75rem' }}>
          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.65rem',
                backgroundColor: 'var(--accent-red-bg)',
                border: '1px solid var(--accent-red-border)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 0.95rem',
                marginBottom: '1.25rem',
                color: 'var(--accent-red-text)',
                fontSize: '0.85rem',
                lineHeight: 1.4,
              }}
            >
              <AlertCircle size={17} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>{error}</span>
            </div>
          )}

          {/* Email input field */}
          <div style={{ marginBottom: '1.15rem' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--text-heading)',
                marginBottom: '0.4rem',
              }}
            >
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <Mail
                size={16}
                color="#7C3AED"
                style={{
                  position: 'absolute',
                  left: '1rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  pointerEvents: 'none',
                }}
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@propertyintel.com"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem 0.75rem 2.65rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: '#FFFFFF',
                  fontSize: '0.925rem',
                  color: 'var(--text-heading)',
                }}
              />
            </div>
          </div>

          {/* Password input field */}
          <div style={{ marginBottom: isLogin ? '1.5rem' : '1.15rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <label
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'var(--text-heading)',
                }}
              >
                Password
              </label>
              {!isLogin && (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Min. 8 characters
                </span>
              )}
            </div>
            <div style={{ position: 'relative' }}>
              <Lock
                size={16}
                color="#7C3AED"
                style={{
                  position: 'absolute',
                  left: '1rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  pointerEvents: 'none',
                }}
              />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isLogin ? 'Enter your password' : 'Create a strong password'}
                required
                style={{
                  width: '100%',
                  padding: '0.75rem 2.65rem 0.75rem 2.65rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: '#FFFFFF',
                  fontSize: '0.925rem',
                  color: 'var(--text-heading)',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '0.85rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  padding: '0.25rem',
                  color: 'var(--text-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Confirm Password (Register only) */}
          {!isLogin && (
            <div style={{ marginBottom: '1.5rem' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'var(--text-heading)',
                  marginBottom: '0.4rem',
                }}
              >
                Confirm Password
              </label>
              <div style={{ position: 'relative' }}>
                <Lock
                  size={16}
                  color="#7C3AED"
                  style={{
                    position: 'absolute',
                    left: '1rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  required
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem 0.75rem 2.65rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: '#FFFFFF',
                    fontSize: '0.925rem',
                    color: 'var(--text-heading)',
                  }}
                />
              </div>
            </div>
          )}

          {/* Action Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-purple"
            style={{
              width: '100%',
              padding: '0.8rem',
              justifyContent: 'center',
              fontSize: '0.95rem',
              fontWeight: 700,
            }}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>Verifying credentials...</span>
              </>
            ) : isLogin ? (
              <>
                <span>Sign In to PropIntel</span>
                <ArrowRight size={17} />
              </>
            ) : (
              <>
                <span>Create Free Workspace</span>
                <Sparkles size={17} />
              </>
            )}
          </button>

          {/* Footer switcher note */}
          <div
            style={{
              marginTop: '1.25rem',
              textAlign: 'center',
              fontSize: '0.85rem',
              color: 'var(--text-muted)',
            }}
          >
            {isLogin ? (
              <span>
                Don't have an account yet?{' '}
                <button
                  type="button"
                  onClick={() => handleSwitchMode('register')}
                  style={{
                    color: 'var(--primary-purple)',
                    fontWeight: 600,
                    textDecoration: 'underline',
                  }}
                >
                  Create one now
                </button>
              </span>
            ) : (
              <span>
                Already registered?{' '}
                <button
                  type="button"
                  onClick={() => handleSwitchMode('login')}
                  style={{
                    color: 'var(--primary-purple)',
                    fontWeight: 600,
                    textDecoration: 'underline',
                  }}
                >
                  Sign in
                </button>
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};
