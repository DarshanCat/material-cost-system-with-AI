/**
 * Central API client.
 *
 * Identity is NEVER asserted by the browser: requests carry only an opaque bearer credential that the
 * backend verifies (HTTP 401 if missing/invalid). There are no X-User-* headers, and the acting user
 * is never sent in query strings or bodies - the backend derives it from the verified credential.
 *
 * The production sign-in mechanism (JWT / Microsoft Entra ID / session) is pending IT Head approval.
 * Only this module and the sign-in functions below need to change when it is chosen.
 */

import type { UserRole } from '../types';

const TOKEN_STORAGE_KEY = 'vspl.accessToken';

export interface AuthStatus {
  provider: string;
  login_available: boolean;
}

export interface AuthUser {
  user_id: string;
  role: UserRole;
  department: string;
}

let accessToken: string | null = null;
try {
  accessToken = window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
} catch {
  accessToken = null; // storage unavailable: session lives in memory only
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  try {
    if (token) window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* ignore: in-memory token still works */
  }
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

export const UNAUTHORIZED_EVENT = 'vspl:unauthorized';

/** fetch() wrapper that attaches the bearer credential and reports 401s to the app shell. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && accessToken) {
    setAccessToken(null);
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  return response;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const res = await fetch('/api/v1/auth/status');
  if (!res.ok) throw new Error(`Auth status unavailable (HTTP ${res.status})`);
  return res.json();
}

/** Returns the verified identity for the stored credential, or null when not signed in. */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  if (!accessToken) return null;
  const res = await apiFetch('/api/v1/auth/me');
  if (!res.ok) return null;
  return res.json();
}

/**
 * Development-only sign-in (backend AUTH_PROVIDER=dev, loopback only). The server maps the requested
 * role to a fixed server-side account and returns a signed token; it is not a production mechanism.
 */
export async function devLogin(role: UserRole): Promise<AuthUser> {
  const res = await fetch('/api/v1/auth/dev-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Sign-in failed (HTTP ${res.status})`);
  }
  const data = await res.json();
  setAccessToken(data.access_token);
  return data.user as AuthUser;
}

export function signOut(): void {
  setAccessToken(null);
}

/**
 * Human-readable message for a failed response. FastAPI returns `detail` as a string, a list of
 * validation errors, or an object; anything else falls back to the HTTP status.
 */
export async function readApiError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.clone().json();
    const detail = body?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((e: any) => (e?.msg ? `${(e.loc ?? []).slice(1).join('.') || 'request'}: ${e.msg}` : String(e)))
        .join('; ');
    }
    if (detail && typeof detail === 'object') {
      return String(detail.message ?? detail.error ?? JSON.stringify(detail));
    }
  } catch {
    /* body was not JSON */
  }
  return `${fallback} (HTTP ${res.status})`;
}
