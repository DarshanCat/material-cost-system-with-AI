import { afterEach, beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';

const storageMap = new Map<string, string>();
const assigned: string[] = [];

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
    dispatchEvent: () => true,
    location: {
      assign: (url: string) => {
        assigned.push(url);
      },
    },
  };
}

const { clearApiCache, fetchCurrentUser, getAuthProvider, getAuthStatus, getAccessToken, hasAccessToken, setAccessToken, signOut } =
  await import('./client.ts');

const originalFetch = globalThis.fetch;

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function stubStatus(provider: string) {
  globalThis.fetch = (async () => jsonRes({ provider, login_available: provider === 'dev' })) as typeof fetch;
}

describe('Google Identity-Aware Proxy sign-in (frontend)', () => {
  beforeEach(() => {
    setAccessToken(null);
    clearApiCache();
    storageMap.clear();
    assigned.length = 0;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setAccessToken(null);
  });

  it('remembers the provider reported by the backend and falls back to none on failure', async () => {
    stubStatus('iap');
    assert.equal((await getAuthStatus()).provider, 'iap');
    assert.equal(getAuthProvider(), 'iap');
    clearApiCache();
    globalThis.fetch = (async () => {
      throw new Error('network down');
    }) as typeof fetch;
    assert.equal((await getAuthStatus()).provider, 'none');
    assert.equal(getAuthProvider(), 'none');
  });

  it('without a token the identity is not requested unless the proxy supplies it', async () => {
    let calls = 0;
    globalThis.fetch = (async () => {
      calls += 1;
      return jsonRes({ user_id: 'x', role: 'Admin', department: 'Admin' });
    }) as typeof fetch;
    assert.equal(await fetchCurrentUser(), null);
    assert.equal(calls, 0);
  });

  it('proxy identity is read from the backend without a bearer token', async () => {
    let authorization: string | null = 'unset';
    globalThis.fetch = (async (_url: string, init?: RequestInit) => {
      authorization = new Headers(init?.headers).get('Authorization');
      return jsonRes({ user_id: 'stores.user@example.com', role: 'Stores', department: 'General/Stores' });
    }) as typeof fetch;
    const user = await fetchCurrentUser({ withoutToken: true });
    assert.equal(user?.role, 'Stores');
    assert.equal(authorization, null);
    assert.equal(hasAccessToken(), false);
  });

  it('an unauthenticated or unmapped proxy user never becomes a synthetic identity', async () => {
    globalThis.fetch = (async () => jsonRes({ detail: 'Authentication required' }, 401)) as typeof fetch;
    assert.equal(await fetchCurrentUser({ withoutToken: true }), null);
    assert.equal(getAccessToken(), null);
    globalThis.fetch = (async () => {
      throw new Error('network down');
    }) as typeof fetch;
    assert.equal(await fetchCurrentUser({ withoutToken: true }), null);
  });

  it('signing out in proxy mode ends the Google session through the proxy', async () => {
    stubStatus('iap');
    await getAuthStatus();
    await signOut();
    assert.deepEqual(assigned, ['/_gcp_iap/clear_login_cookie']);
  });

  it('signing out with any other provider does not navigate away', async () => {
    stubStatus('dev');
    clearApiCache();
    await getAuthStatus();
    setAccessToken('some-token');
    await signOut();
    assert.deepEqual(assigned, []);
    assert.equal(getAccessToken(), null);
  });
});
