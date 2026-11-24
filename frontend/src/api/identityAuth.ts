/**
 * Sign-in for the "identity" provider (Google Identity Platform, e-mail + password).
 *
 * The browser talks to the public Identity Toolkit REST API with the project's web API key (which is not a
 * secret) and receives a short-lived id token. That token is sent to this application's backend as a Bearer
 * credential, and the backend verifies it. Nothing here decides who may do what: roles, approval status and
 * the "must change password" rule are all enforced by the backend.
 */

import type { UserRole } from '../types';
import { apiFetch, getAccessToken, readApiError, setAccessToken, setTokenRefresher, signOut } from './client.ts';

const IDENTITY_TOOLKIT = 'https://identitytoolkit.googleapis.com/v1';
const SECURE_TOKEN = 'https://securetoken.googleapis.com/v1/token';
const REFRESH_KEY = 'vspl.refreshToken';
const EXPIRY_KEY = 'vspl.tokenExpiry';
/** Renew the id token when it has less than this long left. */
export const REFRESH_MARGIN_MS = 5 * 60 * 1000;
export const MIN_PASSWORD_LENGTH = 10;

export type IdentityStatus = 'active' | 'pending' | 'rejected' | 'disabled';

/** Verified identity from `/auth/me` under the identity provider. `role` is null until an administrator approves. */
export interface IdentityProfile {
  user_id: string;
  role: UserRole | null;
  department: string;
  status: IdentityStatus;
  must_change_password: boolean;
  display_name: string;
}

let apiKey = '';
let refreshInFlight: Promise<void> | null = null;

function storageGet(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key: string, value: string | null): void {
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the session then lives in memory only */
  }
}

// In-memory copy so a storage failure does not break renewal inside one page load.
let memoryRefreshToken: string | null = null;
let memoryExpiry = 0;

function readRefreshToken(): string | null {
  return memoryRefreshToken ?? storageGet(REFRESH_KEY);
}

function readExpiry(): number {
  if (memoryExpiry) return memoryExpiry;
  const raw = storageGet(EXPIRY_KEY);
  const parsed = raw ? Number(raw) : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

function storeSession(idToken: string, refreshToken: string, expiresInSeconds: number): void {
  const seconds = Number.isFinite(expiresInSeconds) && expiresInSeconds > 0 ? expiresInSeconds : 3600;
  memoryRefreshToken = refreshToken;
  memoryExpiry = Date.now() + seconds * 1000;
  setAccessToken(idToken);
  storageSet(REFRESH_KEY, refreshToken);
  storageSet(EXPIRY_KEY, String(memoryExpiry));
}

/** Forget the refresh token and expiry (the id token itself is cleared through `setAccessToken(null)`). */
export function clearIdentitySession(): void {
  memoryRefreshToken = null;
  memoryExpiry = 0;
  storageSet(REFRESH_KEY, null);
  storageSet(EXPIRY_KEY, null);
  setAccessToken(null);
}

/** Give the module the web API key reported by `/auth/status`, and arm automatic token renewal. */
export function configureIdentity(key: string): void {
  apiKey = key || '';
  setTokenRefresher(apiKey ? ensureFreshToken : null);
}

const ERROR_MESSAGES: Record<string, string> = {
  INVALID_LOGIN_CREDENTIALS: 'The e-mail or password is not correct.',
  INVALID_PASSWORD: 'The e-mail or password is not correct.',
  EMAIL_NOT_FOUND: 'The e-mail or password is not correct.',
  INVALID_EMAIL: 'Enter a valid e-mail address.',
  MISSING_PASSWORD: 'Enter your password.',
  USER_DISABLED: 'This account has been disabled. Contact the administrator.',
  TOO_MANY_ATTEMPTS_TRY_LATER: 'Too many attempts. Wait a few minutes and try again.',
  WEAK_PASSWORD: 'That password is too weak. Use a longer password with letters and numbers.',
  CREDENTIAL_TOO_OLD_LOGIN_AGAIN: 'For security, sign in again and then change the password.',
  TOKEN_EXPIRED: 'Your session has expired. Sign in again.',
  INVALID_REFRESH_TOKEN: 'Your session has expired. Sign in again.',
  INVALID_ID_TOKEN: 'Your session has expired. Sign in again.',
  USER_NOT_FOUND: 'Your session has expired. Sign in again.',
  OPERATION_NOT_ALLOWED: 'Password sign-in is not enabled. Contact the administrator.',
  API_KEY_NOT_VALID: 'Sign-in is not configured correctly. Contact the administrator.',
};

/** Map a Google Identity error code (for example "WEAK_PASSWORD : Password should be at least 6 characters") to plain words. */
export function mapIdentityError(code: string | undefined | null): string {
  const key = String(code ?? '').split(':')[0].trim().split(' ')[0].trim().toUpperCase();
  if (key && ERROR_MESSAGES[key]) return ERROR_MESSAGES[key];
  return 'Sign-in failed. Check your details and try again.';
}

async function postIdentity(url: string, init: RequestInit): Promise<Record<string, unknown>> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error('Cannot reach the sign-in service. Check your connection and try again.');
  }
  let body: Record<string, any> = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) {
    throw new Error(mapIdentityError(body?.error?.message));
  }
  return body;
}

