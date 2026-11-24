import { afterEach, beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';

const storageMap = new Map<string, string>();
const dispatchedEvents: string[] = [];

if (typeof (globalThis as any).window === 'undefined') {
  (globalThis as any).window = {
    sessionStorage: {
      getItem: (k: string) => storageMap.get(k) ?? null,
      setItem: (k: string, v: string) => {
        storageMap.set(k, String(v));
      },
      removeItem: (k: string) => {
        storageMap.delete(k);
      },
    },
    dispatchEvent: (ev: Event) => {
      dispatchedEvents.push(ev.type);
      return true;
    },
  };
}

const clientMod = await import('./client.ts');
const {
  UNAUTHORIZED_EVENT,
  devLogin,
  fetchCurrentUser,
  getAccessToken,
  getAuthStatus,
  hasAccessToken,
  loginWithCredentials,
  setAccessToken,
  signOut,
} = clientMod;

const originalFetch = globalThis.fetch;

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Frontend Authentication Fail-Closed Regression Tests (Phase 2)', () => {
  beforeEach(() => {
    setAccessToken(null);
    storageMap.clear();
    dispatchedEvents.length = 0;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setAccessToken(null);
  });

  it('devLogin fails closed without synthetic user or token when backend is unavailable', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('Failed to fetch');
    }) as typeof fetch;

    await assert.rejects(() => devLogin('Stores'), /Failed to fetch/);
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });

  it('devLogin fails closed when backend returns HTTP 500', async () => {
    globalThis.fetch = (async () =>
      jsonRes({ detail: 'Internal Server Error' }, 500)) as typeof fetch;

    await assert.rejects(() => devLogin('Management'), /Internal Server Error/);
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });

  it('devLogin and loginWithCredentials reject malformed authentication responses', async () => {
    globalThis.fetch = (async () =>
      jsonRes({ token_type: 'bearer', user: { user_id: 'u1' } }, 200)) as typeof fetch;

    await assert.rejects(() => devLogin('Stores'), /Invalid authentication response/);
    assert.equal(getAccessToken(), null);

    await assert.rejects(
      () => loginWithCredentials('user@vspl.com', 'secret'),
      /Invalid authentication response/
    );
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });

  it('loginWithCredentials fails closed on HTTP 501 (not configured)', async () => {
    globalThis.fetch = (async () =>
      jsonRes({ detail: 'Credential-based login is not configured on this backend.' }, 501)) as typeof fetch;

    await assert.rejects(
      () => loginWithCredentials('stores@vspl.com', 'pass123'),
      /not configured/i
    );
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });

  it('loginWithCredentials rejects invalid credentials with HTTP 401 and clears any token', async () => {
    setAccessToken('stale-token');
    globalThis.fetch = (async () =>
      jsonRes({ detail: 'Invalid username or password' }, 401)) as typeof fetch;

    await assert.rejects(
      () => loginWithCredentials('stores@vspl.com', 'wrong'),
      /Invalid username or password/
    );
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
    assert.ok(dispatchedEvents.includes(UNAUTHORIZED_EVENT));
  });

  it('loginWithCredentials handles network failures without creating a synthetic session', async () => {
    globalThis.fetch = (async () => {
      throw new Error('Network unreachable');
    }) as typeof fetch;

    await assert.rejects(
      () => loginWithCredentials('stores@vspl.com', 'pass123'),
      /Network unreachable/
    );
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });

  it('getAuthStatus falls back safely to none and fetchCurrentUser returns null on expired/invalid tokens', async () => {
    globalThis.fetch = (async () => {
      throw new Error('Connection refused');
    }) as typeof fetch;

    const status = await getAuthStatus();
    assert.deepEqual(status, { provider: 'none', login_available: false });

    setAccessToken('expired-or-revoked-token');
    globalThis.fetch = (async () =>
      jsonRes({ detail: 'Invalid or expired bearer token' }, 401)) as typeof fetch;

    const user = await fetchCurrentUser();
    assert.equal(user, null);
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
    assert.ok(dispatchedEvents.includes(UNAUTHORIZED_EVENT));
  });

  it('signOut sends bearer token to /api/v1/auth/logout and clears local token even when logout fails', async () => {
    const calls: Array<{ url: string; method?: string; auth?: string | null }> = [];
    setAccessToken('dev1.active.token');

    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      calls.push({
        url: String(input),
        method: init?.method,
        auth: headers.get('Authorization'),
      });
      throw new Error('Server offline during logout');
    }) as typeof fetch;

    await signOut();

    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/api/v1/auth/logout');
    assert.equal(calls[0].method, 'POST');
    assert.equal(calls[0].auth, 'Bearer dev1.active.token');
    assert.equal(getAccessToken(), null);
    assert.equal(hasAccessToken(), false);
  });
});
