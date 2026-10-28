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

/** fetch() wrapper that attaches the bearer credential and falls back to demo data if the server is unreachable. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  try {
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401 && accessToken) {
      setAccessToken(null);
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    const contentType = response.headers.get('content-type') || '';
    // If backend responded with HTML (e.g. Vercel SPA routing returning index.html) or error status (e.g. 404, 405 on static POST, 5xx), use mock fallback:
    if (contentType.includes('text/html') || response.status === 404 || response.status === 405 || response.status >= 500) {
      const mockRes = handleMockRequest(input, init);
      if (mockRes) return mockRes;
    }
    return response;
  } catch (err) {
    // If network fetch failed entirely (e.g. backend offline / cloud static deployment)
    const mockRes = handleMockRequest(input, init);
    if (mockRes) return mockRes;
    throw err;
  }
}

export async function getAuthStatus(): Promise<AuthStatus> {
  try {
    const res = await apiFetch('/api/v1/auth/status');
    if (res.ok) return res.json();
  } catch {}
  return { provider: 'dev', login_available: true };
}

/** Returns the verified identity for the stored credential, or default demo admin user. */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    const res = await apiFetch('/api/v1/auth/me');
    if (res.ok) return res.json();
  } catch {}
  return { user_id: 'usr_admin_01', role: 'Admin', department: 'Admin' };
}

/**
 * Development / Demo sign-in: maps role to server account or demo mock user.
 */
export async function devLogin(role: UserRole): Promise<AuthUser> {
  try {
    const res = await apiFetch('/api/v1/auth/dev-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    if (res.ok) {
      const data = await res.json();
      setAccessToken(data.access_token);
      return data.user as AuthUser;
    }
  } catch {}
  const mockUser: AuthUser = { user_id: `usr_${role.toLowerCase()}_01`, role, department: role };
  setAccessToken('demo_token_' + Date.now());
  return mockUser;
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
