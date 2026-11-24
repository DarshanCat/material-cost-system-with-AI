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

import type { UserRole, MaterialItem, Vendor, UOM, Department } from '../types';
import { handleMockRequest } from './mockHandler.ts';

const TOKEN_STORAGE_KEY = 'vspl.accessToken';

export interface AuthStatus {
  provider: string;
  login_available: boolean;
  /** Public web API key of the Google Identity Platform project (provider "identity" only). */
  identity_api_key?: string;
  /** True when the administrator has switched on Microsoft sign-in (provider "identity" only). */
  microsoft_enabled?: boolean;
}

export interface AuthUser {
  user_id: string;
  role: UserRole;
  department: string;
  status?: string;
  must_change_password?: boolean;
  display_name?: string;
}

/**
 * Optional hook run before every request that carries a bearer token. The identity provider registers one
 * so that an id token close to expiry is renewed first (set here to avoid a circular import).
 */
let tokenRefresher: (() => Promise<void>) | null = null;

export function setTokenRefresher(fn: (() => Promise<void>) | null): void {
  tokenRefresher = fn;
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

export function getAccessToken(): string | null {
  return accessToken;
}

export const UNAUTHORIZED_EVENT = 'vspl:unauthorized';

// In-memory response cache for high-frequency reference & catalog endpoints
interface CacheEntry {
  body: string;
  headers: [string, string][];
  status: number;
  timestamp: number;
}
const apiCache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 120_000; // 2 minutes

export function clearApiCache(): void {
  apiCache.clear();
}

const CACHEABLE_PREFIXES = [
  '/api/v1/departments',
  '/api/v1/uoms',
  '/api/v1/items/categories',
  '/api/v1/vendors',
  '/api/v1/items',
  '/api/v1/auth/status',
];

function isCacheable(url: string, method?: string): boolean {
  if (method && method.toUpperCase() !== 'GET') return false;
  return CACHEABLE_PREFIXES.some(prefix => url.startsWith(prefix));
}

function isAuthEndpoint(input: string): boolean {
  return input.startsWith('/api/v1/auth/') || input.includes('/api/v1/auth/');
}

/** fetch() wrapper that attaches the bearer credential and falls back to demo data if the server is unreachable (never for auth routes). */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase();

  // If a mutation happens (POST, PUT, DELETE, PATCH), invalidate reference cache
  if (method !== 'GET') {
    apiCache.clear();
  }

  // Check in-memory cache for safe GET endpoints
  if (isCacheable(input, method)) {
    const cached = apiCache.get(input);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
      return new Response(cached.body, {
        status: cached.status,
        headers: new Headers(cached.headers),
      });
    }
  }

  const headers = new Headers(init.headers);
  if (!headers.has('bypass-tunnel-reminder')) {
    headers.set('bypass-tunnel-reminder', 'true');
  }
  if (!headers.has('ngrok-skip-browser-warning')) {
    headers.set('ngrok-skip-browser-warning', '1');
  }
  if (accessToken && tokenRefresher && !headers.has('Authorization')) {
    try {
      await tokenRefresher();
    } catch {
      /* a failed renewal is not fatal here: the request goes out and the server answers 401 if needed */
    }
  }
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const isAuth = isAuthEndpoint(input);

  try {
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401) {
      setAccessToken(null);
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }

    // Cache successful GET responses for reference endpoints
    if (response.ok && isCacheable(input, method)) {
      const cloned = response.clone();
      cloned.text().then((text) => {
        const headerPairs: [string, string][] = [];
        response.headers.forEach((val, key) => headerPairs.push([key, val]));
        apiCache.set(input, {
          body: text,
          headers: headerPairs,
          status: response.status,
          timestamp: Date.now(),
        });
      }).catch(() => {});
    }

    const contentType = response.headers.get('content-type') || '';
    // Mock fallback is strictly prohibited in production builds and NEVER allowed for auth routes:
    if (
      !import.meta.env?.PROD &&
      !isAuth &&
      (contentType.includes('text/html') || response.status === 404 || response.status === 405 || response.status >= 500)
    ) {
      const mockRes = handleMockRequest(input, init);
      if (mockRes) return mockRes;
    }
    return response;
  } catch (err) {
    // In production or for auth routes, network errors must never silently degrade into fake identity/data:
    if (!import.meta.env?.PROD && !isAuth) {
      const mockRes = handleMockRequest(input, init);
      if (mockRes) return mockRes;
    }
    throw err;
  }
}

