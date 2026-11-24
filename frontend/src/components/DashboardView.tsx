import React from 'react';
import { 
  Building2, 
  Server, 
  ShieldCheck, 
  AlertTriangle, 
  RefreshCw, 
  FolderKanban, 
  CheckCircle, 
  Clock 
} from 'lucide-react';
import type { ModuleId, SystemHealthData, UserRole } from '../types';
import { IMPLEMENTATION_ROADMAP } from '../config/roadmap';
import { canAccessModule } from '../auth/permissions';

interface DashboardViewProps {
  health: SystemHealthData | null;
  loadingHealth: boolean;
  onRefreshHealth: () => void;
  currentRole?: UserRole | null;
  onNavigate: (module: ModuleId) => void;
}

const DEPARTMENTS = [
  'Foundry',
  'Machine Shop',
  'Maintenance',
  'General/Stores',
  'Packing',
  'Quality',
  'F3 HMC',
  'F3 CNC',
];

export const DashboardView: React.FC<DashboardViewProps> = ({
  health,
  loadingHealth,
  onRefreshHealth,
  currentRole,
  onNavigate,
}) => {
  const isDbConnected = health?.database?.connected ?? false;

  return (
    <div className="dashboard-container">
      {/* Welcome Banner */}
      <div className="welcome-banner">
        <div className="welcome-content">
          <span className="badge-pill">Phases 1–3 Operational • Phases 4–6 Implemented</span>
          <h2 className="welcome-title">VSPL Material Management & Costing System</h2>
          <p className="welcome-subtitle">
            Enterprise SG Iron Foundry ERP foundation engineered for Vijay Spheroidals Pvt. Ltd.
            Strict append-only stock movement tracking, heat-to-issue reconciliation, and weighted-average costing.
          </p>
        </div>
        <div className="system-stamp">
          <div className="stamp-label">Costing Baseline</div>
          <div className="stamp-value">12 Oct 2026</div>
        </div>
      </div>

      {/* Scope & System Telemetry Grid */}
      <div className="grid-2-col">
        {/* API & Database Live Telemetry */}
        <div className="card telemetry-card">
          <div className="card-header-row">
            <h3 className="card-title">
              <Server size={18} className="inline-icon text-primary" />
              Backend & Database Telemetry
            </h3>
            <button 
              className="refresh-btn" 
              onClick={onRefreshHealth}
              disabled={loadingHealth}
              title="Ping backend health endpoint"
            >
              <RefreshCw size={14} className={loadingHealth ? 'spin' : ''} />
              <span>{loadingHealth ? 'Pinging...' : 'Refresh Status'}</span>
            </button>
          </div>

          <div className="telemetry-body">
            <div className="telemetry-item">
              <span className="tel-label">FastAPI Backend Status:</span>
              <span className={`tel-status ${health ? 'status-pill-ok' : 'status-pill-wait'}`}>
                {health ? health.status.toUpperCase() : 'POLLING'}
              </span>
            </div>

            <div className="telemetry-item">
              <span className="tel-label">PostgreSQL Database:</span>
              <span className={`tel-status ${isDbConnected ? 'status-pill-ok' : 'status-pill-warn'}`}>
                {isDbConnected ? 'CONNECTED' : 'DISCONNECTED / OFFLINE'}
              </span>
            </div>

            <div className="telemetry-item">
              <span className="tel-label">Environment:</span>
              <code className="tel-code">{health?.environment || 'development'}</code>
            </div>

            <div className="telemetry-item">
              <span className="tel-label">Database Target Message:</span>
              <span className="tel-msg" title={health?.database?.message}>
                {health?.database?.message || 'Awaiting initial telemetry report...'}
              </span>
            </div>

            {!isDbConnected && (
              <div className="db-alert-box">
                <AlertTriangle size={16} className="text-amber flex-shrink-0" />
                <p className="db-alert-text">
                  PostgreSQL is not currently connected. To enable persistence, start the local PostgreSQL
                  service and execute <code>alembic upgrade head</code>. The application shell remains operational.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Plant Foundry Scope & Department Matrix */}
        <div className="card departments-card">
          <div className="card-header-row">
            <h3 className="card-title">
              <Building2 size={18} className="inline-icon text-primary" />
              Foundry Operations Scope
            </h3>
            <span className="scope-tag">8 Departments</span>
          </div>

          <p className="section-note">
            Configured for material requisition, stock transfers, and reconciliation across all active plant units:
          </p>

          <div className="dept-tags-grid">
            {DEPARTMENTS.map((dept) => (
              <div key={dept} className="dept-tag">
                <span className="dept-dot"></span>
                <span>{dept}</span>
              </div>
            ))}
          </div>

          <div className="stats-summary-row">
            <div className="summary-stat-box">
              <div className="stat-label">Item Master Scope</div>
              <div className="stat-value">~741 Items</div>
              <div className="stat-hint">Raw, Alloys, Consumables</div>
            </div>
            <div className="summary-stat-box">
              <div className="stat-label">Historical Records</div>
              <div className="stat-value">~12,280 Rows</div>
              <div className="stat-hint">Phase 7 Migration Target</div>
            </div>
          </div>
        </div>
      </div>

      {/* Strict Audit Policy Callout */}
      <div className="audit-policy-card">
        <div className="policy-icon-col">
          <ShieldCheck size={28} className="text-primary" />
        </div>
        <div className="policy-content">
          <h4 className="policy-title">Non-Negotiable Accounting & Costing Principles</h4>
          <p className="policy-text">
            VSPL ERP enforces strict data fidelity: <strong>No stock movements occur without an authorized Issue transaction</strong>. 
            Heat Log charges do not independently deplete inventory. Transaction history is immutable—no clearing of history to rectify errors.
            Synthetic KPI numbers or fabricated historical pricing are strictly prohibited.
          </p>
        </div>
      </div>

      {/* Implementation Roadmap Overview */}
      <div className="card roadmap-overview-card">
        <div className="card-header-row">
          <h3 className="card-title">
            <FolderKanban size={18} className="inline-icon text-primary" />
            System Implementation Roadmap
          </h3>
          <span className="scope-tag">6-Phase Architectural Plan</span>
        </div>

        <div className="phases-grid">
          {IMPLEMENTATION_ROADMAP.map((phase) => {
            const targetModule = phase.moduleId as ModuleId | undefined;
            const canNav = Boolean(targetModule && canAccessModule(currentRole, targetModule));
            return (
              <div
                key={phase.id}
                className={`phase-card ${phase.cardClass}`}
                onClick={() => canNav && targetModule && onNavigate(targetModule)}
                style={{ cursor: canNav ? 'pointer' : 'default' }}
              >
              <div className="phase-top">
                <span className="phase-number">{phase.number}</span>
                {phase.icon === 'check' ? (
                  <CheckCircle size={16} className="text-success" />
                ) : (
                  <Clock size={16} className={phase.cardClass === 'completed' ? 'text-success' : 'text-amber'} />
                )}
              </div>
              <div className="phase-title">{phase.title}</div>
              <div className="phase-desc">{phase.description}</div>

              <div className="phase-status-stack">
                <div className="phase-status-row">
                  <span className="phase-gate-label">Build:</span>
                  <span className={`phase-status ${phase.implementationBadgeClass}`}>
                    {phase.implementationLabel}
                  </span>
                </div>
                <div className="phase-status-row">
                  <span className="phase-gate-label">Gate:</span>
                  <span className={`phase-status ${phase.approvalBadgeClass}`}>
                    {phase.approvalLabel}
                  </span>
                </div>
              </div>
            </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
