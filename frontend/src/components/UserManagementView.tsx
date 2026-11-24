import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Copy, KeyRound, RefreshCw, ShieldAlert, UserPlus, X } from 'lucide-react';
import type { UserRole } from '../types';
import {
  approveUser,
  ASSIGNABLE_ROLES,
  createUser,
  disableUser,
  enableUser,
  listUserAuditLog,
  listUsers,
  rejectUser,
  resetUserPassword,
  updateUser,
} from '../api/users';
import type { ManagedUser, UserAuditEntry, UserStatus } from '../api/users';

interface UserManagementViewProps {
  currentRole: UserRole;
  /** E-mail of the signed-in administrator (their own row cannot be disabled or demoted here). */
  currentUserId: string;
}

interface TempReveal {
  email: string;
  password: string;
  kind: 'created' | 'reset';
}

const STATUS_STYLE: Record<UserStatus, { bg: string; fg: string; label: string }> = {
  active: { bg: '#dcfce7', fg: '#166534', label: 'Active' },
  pending: { bg: '#fef3c7', fg: '#92400e', label: 'Pending approval' },
  rejected: { bg: '#fee2e2', fg: '#991b1b', label: 'Rejected' },
  disabled: { bg: '#e2e8f0', fg: '#334155', label: 'Disabled' },
};

function StatusPill({ status }: { status: UserStatus }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.disabled;
  return (
    <span style={{ background: s.bg, color: s.fg, padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: 600, whiteSpace: 'nowrap' }}>
      {s.label}
    </span>
  );
}

