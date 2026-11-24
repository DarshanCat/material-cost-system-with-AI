import React, { useState } from 'react';
import { 
  X, 
  User, 
  ShieldCheck, 
  Lock, 
  LogOut, 
  Warehouse, 
  Flame, 
  ShoppingCart, 
  TrendingUp, 
  Key 
} from 'lucide-react';
import type { UserRole } from '../types';
import { hasAccessToken } from '../api/client';

interface SignInModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentRole?: UserRole | null;
  currentUserId?: string | null;
  loginAvailable?: boolean;
  authProvider?: string;
  onSelectRole: (role: UserRole) => Promise<void>;
  onCredentialSignIn: (username: string, password: string) => Promise<void>;
  onSignOut: () => Promise<void> | void;
}

const ROLES_INFO: Array<{
  role: UserRole;
  userId: string;
  dept: string;
  icon: React.ReactNode;
  responsibilities: string;
  colorClass: string;
  canApprove: string[];
  canCreate: string[];
}> = [
  {
    role: 'Stores',
    userId: 'usr_stores_01',
    dept: 'General / Stores',
    icon: <Warehouse size={20} className="text-emerald-600" />,
    responsibilities: 'Gate receipts (GRN), issuing raw materials & alloys to furnace, waste logging, physical audit entry.',
    colorClass: 'border-emerald-200 bg-emerald-50/50 hover:border-emerald-500',
    canCreate: ['GRN (Draft)', 'Material Issue (Draft)', 'Waste Disposition', 'Stock Audit', 'Item Request'],
    canApprove: [],
  },
  {
    role: 'Foundry',
    userId: 'usr_foundry_01',
    dept: 'Foundry / Production',
    icon: <Flame size={20} className="text-orange-600" />,
    responsibilities: 'Furnace heat logging, crucible charge tracking, heat-to-issue reconciliation, item requests.',
    colorClass: 'border-orange-200 bg-orange-50/50 hover:border-orange-500',
    canCreate: ['Heat Log', 'Item Request', 'Heat Reconciliation', 'Material Alias'],
    canApprove: [],
  },
  {
    role: 'Purchase',
    userId: 'usr_purchase_01',
    dept: 'Purchase / SCM',
    icon: <ShoppingCart size={20} className="text-blue-600" />,
    responsibilities: 'Vendor master management, purchase orders, purchase rate verification, item requests.',
    colorClass: 'border-blue-200 bg-blue-50/50 hover:border-blue-500',
    canCreate: ['Vendor Master', 'Purchase Orders', 'Item Request'],
    canApprove: [],
  },
  {
    role: 'Management',
    userId: 'usr_mgmt_01',
    dept: 'Management / Plant Head',
    icon: <TrendingUp size={20} className="text-purple-600" />,
    responsibilities: 'Authoritative checker: approves GRNs, Issues, Waste, Stock Audits & Item Requests (Maker-Checker enforced). Costing & financial reports.',
    colorClass: 'border-purple-200 bg-purple-50/50 hover:border-purple-500',
    canCreate: ['Item Request', 'Costing Run'],
    canApprove: ['GRN', 'Material Issue', 'Waste', 'Stock Audit', 'Item Request', 'Material Alias'],
  },
  {
    role: 'Quality',
    userId: 'usr_quality_01',
    dept: 'Quality / QA Lab',
    icon: <ShieldCheck size={20} className="text-teal-600" />,
    responsibilities: 'Inspects submitted GRNs (Mill Test Certificates, chemistry, physical checks) and records Passed / Conditional / Rejected. Approval is blocked until QA passes.',
    colorClass: 'border-teal-200 bg-teal-50/50 hover:border-teal-500',
    canCreate: ['QA Inspection Result'],
    canApprove: [],
  },
  {
    role: 'Accounts',
    userId: 'usr_accounts_01',
    dept: 'Accounts / Finance',
    icon: <ShoppingCart size={20} className="text-amber-600" />,
    responsibilities: 'Records vendor payments (UTR / cheque) against approved GRNs. Cannot pay a GRN they created or approved.',
    colorClass: 'border-amber-200 bg-amber-50/50 hover:border-amber-500',
    canCreate: ['Vendor Payment'],
    canApprove: [],
  },
  {
    role: 'Admin',
    userId: 'usr_admin_01',
    dept: 'Admin / IT Systems',
    icon: <ShieldCheck size={20} className="text-slate-700" />,
    responsibilities: 'System administration, user lifecycle, system audit logs, read-only system inspection. Prohibited from operational document creation and approval.',
    colorClass: 'border-slate-300 bg-slate-50/60 hover:border-slate-700',
    canCreate: [],
    canApprove: [],
  },
];