/** Provider reported by the backend (for example "iap" behind Google Identity-Aware Proxy). */
let authProvider = 'none';

export function getAuthProvider(): string {
  return authProvider;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  try {
    const res = await apiFetch('/api/v1/auth/status');
    if (res.ok) {
      const status: AuthStatus = await res.json();
      authProvider = status.provider;
      return status;
    }
  } catch {}
  authProvider = 'none';
  return { provider: 'none', login_available: false };
}

/** Returns the verified identity for the stored credential, or null if unauthenticated. */
export async function fetchCurrentUser(options: { withoutToken?: boolean } = {}): Promise<AuthUser | null> {
  try {
    // Behind Google Identity-Aware Proxy the browser holds no bearer token: the proxy supplies the identity.
    if (accessToken || options.withoutToken) {
      const res = await apiFetch('/api/v1/auth/me');
      if (res.ok) return res.json();
    }
  } catch {}
  return null;
}

/**
 * Development sign-in: requests a server-issued signed token for the selected dev role.
 * Never fabricates client-side identities or demo tokens when the backend rejects or is unavailable.
 */
export async function devLogin(role: UserRole): Promise<AuthUser> {
  if (import.meta.env?.PROD) {
    throw new Error('Development sign-in is disabled in production builds.');
  }
  const res = await apiFetch('/api/v1/auth/dev-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    throw new Error(await readApiError(res, 'Development sign-in failed'));
  }
  const data = await res.json();
  if (!data?.access_token || !data?.user?.user_id || !data?.user?.role) {
    throw new Error('Invalid authentication response from server.');
  }
  setAccessToken(data.access_token);
  return data.user as AuthUser;
}

/**
 * Credential sign-in: sends entered credentials to the backend without simulating authentication.
 */
export async function loginWithCredentials(username: string, password: string): Promise<AuthUser> {
  const res = await apiFetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error(
      await readApiError(res, 'Credential login is not available on this backend')
    );
  }
  const data = await res.json();
  if (!data?.access_token || !data?.user?.user_id || !data?.user?.role) {
    throw new Error('Invalid authentication response from server.');
  }
  setAccessToken(data.access_token);
  return data.user as AuthUser;
}

/**
 * Revokes the current bearer token on the server (when present) and clears local auth state.
 */
