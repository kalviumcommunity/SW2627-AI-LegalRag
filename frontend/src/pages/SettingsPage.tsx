import React, { useEffect, useState } from 'react';
import { Settings, Server, ShieldCheck, CheckCircle2, AlertCircle, RefreshCw, Cpu } from 'lucide-react';
import { Card } from '../components/common/Card';
import { getApiBaseUrl, apiClient } from '../api/client';
import { useToast } from '../components/common/Toast';

interface HealthCheckResponse {
  status: string;
  app_name?: string;
  app_env?: string;
}

export const SettingsPage: React.FC = () => {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [isChecking, setIsChecking] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const baseUrl = getApiBaseUrl();
  const { showSuccess } = useToast();

  const checkHealth = async () => {
    setIsChecking(true);
    setError(null);
    try {
      const data = await apiClient<HealthCheckResponse>('/health');
      setHealth(data);
      showSuccess('Backend connection verified');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Backend unreachable';
      setError(msg);
      setHealth(null);
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Title */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Settings size={28} color="#7C3AED" />
          <h1 style={{ fontSize: '2.1rem', fontWeight: 800, color: '#18181B' }}>
            System Settings & Status
          </h1>
        </div>
        <p style={{ fontSize: '0.95rem', color: '#6B7280', marginTop: '0.2rem' }}>
          Backend connectivity, API base endpoint configuration, and security architecture.
        </p>
      </div>

      {/* Backend API Configuration & Health Card */}
      <Card padding="lg">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1.25rem',
            paddingBottom: '1rem',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Server size={22} color="#6D28D9" />
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#18181B' }}>
                FastAPI Backend Service
              </h2>
              <span style={{ fontSize: '0.8125rem', color: '#6B7280' }}>
                Configured via <code>VITE_API_BASE_URL</code>
              </span>
            </div>
          </div>

          <button
            onClick={checkHealth}
            disabled={isChecking}
            className="btn-outline"
            style={{ fontSize: '0.8125rem' }}
          >
            <RefreshCw size={14} className={isChecking ? 'animate-spin' : ''} />
            <span>{isChecking ? 'Checking...' : 'Check Connection'}</span>
          </button>
        </div>

        {/* Current Endpoint */}
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#374151', display: 'block', marginBottom: '0.4rem' }}>
            Target API Base URL:
          </label>
          <div
            style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '10px',
              backgroundColor: '#FAF8F5',
              border: '1px solid #E5E7EB',
              fontFamily: 'monospace',
              fontSize: '0.9rem',
              color: '#18181B',
            }}
          >
            {baseUrl}
          </div>
        </div>

        {/* Health status badge & details */}
        {health ? (
          <div
            style={{
              backgroundColor: '#DCFCE7',
              border: '1px solid #86EFAC',
              borderRadius: '12px',
              padding: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.85rem',
            }}
          >
            <CheckCircle2 size={24} color="#15803D" />
            <div>
              <div style={{ fontWeight: 700, color: '#166534', fontSize: '0.95rem' }}>
                Backend Connected & Healthy
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#15803D', marginTop: '0.15rem' }}>
                Status: {health.status} {health.app_name ? `• App: ${health.app_name}` : ''}
              </div>
            </div>
          </div>
        ) : error ? (
          <div
            style={{
              backgroundColor: '#FEE2E2',
              border: '1px solid #FCA5A5',
              borderRadius: '12px',
              padding: '1rem',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.85rem',
            }}
          >
            <AlertCircle size={22} color="#DC2626" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.95rem' }}>
                Backend Not Responding at {baseUrl}
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#B91C1C', marginTop: '0.2rem' }}>
                Ensure your FastAPI backend is running via <code>uvicorn app.main:app --port 8000</code>.
              </div>
            </div>
          </div>
        ) : null}
      </Card>

      {/* Architecture & Security Specs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1.25rem' }}>
        <Card padding="md">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Cpu size={18} color="#7C3AED" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#18181B' }}>
              Intelligence Architecture
            </h3>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', color: '#4B5563' }}>
            <li><strong>Embeddings:</strong> FastEmbed nomic-ai/nomic-embed-text-v1.5-Q (768d)</li>
            <li><strong>Vector Store:</strong> PostgreSQL with pgvector cosine distance index</li>
            <li><strong>Search Modes:</strong> Semantic vector cosine & Hybrid RRF fusion</li>
            <li><strong>Grounded LLM:</strong> Groq API server-side generation</li>
          </ul>
        </Card>

        <Card padding="md">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ShieldCheck size={18} color="#059669" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#18181B' }}>
              Security & Privacy Guarantee
            </h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#4B5563', lineHeight: 1.5 }}>
            API keys (e.g. Groq, database credentials) remain safely quarantined on the FastAPI server and are never delivered or exposed to browser client code. All client communications pass through authenticated or internal endpoints.
          </p>
        </Card>
      </div>
    </div>
  );
};
