import React from 'react';
import { Activity, Calendar, User, ShieldCheck, Key } from 'lucide-react';
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
  onOpenSignInModal?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentRole,
  onRoleChange: _onRoleChange,
  roleSelectorEnabled: _roleSelectorEnabled,
  signedInAs,
  health,
  loadingHealth,
  onRefreshHealth,
  onOpenSignInModal,
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

        {/* Authentication & User Session Pill */}
        <div 
          className="role-selector-container cursor-pointer"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 10px', borderRadius: '6px', cursor: 'pointer', background: 'rgba(255,255,255,0.08)' }}
          title="Click to manage authentication or switch roles"
          onClick={onOpenSignInModal}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            {currentRole === 'Admin' ? (
              <ShieldCheck size={15} style={{ color: '#38bdf8' }} />
            ) : (
              <User size={15} style={{ color: '#94a3b8' }} />
            )}
            <span style={{ fontSize: '12px', color: '#cbd5e1' }}>
              {signedInAs || `usr_${currentRole.toLowerCase()}_01`}
            </span>
          </div>

          <span 
            className="pill p-steel" 
            style={{ fontSize: '11px', padding: '2px 8px', fontWeight: 600 }}
          >
            {currentRole}
          </span>

          <button
            type="button"
            className="erp-btn btn-sm btn-secondary"
            style={{ 
              padding: '2px 8px', 
              fontSize: '11px', 
              height: 'auto', 
              border: '1px solid rgba(255,255,255,0.2)',
              background: 'transparent',
              color: '#f1f5f9'
            }}
            onClick={(e) => {
              e.stopPropagation();
              if (onOpenSignInModal) onOpenSignInModal();
            }}
          >
            <Key size={11} style={{ marginRight: '3px' }} /> Auth
          </button>
        </div>
      </div>
    </header>
  );
};
