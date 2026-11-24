import React, { useRef, useState } from 'react';
import { Eye, EyeOff, KeyRound, Lock, LogOut, ShieldCheck, Clock, Ban, User } from 'lucide-react';
import {
  changePassword,
  confirmPasswordChanged,
  fetchIdentityProfile,
  MIN_PASSWORD_LENGTH,
  signInWithPassword,
  validateNewPassword,
} from '../api/identityAuth';
import type { IdentityProfile } from '../api/identityAuth';

interface IdentityGateProps {
  /** Null while nobody is signed in; set when signed in but not yet allowed into the application. */
  profile: IdentityProfile | null;
  microsoftEnabled: boolean;
  /** Notice shown above the form, for example "Your session has expired". */
  notice?: string;
  onProfile: (profile: IdentityProfile | null) => void;
  onSignOut: () => Promise<void> | void;
}

const shell: React.CSSProperties = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'linear-gradient(160deg, #0f172a 0%, #1e293b 100%)',
  padding: '24px',
};

const card: React.CSSProperties = {
  width: '100%',
  maxWidth: '420px',
  background: '#ffffff',
  borderRadius: '12px',
  padding: '28px 28px 24px',
  boxShadow: '0 20px 40px rgba(0,0,0,0.35)',
};

const inputStyle: React.CSSProperties = { paddingLeft: '34px', fontSize: '14px', width: '100%' };

function Banner({ kind, children }: { kind: 'error' | 'info'; children: React.ReactNode }) {
  const error = kind === 'error';
  return (
    <div
      role={error ? 'alert' : 'status'}
      style={{
        padding: '10px 14px',
        marginBottom: '14px',
        borderRadius: '6px',
        fontSize: '13px',
        lineHeight: 1.45,
        background: error ? '#fef2f2' : '#eff6ff',
        color: error ? '#991b1b' : '#1e3a8a',
        border: error ? '1px solid #fecaca' : '1px solid #bfdbfe',
      }}
    >
      {children}
    </div>
  );
}

function Heading({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div style={{ textAlign: 'center', marginBottom: '18px' }}>
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: '#e0f2fe',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 10px',
        }}
      >
        {icon}
      </div>
      <h1 style={{ margin: 0, fontSize: '19px', color: '#0f172a' }}>{title}</h1>
      {subtitle && <p style={{ margin: '6px 0 0', fontSize: '13px', color: '#64748b' }}>{subtitle}</p>}
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  show,
  onToggle,
  autoComplete,
  id,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  onToggle: () => void;
  autoComplete: string;
  id: string;
}) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <label htmlFor={id} style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <Lock size={16} style={{ position: 'absolute', left: '10px', top: '11px', color: '#94a3b8' }} />
        <input
          id={id}
          type={show ? 'text' : 'password'}
          className="form-control"
          style={{ ...inputStyle, paddingRight: '38px' }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          required
        />
        <button
          type="button"
          onClick={onToggle}
          aria-label={show ? 'Hide password' : 'Show password'}
          style={{ position: 'absolute', right: '8px', top: '8px', border: 'none', background: 'none', cursor: 'pointer', color: '#64748b' }}
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  );
}

const SignOutButton: React.FC<{ onSignOut: () => Promise<void> | void }> = ({ onSignOut }) => (
  <button
    type="button"
    className="erp-btn btn-secondary"
    onClick={() => void onSignOut()}
    style={{ width: '100%', justifyContent: 'center', gap: '6px', marginTop: '6px' }}
  >
    <LogOut size={14} /> Sign out
  </button>
);