function requireKey(): string {
  if (!apiKey) throw new Error('Sign-in is not configured correctly. Contact the administrator.');
  return apiKey;
}

function readTokens(body: Record<string, any>, kind: 'rest' | 'secure'): { id: string; refresh: string; ttl: number } {
  const id = kind === 'rest' ? body.idToken : body.id_token;
  const refresh = kind === 'rest' ? body.refreshToken : body.refresh_token;
  const ttl = Number(kind === 'rest' ? body.expiresIn : body.expires_in);
  if (typeof id !== 'string' || !id || typeof refresh !== 'string' || !refresh) {
    throw new Error('Invalid response from the sign-in service.');
  }
  return { id, refresh, ttl };
}

/** E-mail and password sign-in. Stores the session on success and throws a friendly Error on failure. */
export async function signInWithPassword(email: string, password: string): Promise<void> {
  const key = requireKey();
  const body = await postIdentity(`${IDENTITY_TOOLKIT}/accounts:signInWithPassword?key=${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password, returnSecureToken: true }),
  });
  const t = readTokens(body, 'rest');
  storeSession(t.id, t.refresh, t.ttl);
}

/** Exchange the refresh token for a new id token. Concurrent callers share one request. */
export function refreshIdToken(): Promise<void> {
  if (refreshInFlight) return refreshInFlight;
  const run = (async () => {
    const key = requireKey();
    const refresh = readRefreshToken();
    if (!refresh) throw new Error(mapIdentityError('TOKEN_EXPIRED'));
    try {
      const body = await postIdentity(`${SECURE_TOKEN}?key=${encodeURIComponent(key)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: refresh }).toString(),
      });
      const t = readTokens(body, 'secure');
      storeSession(t.id, t.refresh, t.ttl);
    } catch (err) {
      const message = err instanceof Error ? err.message : '';
      // The refresh token itself was refused: the session is over. A network failure is retried next time.
      if (message === mapIdentityError('TOKEN_EXPIRED')) clearIdentitySession();
      throw err;
    }
  })();
  refreshInFlight = run.finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** Renew the id token if it is within five minutes of expiry. Does nothing when signed out. */
export async function ensureFreshToken(): Promise<void> {
  if (!getAccessToken() || !readRefreshToken()) return;
  const expiry = readExpiry();
  if (expiry && expiry - Date.now() > REFRESH_MARGIN_MS) return;
  await refreshIdToken();
}

/** Set a new password for the signed-in user. The new id token replaces the old one. */
export async function changePassword(newPassword: string): Promise<void> {
  const key = requireKey();
  const idToken = getAccessToken();
  if (!idToken) throw new Error(mapIdentityError('TOKEN_EXPIRED'));
  const body = await postIdentity(`${IDENTITY_TOOLKIT}/accounts:update?key=${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idToken, password: newPassword, returnSecureToken: true }),
  });
  const t = readTokens(body, 'rest');
  storeSession(t.id, t.refresh, t.ttl);
}

/** Tell the backend the password was changed so it lifts the "must change password" restriction. */
export async function confirmPasswordChanged(): Promise<void> {
  const res = await apiFetch('/api/v1/auth/password-changed', { method: 'POST' });
  if (!res.ok) {
    throw new Error(await readApiError(res, 'Could not confirm the password change'));
  }
}

/** Identity, role and approval status of the signed-in user, or null when the token is missing or refused. */
export async function fetchIdentityProfile(): Promise<IdentityProfile | null> {
  if (!getAccessToken()) return null;
  try {
    const res = await apiFetch('/api/v1/auth/me');
    if (!res.ok) return null;
    const data = await res.json();
    if (!data || typeof data.user_id !== 'string') return null;
    const status: IdentityStatus = ['active', 'pending', 'rejected', 'disabled'].includes(data.status) ? data.status : 'disabled';
    return {
      user_id: data.user_id,
      role: data.role ?? null,
      department: String(data.department ?? ''),
      status,
      must_change_password: Boolean(data.must_change_password),
      display_name: String(data.display_name ?? ''),
    };
  } catch {
    return null;
  }
}

/** Sign out: revoke on the server where possible, then forget the whole session. */
export async function signOutIdentity(): Promise<void> {
  try {
    await signOut();
  } finally {
    clearIdentitySession();
  }
}

/** Why a new password is unacceptable, or null if it is fine. Mirrors the rule the form shows. */
export function validateNewPassword(next: string, confirm: string, current?: string): string | null {
  if (next.length < MIN_PASSWORD_LENGTH) return `The new password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (next !== confirm) return 'The two passwords do not match.';
  if (current !== undefined && next === current) return 'The new password must be different from the temporary password.';
  return null;
}
