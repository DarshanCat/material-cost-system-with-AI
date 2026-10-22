import { Activity, Calendar, User } from 'lucide-react';
import type { UserRole, SystemHealthData } from '../types';

interface HeaderProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  /** True only when the backend offers development sign-in; otherwise no role can be chosen client-side. */
  roleSelectorEnabled: boolean;
  signedInAs?: string;
  health: SystemHealthData | null;
  loadingHealth: boolean;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentRole,
  onRoleChange,
  roleSelectorEnabled,
  signedInAs,
  health,
  loadingHealth,
  onRefreshHealth,
}) => {
  const isDbConnected = health?.database?.connected ?? false;

  return (
    <header className="erp-header">
      <div className="header-brand">
        <div className="brand-logo">VSPL</div>
        <div className="brand-titles">
          <h1 className="brand-title">Vijay Spheroidals Pvt. Ltd.</h1>
          <span className="brand-subtitle">SG Iron Foundry — Material Management & Costing System</span>
        </div>
      </div>

      <div className="header-meta">
        <div className="meta-badge costing-date-badge" title="Costing baseline start date per business rules">
          <Calendar size={14} className="badge-icon" />
          <span>Costing Start: <strong>12 Oct 2026</strong></span>
        </div>

        <div 
          className={`meta-badge health-badge ${isDbConnected ? 'status-ok' : 'status-warning'}`}
          onClick={onRefreshHealth}
          title={`Click to refresh health check. DB: ${health?.database?.status || 'Unknown'}`}
        >
          <Activity size={14} className={`badge-icon ${loadingHealth ? 'spin' : ''}`} />
          <span>
            API: {health ? health.status.toUpperCase() : 'CHECKING...'}
            {health && (
              <span className="db-subtext"> (DB: {isDbConnected ? 'ONLINE' : 'OFFLINE'})</span>
            )}
          </span>
        </div>

        <div className="role-selector-container" title="Identity is verified by the server; the role below only requests a development sign-in">
          <User size={14} className="badge-icon text-muted" />
          <span className="role-label">{roleSelectorEnabled ? 'Dev sign-in as:' : 'Not signed in'}</span>
          {roleSelectorEnabled && (
          <select 
            value={currentRole} 
            onChange={(e) => onRoleChange(e.target.value as UserRole)}
            className="role-dropdown"
          >
            <option value="Stores">Stores</option>
            <option value="Foundry">Foundry</option>
            <option value="Purchase">Purchase</option>
            <option value="Management">Management</option>
            <option value="Admin">Admin</option>
          </select>
          )}
          {signedInAs && <span className="role-label" title="Verified by the server"> ({signedInAs})</span>}
        </div>
      </div>
    </header>
  );
};