export async function signOut(): Promise<void> {
  const token = accessToken;
  setAccessToken(null);
  if (!token) {
    signOutOfProxy();
    return;
  }
  try {
    await fetch('/api/v1/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    /* local token already cleared; server unavailability does not keep client signed in */
  }
  signOutOfProxy();
}

/** Ends a Google Identity-Aware Proxy session (the proxy, not this app, owns that session). */
export function signOutOfProxy(): void {
  if (authProvider === 'iap' && typeof window !== 'undefined' && window.location) {
    window.location.assign('/_gcp_iap/clear_login_cookie');
  }
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


/**
 * Unwraps an items API response that can be either a PaginatedResponse<T> or a direct array of T.
 * Validates the data contract: if the response is neither an array nor an object containing
 * an items array, it raises a contract error rather than silently hiding invalid data.
 */
export function extractItems<T>(data: unknown): T[] {
  if (Array.isArray(data)) {
    return data;
  }
  if (data && typeof data === 'object' && Array.isArray((data as any).items)) {
    return (data as any).items;
  }
  throw new Error(
    `Invalid items response contract: expected array or { items: [...] }, got ${
      data === null ? 'null' : typeof data
    }`
  );
}

type FieldType = 'number' | 'string';
type Fetcher = (input: string) => Promise<Response>;

/**
 * Validates that every record carries the fields a reference list depends on (ids for option values,
 * codes/names for labels). Throws naming the first bad record so a contract change is visible instead
 * of rendering blank or broken dropdown options.
 */
export function validateRecords<T>(rows: unknown[], label: string, fields: Record<string, FieldType>): T[] {
  rows.forEach((row, index) => {
    if (!row || typeof row !== 'object') {
      throw new Error(`Invalid ${label} record at index ${index}: expected an object`);
    }
    for (const [field, type] of Object.entries(fields)) {
      if (typeof (row as Record<string, unknown>)[field] !== type) {
        throw new Error(`Invalid ${label} record at index ${index}: '${field}' must be a ${type}`);
      }
    }
  });
  return rows as T[];
}

const ITEM_FIELDS: Record<string, FieldType> = { id: 'number', item_code: 'string', name: 'string', base_uom_id: 'number' };
const VENDOR_FIELDS: Record<string, FieldType> = { id: 'number', name: 'string' };
const UOM_FIELDS: Record<string, FieldType> = { id: 'number', code: 'string', name: 'string' };
const DEPARTMENT_FIELDS: Record<string, FieldType> = { id: 'number', code: 'string', name: 'string' };

/** Largest page the list endpoints accept (`size` is capped at 1000 server-side). */
export const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 100;

/**
 * Fetches every page of a paginated list endpoint until the API-reported `total` is reached.
 * Throws if the envelope is malformed, a page fails, or the server stops returning rows before
 * `total` - a partial reference list would silently hide valid choices.
 */
export async function fetchAllPages<T>(
  path: string,
  label: string,
  fields: Record<string, FieldType>,
  { pageSize = MAX_PAGE_SIZE, fetcher = apiFetch }: { pageSize?: number; fetcher?: Fetcher } = {},
): Promise<T[]> {
  const byId = new Map<unknown, T>();
  const separator = path.includes('?') ? '&' : '?';
  let received = 0;

  for (let page = 1; page <= MAX_PAGES; page++) {
    const res = await fetcher(`${path}${separator}page=${page}&size=${pageSize}`);
    if (!res.ok) throw new Error(await readApiError(res, `Failed to load ${label} (page ${page})`));

    const body: unknown = await res.json();
    const total = (body as { total?: unknown } | null)?.total;
    if (!Array.isArray((body as { items?: unknown } | null)?.items) || !Number.isInteger(total) || (total as number) < 0) {
      throw new Error(`Invalid ${label} response contract: expected { items: [...], total: <integer> }`);
    }
    const rows = validateRecords<T>((body as { items: unknown[] }).items, label, fields);
    // Rows inserted between page requests can shift offsets and repeat a record; keep one per id.
    for (const row of rows) byId.set((row as { id: unknown }).id, row);
    received += rows.length;

    if (received >= (total as number)) return [...byId.values()];
    if (rows.length === 0) {
      throw new Error(`Incomplete ${label} list: server reported ${total} records but returned ${received}`);
    }
  }
  throw new Error(`Stopped loading ${label} after ${MAX_PAGES} pages; the list is larger than expected`);
}

/** Fetches a non-paginated list endpoint (bare JSON array) and validates each record. */
export async function fetchList<T>(
  path: string,
  label: string,
  fields: Record<string, FieldType>,
  fetcher: Fetcher = apiFetch,
): Promise<T[]> {
  const res = await fetcher(path);
  if (!res.ok) throw new Error(await readApiError(res, `Failed to load ${label}`));
  const body: unknown = await res.json();
  if (!Array.isArray(body)) {
    throw new Error(`Invalid ${label} response contract: expected an array, got ${body === null ? 'null' : typeof body}`);
  }
  return validateRecords<T>(body, label, fields);
}

/** All active material items, across every page, for reference/dropdown lists. */
export function fetchReferenceItems(fetcher: Fetcher = apiFetch): Promise<MaterialItem[]> {
  return fetchAllPages<MaterialItem>('/api/v1/items', 'material items', ITEM_FIELDS, { fetcher });
}

/** All active vendors, across every page. */
export function fetchReferenceVendors(fetcher: Fetcher = apiFetch): Promise<Vendor[]> {
  return fetchAllPages<Vendor>('/api/v1/vendors', 'vendors', VENDOR_FIELDS, { fetcher });
}

export function fetchReferenceUoms(fetcher: Fetcher = apiFetch): Promise<UOM[]> {
  return fetchList<UOM>('/api/v1/uoms', 'units of measure', UOM_FIELDS, fetcher);
}

export function fetchReferenceDepartments(fetcher: Fetcher = apiFetch): Promise<Department[]> {
  return fetchList<Department>('/api/v1/departments', 'departments', DEPARTMENT_FIELDS, fetcher);
}