export const IdentityGate: React.FC<IdentityGateProps> = ({ profile, microsoftEnabled, notice, onProfile, onSignOut }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [nextPassword, setNextPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [microsoftNote, setMicrosoftNote] = useState(false);
  const tempPassword = useRef('');

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signInWithPassword(email, password);
      const me = await fetchIdentityProfile();
      if (!me) {
        throw new Error('You signed in, but this system does not recognise the account. Contact the administrator.');
      }
      // Kept in memory only so the next screen can refuse a "new" password equal to the temporary one.
      tempPassword.current = password;
      setPassword('');
      onProfile(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validateNewPassword(nextPassword, confirmPassword, tempPassword.current || undefined);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await changePassword(nextPassword);
      await confirmPasswordChanged();
      const me = await fetchIdentityProfile();
      tempPassword.current = '';
      setNextPassword('');
      setConfirmPassword('');
      onProfile(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The password could not be changed.');
    } finally {
      setBusy(false);
    }
  };

  // ---- Signed in, but not yet allowed into the application ------------------------------------------------
  if (profile) {
    if (profile.status === 'pending') {
      return (
        <div style={shell}>
          <div style={card}>
            <Heading icon={<Clock size={24} color="#0369a1" />} title="Waiting for approval" subtitle={profile.user_id} />
            <Banner kind="info">
              Your sign-in worked, but an administrator has not approved your access yet. You will be given a role when
              they approve you. Ask your administrator, then sign in again.
            </Banner>
            <SignOutButton onSignOut={onSignOut} />
          </div>
        </div>
      );
    }
    if (profile.status === 'rejected' || profile.status === 'disabled') {
      return (
        <div style={shell}>
          <div style={card}>
            <Heading
              icon={<Ban size={24} color="#b91c1c" />}
              title={profile.status === 'rejected' ? 'Access not granted' : 'Account disabled'}
              subtitle={profile.user_id}
            />
            <Banner kind="error">
              {profile.status === 'rejected'
                ? 'Your request for access was declined by an administrator. Contact them if you think this is a mistake.'
                : 'This account has been disabled by an administrator. Contact them to have it switched back on.'}
            </Banner>
            <SignOutButton onSignOut={onSignOut} />
          </div>
        </div>
      );
    }
    if (profile.must_change_password) {
      return (
        <div style={shell}>
          <div style={card}>
            <Heading
              icon={<KeyRound size={24} color="#0369a1" />}
              title="Set your new password"
              subtitle={`Signed in as ${profile.user_id}`}
            />
            <Banner kind="info">
              You signed in with a temporary password. Choose a new password of at least {MIN_PASSWORD_LENGTH} characters
              before you continue. Only you should know it.
            </Banner>
            {error && <Banner kind="error">{error}</Banner>}
            <form onSubmit={handleChangePassword}>
              <PasswordField
                id="new-password"
                label="New password"
                value={nextPassword}
                onChange={setNextPassword}
                show={showPassword}
                onToggle={() => setShowPassword((v) => !v)}
                autoComplete="new-password"
              />
              <PasswordField
                id="confirm-password"
                label="Confirm new password"
                value={confirmPassword}
                onChange={setConfirmPassword}
                show={showPassword}
                onToggle={() => setShowPassword((v) => !v)}
                autoComplete="new-password"
              />
              <button type="submit" className="erp-btn btn-primary" disabled={busy} style={{ width: '100%', justifyContent: 'center', padding: '10px' }}>
                {busy ? 'Saving...' : 'Save new password'}
              </button>
            </form>
            <SignOutButton onSignOut={onSignOut} />
          </div>
        </div>
      );
    }
  }

  // ---- Not signed in -------------------------------------------------------------------------------------
  return (
    <div style={shell}>
      <div style={card}>
        <Heading
          icon={<ShieldCheck size={24} color="#0369a1" />}
          title="VSPL Material Management"
          subtitle="Internal system. Sign in with the account your administrator created for you."
        />
        {notice && !error && <Banner kind="info">{notice}</Banner>}
        {error && <Banner kind="error">{error}</Banner>}
        <form onSubmit={handleSignIn}>
          <div style={{ marginBottom: '14px' }}>
            <label htmlFor="identity-email" style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
              E-mail
            </label>
            <div style={{ position: 'relative' }}>
              <User size={16} style={{ position: 'absolute', left: '10px', top: '11px', color: '#94a3b8' }} />
              <input
                id="identity-email"
                type="email"
                className="form-control"
                style={inputStyle}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
          </div>
          <PasswordField
            id="identity-password"
            label="Password"
            value={password}
            onChange={setPassword}
            show={showPassword}
            onToggle={() => setShowPassword((v) => !v)}
            autoComplete="current-password"
          />
          <button type="submit" className="erp-btn btn-primary" disabled={busy} style={{ width: '100%', justifyContent: 'center', padding: '10px' }}>
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        {microsoftEnabled && (
          <>
            <div style={{ textAlign: 'center', margin: '12px 0', fontSize: '12px', color: '#94a3b8' }}>or</div>
            <button
              type="button"
              className="erp-btn btn-secondary"
              onClick={() => setMicrosoftNote(true)}
              style={{ width: '100%', justifyContent: 'center', opacity: 0.75 }}
            >
              Sign in with Microsoft
            </button>
            {microsoftNote && (
              <p style={{ fontSize: '12px', color: '#64748b', margin: '8px 0 0', textAlign: 'center' }}>
                Microsoft sign-in is not configured yet. Use your e-mail and password.
              </p>
            )}
          </>
        )}
        <p style={{ fontSize: '12px', color: '#94a3b8', margin: '16px 0 0', textAlign: 'center' }}>
          Forgot your password? Ask your administrator to reset it.
        </p>
      </div>
    </div>
  );
};

export default IdentityGate;
