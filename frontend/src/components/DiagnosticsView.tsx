import React, { useState } from 'react';
import { Server, Database, CheckCircle, XCircle, RefreshCw, Terminal } from 'lucide-react';
import type { SystemHealthData } from '../types';
import { apiFetch } from '../api/client';

interface DiagnosticsViewProps {
  health: SystemHealthData | null;
  loadingHealth: boolean;
  onRefreshHealth: () => void;
}

export const DiagnosticsView: React.FC<DiagnosticsViewProps> = ({
  health,
  loadingHealth,
  onRefreshHealth,
}) => {
  const [strictCheckResult, setStrictCheckResult] = useState<string | null>(null);
  const [checkingStrict, setCheckingStrict] = useState(false);

  const runStrictDbCheck = async () => {
    setCheckingStrict(true);
    setStrictCheckResult(null);
    try {
      const res = await apiFetch('/api/v1/health/db-check');
      const data = await res.json();
      if (res.ok) {
        setStrictCheckResult(`SUCCESS (HTTP 200): ${JSON.stringify(data, null, 2)}`);
      } else {
        setStrictCheckResult(`FAILED (HTTP ${res.status}): ${JSON.stringify(data, null, 2)}`);
      }
    } catch (err: any) {
      setStrictCheckResult(`ERROR: Unable to reach /api/v1/health/db-check - ${err.message}`);
    } finally {
      setCheckingStrict(false);
    }
  };

  const isDbConnected = health?.database?.connected ?? false;

  return (
    <div className="diagnostics-container">
      <div className="placeholder-header-card">
        <div className="placeholder-title-row">
          <div>
            <span className="phase-pill">System Diagnostic Center</span>
            <h2 className="placeholder-title">API & Database Infrastructure Verification</h2>
          </div>
          <button 
            className="refresh-btn" 
            onClick={onRefreshHealth}
            disabled={loadingHealth}
          >
            <RefreshCw size={14} className={loadingHealth ? 'spin' : ''} />
            <span>{loadingHealth ? 'Pinging...' : 'Refresh Telemetry'}</span>
          </button>
        </div>
        <p className="placeholder-desc">
          Live inspection of FastAPI services, PostgreSQL engine connectivity, and runtime settings.
        </p>
      </div>

      <div className="grid-2-col">
        {/* Core Connectivity Status */}
        <div className="card">
          <h3 className="card-title">
            <Server size={18} className="inline-icon text-primary" />
            Backend API Status
          </h3>
          <div className="diag-table">
            <div className="diag-row">
              <span className="diag-key">FastAPI Host:</span>
              <span className="diag-val"><code>http://127.0.0.1:8000</code></span>
            </div>
            <div className="diag-row">
              <span className="diag-key">API Version:</span>
              <span className="diag-val">{health?.version || '0.1.0'}</span>
            </div>
            <div className="diag-row">
              <span className="diag-key">Environment:</span>
              <span className="diag-val">{health?.environment || 'development'}</span>
            </div>
            <div className="diag-row">
              <span className="diag-key">Costing Baseline:</span>
              <span className="diag-val">{health?.costing_start_date || '2026-10-12'}</span>
            </div>
            <div className="diag-row">
              <span className="diag-key">Telemetry Timestamp:</span>
              <span className="diag-val">{health?.timestamp ? new Date(health.timestamp).toLocaleString() : 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Database Connectivity Gate */}
        <div className="card">
          <h3 className="card-title">
            <Database size={18} className="inline-icon text-primary" />
            PostgreSQL Connectivity Gate
          </h3>
          <div className="diag-table">
            <div className="diag-row">
              <span className="diag-key">Connection Status:</span>
              <span className="diag-val">
                {isDbConnected ? (
                  <span className="status-pill-ok inline-flex items-center gap-1">
                    <CheckCircle size={14} /> CONNECTED
                  </span>
                ) : (
                  <span className="status-pill-warn inline-flex items-center gap-1">
                    <XCircle size={14} /> OFFLINE / DISCONNECTED
                  </span>
                )}
              </span>
            </div>
            <div className="diag-row">
              <span className="diag-key">Target Database:</span>
              <span className="diag-val"><code>vspl_material_management</code> (Local)</span>
            </div>
            <div className="diag-row">
              <span className="diag-key">Driver:</span>
              <span className="diag-val">SQLAlchemy 2.x + psycopg 3</span>
            </div>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <button 
              className="action-btn"
              onClick={runStrictDbCheck}
              disabled={checkingStrict}
            >
              {checkingStrict ? 'Running Connectivity Gate...' : 'Execute Strict DB Connectivity Gate'}
            </button>
          </div>

          {strictCheckResult && (
            <div className="strict-result-box">
              <pre><code>{strictCheckResult}</code></pre>
            </div>
          )}
        </div>
      </div>

      {/* Raw Health JSON Telemetry */}
      <div className="card">
        <h3 className="card-title">
          <Terminal size={18} className="inline-icon text-primary" />
          Raw Telemetry Response Payload (/api/v1/health)
        </h3>
        <pre className="json-dump-box">
          <code>{health ? JSON.stringify(health, null, 2) : 'Awaiting backend connection...'}</code>
        </pre>
      </div>
    </div>
  );
};