function formatWhen(value: string | null): string {
  if (!value) return 'Never';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

export const UserManagementView: React.FC<UserManagementViewProps> = ({ currentRole, currentUserId }) => {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [audit, setAudit] = useState<UserAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | UserStatus>('all');
  const [reveal, setReveal] = useState<TempReveal | null>(null);
  const [copied, setCopied] = useState(false);
  const [resetTarget, setResetTarget] = useState<ManagedUser | null>(null);

  // Create form
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState<UserRole>('Stores');
  const [newDepartment, setNewDepartment] = useState('');
  const [creating, setCreating] = useState(false);

  // Per-row draft values: pending approvals and role edits
  const [draftRole, setDraftRole] = useState<Record<number, UserRole>>({});
  const [draftDept, setDraftDept] = useState<Record<number, string>>({});

  const isAdmin = currentRole === 'Admin';
  const me = (currentUserId || '').trim().toLowerCase();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, a] = await Promise.all([listUsers(), listUserAuditLog(50).catch(() => ({ items: [] as UserAuditEntry[] }))]);
      setUsers(u.items);
      setAudit(a.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load users.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) void load();
  }, [isAdmin, load]);

  const counts = useMemo(() => {
    const c = { total: users.length, active: 0, pending: 0, disabled: 0, rejected: 0 };
    for (const u of users) {
      if (u.status === 'active') c.active += 1;
      else if (u.status === 'pending') c.pending += 1;
      else if (u.status === 'disabled') c.disabled += 1;
      else if (u.status === 'rejected') c.rejected += 1;
    }
    return c;
  }, [users]);

  const pending = useMemo(() => users.filter((u) => u.status === 'pending'), [users]);
  const visibleUsers = useMemo(
    () => users.filter((u) => u.status !== 'pending' && (filter === 'all' || u.status === filter)),
    [users, filter],
  );

  const replaceUser = (updated: ManagedUser) => {
    setUsers((prev) => (prev.some((u) => u.id === updated.id) ? prev.map((u) => (u.id === updated.id ? updated : u)) : [updated, ...prev]));
  };

  const refreshAudit = async () => {
    try {
      setAudit((await listUserAuditLog(50)).items);
    } catch {
      /* the audit panel is informational; ignore a refresh failure */
    }
  };

  const run = async (id: number | null, action: () => Promise<void>) => {
    setBusyId(id);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refreshAudit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createUser({ email: newEmail, display_name: newName, role: newRole, department: newDepartment });
      replaceUser(result.user);
      setReveal({ email: result.user.email, password: result.temporary_password, kind: 'created' });
      setCopied(false);
      setNewEmail('');
      setNewName('');
      setNewDepartment('');
      await refreshAudit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the user.');
    } finally {
      setCreating(false);
    }
  };

  const copyPassword = async () => {
    if (!reveal) return;
    try {
      await navigator.clipboard.writeText(reveal.password);
      setCopied(true);
    } catch {
      setCopied(false);
      setNotice('Copy failed. Select the password and copy it by hand.');
    }
  };

  const confirmReset = async () => {
    const target = resetTarget;
    if (!target) return;
    setResetTarget(null);
    await run(target.id, async () => {
      const result = await resetUserPassword(target.id);
      replaceUser(result.user);
      setReveal({ email: result.user.email, password: result.temporary_password, kind: 'reset' });
      setCopied(false);
    });
  };

  if (!isAdmin) {
    return (
      <div className="module-container">
        <div className="error-banner card mb-3" role="alert">
          <ShieldAlert size={16} /> Only an administrator can manage users.
        </div>
      </div>
    );
  }

  const roleOptions = ASSIGNABLE_ROLES.map((r) => (
    <option key={r} value={r}>
      {r}
    </option>
  ));

  return (
    <div className="module-container">
      <div className="view-header-row">
        <div>
          <h2 className="view-title">User Management</h2>
          <p className="view-subtitle">
            Create accounts, approve people who sign in for the first time, and give each person exactly one role. Every
            change is recorded below.
          </p>
        </div>
        <button type="button" className="erp-btn btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && (
        <div className="error-banner card mb-3" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="success-banner card mb-3" role="status">
          {notice}
        </div>
      )}

      {reveal && (
        <div
          role="alert"
          style={{ border: '2px solid #f59e0b', background: '#fffbeb', borderRadius: '8px', padding: '14px 16px', marginBottom: '16px' }}
        >
          <div style={{ fontWeight: 700, color: '#92400e', marginBottom: '6px' }}>
            {reveal.kind === 'created' ? 'Account created' : 'Password reset'} for {reveal.email}
          </div>
          <div style={{ fontSize: '13px', color: '#78350f', marginBottom: '8px' }}>
            Temporary password. It is shown <strong>only once</strong> and cannot be retrieved later. Give it to the person
            privately. They must change it the first time they sign in.
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <code
              data-testid="temporary-password"
              style={{ background: '#fff', border: '1px solid #fcd34d', borderRadius: '6px', padding: '8px 12px', fontSize: '15px', userSelect: 'all' }}
            >
              {reveal.password}
            </code>
            <button type="button" className="erp-btn btn-sm btn-secondary" onClick={() => void copyPassword()}>
              {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
            </button>
            <button type="button" className="erp-btn btn-sm btn-secondary" onClick={() => setReveal(null)}>
              <X size={13} /> I have saved it, hide
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {[
          ['Total users', counts.total],
          ['Active', counts.active],
          ['Pending approval', counts.pending],
          ['Disabled', counts.disabled],
          ['Rejected', counts.rejected],
        ].map(([label, value]) => (
          <div key={label as string} className="card" style={{ padding: '12px 14px' }}>
            <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>{label}</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a' }}>{value}</div>
          </div>
        ))}
      </div>

      {pending.length > 0 && (
        <div className="card table-card mb-3" style={{ border: '1px solid #fcd34d' }}>
          <div className="card-header-row mb-3">
            <h3 className="card-title">Pending approval ({pending.length})</h3>
          </div>
          <table className="erp-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Requested</th>
                <th>Role to give</th>
                <th>Department (optional)</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="font-semibold">{u.display_name || u.email}</div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>{u.email}</div>
                  </td>
                  <td>{formatWhen(u.created_at)}</td>
                  <td>
                    <select
                      className="form-input"
                      aria-label={`Role for ${u.email}`}
                      value={draftRole[u.id] ?? ''}
                      onChange={(e) => setDraftRole((p) => ({ ...p, [u.id]: e.target.value as UserRole }))}
                    >
                      <option value="">Choose a role...</option>
                      {roleOptions}
                    </select>
                  </td>
                  <td>
                    <input
                      className="form-input"
                      aria-label={`Department for ${u.email}`}
                      value={draftDept[u.id] ?? ''}
                      onChange={(e) => setDraftDept((p) => ({ ...p, [u.id]: e.target.value }))}
                      placeholder="Uses the role default"
                    />
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button
                      type="button"
                      className="erp-btn btn-sm btn-primary"
                      disabled={busyId === u.id || !draftRole[u.id]}
                      onClick={() =>
                        void run(u.id, async () => {
                          replaceUser(await approveUser(u.id, draftRole[u.id], draftDept[u.id]));
                          setNotice(`${u.email} approved as ${draftRole[u.id]}.`);
                        })
                      }
                    >
                      Approve
                    </button>{' '}
                    <button
                      type="button"
                      className="erp-btn btn-sm btn-secondary"
                      disabled={busyId === u.id}
                      onClick={() =>
                        void run(u.id, async () => {
                          replaceUser(await rejectUser(u.id));
                          setNotice(`${u.email} rejected.`);
                        })
                      }
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card mb-3" style={{ padding: '16px' }}>
        <div className="card-header-row mb-3">
          <h3 className="card-title">
            <UserPlus size={15} style={{ verticalAlign: '-2px' }} /> Create a user
          </h3>
        </div>
        <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px', alignItems: 'end' }}>
          <div className="form-group">
            <label className="form-label" htmlFor="new-user-email">E-mail *</label>
            <input id="new-user-email" type="email" className="form-input" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="new-user-name">Display name *</label>
            <input id="new-user-name" className="form-input" value={newName} onChange={(e) => setNewName(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="new-user-role">Role *</label>
            <select id="new-user-role" className="form-input" value={newRole} onChange={(e) => setNewRole(e.target.value as UserRole)}>
              {roleOptions}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="new-user-dept">Department (optional)</label>
            <input id="new-user-dept" className="form-input" value={newDepartment} onChange={(e) => setNewDepartment(e.target.value)} />
          </div>
          <div className="form-group">
            <button type="submit" className="erp-btn btn-primary" disabled={creating}>
              {creating ? 'Creating...' : 'Create user'}
            </button>
          </div>
        </form>
        <p className="form-hint" style={{ marginTop: '8px' }}>
          The system generates a temporary password and shows it once. The new user must set their own password at first sign-in.
        </p>
      </div>

      <div className="card table-card mb-3">
        <div className="card-header-row mb-3">
          <h3 className="card-title">Users</h3>
          <select className="form-input" aria-label="Filter users by status" style={{ maxWidth: '180px' }} value={filter} onChange={(e) => setFilter(e.target.value as 'all' | UserStatus)}>
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
        {loading ? (
          <div className="loading-state">
            <div className="spinner" /> Loading users...
          </div>
        ) : (
          <table className="erp-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Status</th>
                <th>Role</th>
                <th>Last sign-in</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleUsers.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                    No users to show.
                  </td>
                </tr>
              )}
              {visibleUsers.map((u) => {
                const isSelf = u.email.trim().toLowerCase() === me;
                const draft = draftRole[u.id];
                const roleChanged = draft !== undefined && draft !== u.role;
                return (
                  <tr key={u.id}>
                    <td>
                      <div className="font-semibold">
                        {u.display_name || u.email} {isSelf && <span style={{ fontSize: '11px', color: '#64748b' }}>(you)</span>}
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>
                        {u.email}
                        {u.department ? ` · ${u.department}` : ''}
                      </div>
                      {u.must_change_password && <div style={{ fontSize: '11px', color: '#b45309' }}>Must change password at next sign-in</div>}
                    </td>
                    <td>
                      <StatusPill status={u.status} />
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <select
                          className="form-input"
                          aria-label={`Role of ${u.email}`}
                          disabled={isSelf || busyId === u.id}
                          title={isSelf ? 'You cannot change your own role' : undefined}
                          value={draft ?? u.role ?? ''}
                          onChange={(e) => setDraftRole((p) => ({ ...p, [u.id]: e.target.value as UserRole }))}
                        >
                          {!u.role && <option value="">No role</option>}
                          {roleOptions}
                        </select>
                        {roleChanged && (
                          <button
                            type="button"
                            className="erp-btn btn-sm btn-primary"
                            disabled={busyId === u.id || isSelf}
                            onClick={() =>
                              void run(u.id, async () => {
                                replaceUser(await updateUser(u.id, { role: draft }));
                                setDraftRole((p) => {
                                  const next = { ...p };
                                  delete next[u.id];
                                  return next;
                                });
                                setNotice(`${u.email} is now ${draft}.`);
                              })
                            }
                          >
                            Save role
                          </button>
                        )}
                      </div>
                    </td>
                    <td>{formatWhen(u.last_login_at)}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {u.status === 'disabled' || u.status === 'rejected' ? (
                        <button
                          type="button"
                          className="erp-btn btn-sm btn-secondary"
                          disabled={busyId === u.id || isSelf}
                          onClick={() =>
                            void run(u.id, async () => {
                              replaceUser(await enableUser(u.id));
                              setNotice(`${u.email} enabled.`);
                            })
                          }
                        >
                          Enable
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="erp-btn btn-sm btn-secondary"
                          disabled={busyId === u.id || isSelf}
                          title={isSelf ? 'You cannot disable your own account' : undefined}
                          onClick={() =>
                            void run(u.id, async () => {
                              replaceUser(await disableUser(u.id));
                              setNotice(`${u.email} disabled.`);
                            })
                          }
                        >
                          Disable
                        </button>
                      )}{' '}
                      <button
                        type="button"
                        className="erp-btn btn-sm btn-secondary"
                        disabled={busyId === u.id}
                        onClick={() => setResetTarget(u)}
                      >
                        <KeyRound size={12} /> Reset password
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card table-card">
        <div className="card-header-row mb-3">
          <h3 className="card-title">Recent changes</h3>
        </div>
        <table className="erp-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Person</th>
              <th>Action</th>
              <th>By</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {audit.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  No changes recorded yet.
                </td>
              </tr>
            )}
            {audit.map((a) => (
              <tr key={a.id}>
                <td>{formatWhen(a.created_at)}</td>
                <td>{a.user_email}</td>
                <td>{a.action}</td>
                <td>{a.actor}</td>
                <td>{a.detail ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {resetTarget && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Confirm password reset" onClick={() => setResetTarget(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '440px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Reset password?</h3>
              <button type="button" className="close-btn" onClick={() => setResetTarget(null)} aria-label="Close">
                <X size={16} />
              </button>
            </div>
            <div className="modal-body" style={{ fontSize: '14px' }}>
              This replaces the password of <strong>{resetTarget.email}</strong> with a new temporary one, shown to you once.
              They will have to choose their own password at the next sign-in.
            </div>
            <div className="modal-footer">
              <button type="button" className="erp-btn btn-secondary" onClick={() => setResetTarget(null)}>
                Cancel
              </button>
              <button type="button" className="erp-btn btn-primary" onClick={() => void confirmReset()}>
                Reset password
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementView;