export const SignInModal: React.FC<SignInModalProps> = ({
  isOpen,
  onClose,
  currentRole,
  currentUserId,
  loginAvailable = false,
  authProvider = 'none',
  onSelectRole,
  onCredentialSignIn,
  onSignOut,
}) => {
  const isDev = import.meta.env.DEV;
  const devSwitcherEnabled = isDev && loginAvailable;
  const credentialLoginSupported = authProvider === 'password' || authProvider === 'oidc';
  const [activeTab, setActiveTab] = useState<'quick' | 'credentials'>(
    devSwitcherEnabled ? 'quick' : 'credentials'
  );
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  if (!isOpen) return null;

  const handleRoleSelect = async (role: UserRole) => {
    setLoading(true);
    setMessage(null);
    try {
      await onSelectRole(role);
      setMessage({ type: 'success', text: `Switched active session to ${role}` });
      setTimeout(() => {
        onClose();
      }, 400);
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err?.message || 'Authentication failed. No session was established.',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCredsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      await onCredentialSignIn(username.trim(), password);
      setMessage({ type: 'success', text: `Signed in successfully as ${username.trim()}` });
      setTimeout(() => {
        onClose();
      }, 500);
    } catch (err: any) {
      setMessage({
        type: 'error',
        text:
          err?.message ||
          'Credential login is not configured on this backend. Production identity provider approval is pending.',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSignOutClick = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await onSignOut();
      setMessage({ type: 'success', text: 'Session cleared and token revoked.' });
      setTimeout(() => {
        onClose();
      }, 400);
    } finally {
      setLoading(false);
    }
  };

  if (authProvider === 'identity') {
    return (
      <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
        <div
          className="modal-content max-w-3xl"
          onClick={(e) => e.stopPropagation()}
          style={{ borderRadius: '12px', overflow: 'hidden', maxWidth: '440px' }}
        >
          <div className="modal-header" style={{ background: '#1e293b', color: '#fff', padding: '16px 20px' }}>
            <h3 style={{ margin: 0, fontSize: '17px', color: '#fff' }}>VSPL Account</h3>
            <button type="button" className="close-btn" onClick={onClose} style={{ color: '#fff' }}>
              <X size={18} />
            </button>
          </div>
          <div className="modal-body" style={{ padding: '20px', fontSize: '14px' }}>
            <p style={{ marginTop: 0 }}>
              <strong>Signed in as:</strong> {currentUserId || 'not signed in'}{' '}
              {currentRole && (
                <span className="pill p-steel" style={{ padding: '2px 8px', fontSize: '11px' }}>
                  {currentRole}
                </span>
              )}
            </p>
            <p style={{ color: '#475569' }}>
              Your role is set by the system administrator and cannot be changed on this screen.
            </p>
            <button
              type="button"
              className="erp-btn btn-sm btn-secondary"
              onClick={handleSignOutClick}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#dc2626' }}
            >
              <LogOut size={13} /> Sign out
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (authProvider === 'iap') {
    return (
      <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
        <div
          className="modal-content max-w-3xl"
          onClick={(e) => e.stopPropagation()}
          style={{ borderRadius: '12px', overflow: 'hidden' }}
        >
          <div className="modal-header" style={{ background: '#1e293b', color: '#fff', padding: '16px 20px' }}>
            <h3 style={{ margin: 0, fontSize: '17px', color: '#fff' }}>VSPL Account</h3>
            <button type="button" className="close-btn" onClick={onClose} style={{ color: '#fff' }}>
              <X size={18} />
            </button>
          </div>
          <div className="modal-body" style={{ padding: '20px', fontSize: '14px' }}>
            <p style={{ marginTop: 0 }}>
              You are signed in with your company Google account. Your role is assigned by the system
              administrator and cannot be changed on this screen.
            </p>
            <p>
              <strong>Signed in as:</strong> {currentUserId || 'no role assigned'}{' '}
              {currentRole && (
                <span className="pill p-steel" style={{ padding: '2px 8px', fontSize: '11px' }}>
                  {currentRole}
                </span>
              )}
            </p>
            {!currentRole && (
              <p style={{ color: '#991b1b' }}>
                This Google account has no role in the system. Ask the administrator to add it.
              </p>
            )}
            <button
              type="button"
              className="erp-btn btn-sm btn-secondary"
              onClick={handleSignOutClick}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#dc2626' }}
            >
              <LogOut size={13} /> Sign out of Google
            </button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="modal-backdrop" onClick={onClose} style={{ zIndex: 1100 }}>
      <div 
        className="modal-content max-w-3xl" 
        onClick={(e) => e.stopPropagation()}
        style={{ borderRadius: '12px', overflow: 'hidden' }}
      >
        <div className="modal-header" style={{ background: '#1e293b', color: '#fff', padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Key size={20} className="text-cyan-400" />
            <div>
              <h3 style={{ margin: 0, fontSize: '17px', color: '#fff' }}>VSPL Authentication &amp; Role Management</h3>
              <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Secure Bearer Credential &amp; Role-Based Access Control (RBAC)
              </p>
            </div>
          </div>
          <button type="button" className="close-btn" onClick={onClose} style={{ color: '#fff' }}>
            <X size={18} />
          </button>
        </div>

        {/* Current Active Session Ribbon */}
        <div style={{ 
          background: '#f8fafc', 
          borderBottom: '1px solid #e2e8f0', 
          padding: '12px 20px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          fontSize: '13px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#64748b' }}>Active Identity:</span>
            <strong style={{ color: '#0f172a' }}>{currentUserId || 'None'}</strong>
            {currentRole ? (
              <span className="pill p-steel" style={{ padding: '2px 8px', fontSize: '11px' }}>{currentRole}</span>
            ) : (
              <span className="pill p-amber" style={{ padding: '2px 8px', fontSize: '11px' }}>Not Authenticated</span>
            )}
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              ({hasAccessToken() ? 'Bearer Token Active' : 'No Active Token'})
            </span>
          </div>
          <button 
            type="button" 
            className="erp-btn btn-sm btn-secondary"
            onClick={handleSignOutClick}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: '#dc2626' }}
          >
            <LogOut size={13} /> Sign Out
          </button>
        </div>

        <div className="modal-body" style={{ padding: '20px' }}>
          {message && (
            <div style={{ 
              padding: '10px 14px', 
              marginBottom: '16px', 
              borderRadius: '6px', 
              background: message.type === 'error' ? '#fef2f2' : '#ecfdf5', 
              color: message.type === 'error' ? '#991b1b' : '#065f46', 
              border: message.type === 'error' ? '1px solid #fecaca' : '1px solid #a7f3d0',
              fontSize: '13px'
            }}>
              {message.text}
            </div>
          )}

          {!devSwitcherEnabled && (
            <div style={{
              padding: '10px 14px',
              marginBottom: '16px',
              borderRadius: '6px',
              background: '#fef3c7',
              color: '#92400e',
              border: '1px solid #fde68a',
              fontSize: '13px'
            }}>
              <strong>{isDev ? 'Development Sign-In Unavailable:' : 'Production Security Mode:'}</strong> Direct 1-click role switching is {isDev ? `disabled when backend auth provider is "${authProvider}"` : 'disabled in production builds'}.
            </div>
          )}

          {/* Tab Selector */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '18px', borderBottom: '1px solid #e2e8f0' }}>
            {devSwitcherEnabled && (
              <button
                type="button"
                onClick={() => setActiveTab('quick')}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  fontWeight: activeTab === 'quick' ? 600 : 400,
                  color: activeTab === 'quick' ? '#0284c7' : '#64748b',
                  borderBottom: activeTab === 'quick' ? '2px solid #0284c7' : '2px solid transparent',
                  fontSize: '14px'
                }}
              >
                1-Click Role Switcher (Maker-Checker Testing)
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab('credentials')}
              style={{
                padding: '8px 16px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                fontWeight: activeTab === 'credentials' ? 600 : 400,
                color: activeTab === 'credentials' ? '#0284c7' : '#64748b',
                borderBottom: activeTab === 'credentials' ? '2px solid #0284c7' : '2px solid transparent',
                fontSize: '14px'
              }}
            >
              {isDev ? 'Standard Credential Login' : 'Corporate Identity / Credential Login'}
            </button>
          </div>

          {devSwitcherEnabled && activeTab === 'quick' ? (
            <div>
              <p style={{ fontSize: '13px', color: '#475569', marginBottom: '14px' }}>
                Select a user role to simulate maker-checker segregation of duties. Per company policy, creators of documents cannot approve their own transactions.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
                {ROLES_INFO.map((item) => {
                  const isActive = currentRole === item.role;
                  return (
                    <div
                      key={item.role}
                      onClick={() => !loading && handleRoleSelect(item.role)}
                      style={{
                        padding: '14px',
                        border: isActive ? '2px solid #0284c7' : '1px solid #cbd5e1',
                        borderRadius: '8px',
                        cursor: loading ? 'wait' : 'pointer',
                        background: isActive ? '#f0f9ff' : '#ffffff',
                        transition: 'all 0.15s ease-in-out',
                        boxShadow: isActive ? '0 0 0 2px rgba(2, 132, 199, 0.15)' : 'none'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {item.icon}
                          <div>
                            <strong style={{ fontSize: '14px', color: '#0f172a' }}>{item.role}</strong>
                            <div style={{ fontSize: '11px', color: '#64748b' }}>{item.userId} · {item.dept}</div>
                          </div>
                        </div>
                        {isActive && (
                          <span style={{ 
                            background: '#0284c7', 
                            color: '#fff', 
                            borderRadius: '999px', 
                            padding: '2px 8px', 
                            fontSize: '11px', 
                            fontWeight: 600 
                          }}>
                            Active
                          </span>
                        )}
                      </div>

                      <p style={{ fontSize: '12px', color: '#475569', marginBottom: '8px', lineHeight: 1.4 }}>
                        {item.responsibilities}
                      </p>

                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        <div><strong style={{ color: '#334155' }}>Creates:</strong> {item.canCreate.join(', ')}</div>
                        <div>
                          <strong style={{ color: '#334155' }}>Approves:</strong>{' '}
                          {item.canApprove.length > 0 ? (
                            <span style={{ color: '#059669', fontWeight: 600 }}>{item.canApprove.join(', ')}</span>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>None (Checker required)</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <form onSubmit={handleCredsSubmit} style={{ maxWidth: '420px', margin: '0 auto' }}>
              {!credentialLoginSupported && (
                <div
                  role="status"
                  style={{
                    padding: '10px 14px',
                    marginBottom: '16px',
                    borderRadius: '6px',
                    background: '#fff7ed',
                    color: '#9a3412',
                    border: '1px solid #fed7aa',
                    fontSize: '12px',
                    lineHeight: 1.45,
                  }}
                >
                  <strong>Credential Login Unavailable:</strong> Backend credential authentication is not configured
                  (current provider: <code>{authProvider}</code>). Production identity provider approval is pending.
                </div>
              )}

              <div className="mb-3">
                <label className="form-label" style={{ fontSize: '13px', fontWeight: 600 }}>
                  User Account / Email
                </label>
                <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                  <User size={16} style={{ position: 'absolute', left: '10px', color: '#94a3b8' }} />
                  <input
                    type="text"
                    className="form-control"
                    style={{ paddingLeft: '34px', fontSize: '13px' }}
                    placeholder="user@vspl.com"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className="form-label" style={{ fontSize: '13px', fontWeight: 600 }}>
                  Password
                </label>
                <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                  <Lock size={16} style={{ position: 'absolute', left: '10px', color: '#94a3b8' }} />
                  <input
                    type="password"
                    className="form-control"
                    style={{ paddingLeft: '34px', fontSize: '13px' }}
                    placeholder="Enter password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="erp-btn btn-primary w-full"
                disabled={loading}
                style={{ width: '100%', padding: '10px', fontSize: '14px', justifyContent: 'center' }}
              >
                {loading ? 'Authenticating...' : 'Sign In'}
              </button>

              <div style={{ marginTop: '16px', padding: '12px 14px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}>
                <div style={{ fontWeight: 600, color: '#334155', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Key size={14} className="text-primary" />
                  <span>Sample Login Accounts (Click to Auto-fill):</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <button 
                    type="button" 
                    className="erp-btn btn-outline btn-sm" 
                    style={{ fontSize: '11px', padding: '4px 8px', justifyContent: 'flex-start' }}
                    onClick={() => { setUsername('mgmt@vspl.com'); setPassword('mgmt123'); }}
                  >
                    👑 Management (mgmt@vspl.com)
                  </button>
                  <button 
                    type="button" 
                    className="erp-btn btn-outline btn-sm" 
                    style={{ fontSize: '11px', padding: '4px 8px', justifyContent: 'flex-start' }}
                    onClick={() => { setUsername('foundry@vspl.com'); setPassword('foundry123'); }}
                  >
                    🔥 Foundry (foundry@vspl.com)
                  </button>
                  <button 
                    type="button" 
                    className="erp-btn btn-outline btn-sm" 
                    style={{ fontSize: '11px', padding: '4px 8px', justifyContent: 'flex-start' }}
                    onClick={() => { setUsername('stores@vspl.com'); setPassword('stores123'); }}
                  >
                    🏬 Stores (stores@vspl.com)
                  </button>
                  <button 
                    type="button" 
                    className="erp-btn btn-outline btn-sm" 
                    style={{ fontSize: '11px', padding: '4px 8px', justifyContent: 'flex-start' }}
                    onClick={() => { setUsername('purchase@vspl.com'); setPassword('purchase123'); }}
                  >
                    🛒 Purchase (purchase@vspl.com)
                  </button>
                  <button 
                    type="button" 
                    className="erp-btn btn-outline btn-sm" 
                    style={{ fontSize: '11px', padding: '4px 8px', gridColumn: 'span 2', justifyContent: 'center' }}
                    onClick={() => { setUsername('admin@vspl.com'); setPassword('admin123'); }}
                  >
                    🛡️ Admin (admin@vspl.com)
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>

        <div className="modal-footer" style={{ background: '#f8fafc', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '12px', color: '#64748b' }}>
            Identity established via opaque Bearer token.
          </div>
          <button type="button" className="erp-btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
