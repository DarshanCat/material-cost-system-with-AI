import { afterEach, beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';

const storageMap = new Map<string, string>();

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
    location: { assign: () => undefined },
  };
}

const client = await import('./client.ts');
const identity = await import('./identityAuth.ts');
const users = await import('./users.ts');

const originalFetch = globalThis.fetch;

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

interface Call {
  url: string;
  init?: RequestInit;
}

function stubFetch(handler: (call: Call) => Response | Promise<Response>): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const call = { url: String(url), init };
    calls.push(call);
    return handler(call);
  }) as typeof fetch;
  return calls;
}

const SIGN_IN_OK = { idToken: 'id-1', refreshToken: 'refresh-1', expiresIn: '3600' };

describe('identity provider: error messages', () => {
  it('maps Google error codes to plain language', () => {
    assert.match(identity.mapIdentityError('INVALID_LOGIN_CREDENTIALS'), /not correct/);
    assert.match(identity.mapIdentityError('USER_DISABLED'), /disabled/);
    assert.match(identity.mapIdentityError('TOO_MANY_ATTEMPTS_TRY_LATER'), /Too many attempts/);
    assert.match(identity.mapIdentityError('WEAK_PASSWORD : Password should be at least 6 characters'), /too weak/);
    assert.match(identity.mapIdentityError('CREDENTIAL_TOO_OLD_LOGIN_AGAIN'), /sign in again/i);
    assert.match(identity.mapIdentityError('SOMETHING_NEW'), /Sign-in failed/);
    assert.match(identity.mapIdentityError(undefined), /Sign-in failed/);
  });

  it('never reveals which of e-mail or password was wrong', () => {
    const a = identity.mapIdentityError('EMAIL_NOT_FOUND');
    const b = identity.mapIdentityError('INVALID_PASSWORD');
    const c = identity.mapIdentityError('INVALID_LOGIN_CREDENTIALS');
    assert.equal(a, b);
    assert.equal(b, c);
  });
});

describe('identity provider: sign-in, renewal and password change', () => {
  beforeEach(() => {
    storageMap.clear();
    client.setAccessToken(null);
    client.clearApiCache();
    identity.clearIdentitySession();
    identity.configureIdentity('test-api-key');
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    identity.configureIdentity('');
    identity.clearIdentitySession();
  });

  it('signs in with e-mail and password and stores the id token', async () => {
    const calls = stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('  ravi.s@example.com ', 'secret-password');
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /identitytoolkit\.googleapis\.com\/v1\/accounts:signInWithPassword\?key=test-api-key$/);
    const sent = JSON.parse(String(calls[0].init?.body));
    assert.deepEqual(sent, { email: 'ravi.s@example.com', password: 'secret-password', returnSecureToken: true });
    assert.equal(client.getAccessToken(), 'id-1');
    assert.equal(storageMap.get('vspl.refreshToken'), 'refresh-1');
  });

  it('reports a wrong password in friendly words and stores nothing', async () => {
    stubFetch(() => jsonRes({ error: { code: 400, message: 'INVALID_LOGIN_CREDENTIALS' } }, 400));
    await assert.rejects(() => identity.signInWithPassword('a@b.com', 'wrong'), /not correct/);
    assert.equal(client.getAccessToken(), null);
    assert.equal(storageMap.size, 0);
  });

  it('reports an unreachable sign-in service', async () => {
    globalThis.fetch = (async () => {
      throw new Error('network down');
    }) as typeof fetch;
    await assert.rejects(() => identity.signInWithPassword('a@b.com', 'x'), /Cannot reach the sign-in service/);
  });

  it('refuses to sign in when the web API key is not configured', async () => {
    identity.configureIdentity('');
    const calls = stubFetch(() => jsonRes(SIGN_IN_OK));
    await assert.rejects(() => identity.signInWithPassword('a@b.com', 'x'), /not configured/);
    assert.equal(calls.length, 0);
  });

  it('renews the id token with the refresh token', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    const calls = stubFetch(() => jsonRes({ id_token: 'id-2', refresh_token: 'refresh-2', expires_in: '3600' }));
    await identity.refreshIdToken();
    assert.match(calls[0].url, /securetoken\.googleapis\.com\/v1\/token\?key=test-api-key$/);
    const form = new URLSearchParams(String(calls[0].init?.body));
    assert.equal(form.get('grant_type'), 'refresh_token');
    assert.equal(form.get('refresh_token'), 'refresh-1');
    assert.equal(client.getAccessToken(), 'id-2');
    assert.equal(storageMap.get('vspl.refreshToken'), 'refresh-2');
  });

  it('shares one renewal request between simultaneous callers', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    const calls = stubFetch(() => jsonRes({ id_token: 'id-3', refresh_token: 'refresh-3', expires_in: '3600' }));
    await Promise.all([identity.refreshIdToken(), identity.refreshIdToken(), identity.refreshIdToken()]);
    assert.equal(calls.length, 1);
  });

  it('ends the session when the refresh token is refused', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    stubFetch(() => jsonRes({ error: { message: 'TOKEN_EXPIRED' } }, 400));
    await assert.rejects(() => identity.refreshIdToken(), /expired/);
    assert.equal(client.getAccessToken(), null);
    assert.equal(storageMap.has('vspl.refreshToken'), false);
  });

  it('keeps the session when renewal fails only because the network is down', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    globalThis.fetch = (async () => {
      throw new Error('offline');
    }) as typeof fetch;
    await assert.rejects(() => identity.refreshIdToken());
    assert.equal(client.getAccessToken(), 'id-1');
  });

  it('ensureFreshToken renews only when the token is within five minutes of expiry', async () => {
    stubFetch(() => jsonRes({ ...SIGN_IN_OK, expiresIn: '3600' }));
    await identity.signInWithPassword('a@b.com', 'pw');
    let calls = stubFetch(() => jsonRes({ id_token: 'id-4', refresh_token: 'refresh-4', expires_in: '3600' }));
    await identity.ensureFreshToken();
    assert.equal(calls.length, 0, 'a fresh token is left alone');

    stubFetch(() => jsonRes({ ...SIGN_IN_OK, expiresIn: '120' }));
    await identity.signInWithPassword('a@b.com', 'pw');
    calls = stubFetch(() => jsonRes({ id_token: 'id-5', refresh_token: 'refresh-5', expires_in: '3600' }));
    await identity.ensureFreshToken();
    assert.equal(calls.length, 1, 'a token with two minutes left is renewed');
    assert.equal(client.getAccessToken(), 'id-5');
  });

  it('does not bring a signed-out session back to life', async () => {
    stubFetch(() => jsonRes({ ...SIGN_IN_OK, expiresIn: '60' }));
    await identity.signInWithPassword('a@b.com', 'pw');
    client.setAccessToken(null);
    const calls = stubFetch(() => jsonRes({ id_token: 'x', refresh_token: 'y', expires_in: '3600' }));
    await identity.ensureFreshToken();
    assert.equal(calls.length, 0);
    assert.equal(client.getAccessToken(), null);
  });

  it('apiFetch renews a nearly expired token before sending the request', async () => {
    stubFetch(() => jsonRes({ ...SIGN_IN_OK, expiresIn: '60' }));
    await identity.signInWithPassword('a@b.com', 'pw');
    const seen: string[] = [];
    stubFetch(({ url, init }) => {
      if (url.includes('securetoken')) return jsonRes({ id_token: 'id-renewed', refresh_token: 'r', expires_in: '3600' });
      seen.push(new Headers(init?.headers).get('Authorization') ?? '');
      return jsonRes({ ok: true });
    });
    await client.apiFetch('/api/v1/users');
    assert.deepEqual(seen, ['Bearer id-renewed']);
  });

  it('changes the password with the current id token and keeps the new session', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'temp-pass');
    const calls = stubFetch(() => jsonRes({ idToken: 'id-new', refreshToken: 'refresh-new', expiresIn: '3600' }));
    await identity.changePassword('a-much-better-password');
    assert.match(calls[0].url, /accounts:update\?key=test-api-key$/);
    assert.deepEqual(JSON.parse(String(calls[0].init?.body)), {
      idToken: 'id-1',
      password: 'a-much-better-password',
      returnSecureToken: true,
    });
    assert.equal(client.getAccessToken(), 'id-new');
  });

  it('maps a weak-password refusal and an old login when changing the password', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'temp-pass');
    stubFetch(() => jsonRes({ error: { message: 'WEAK_PASSWORD : Password should be at least 6 characters' } }, 400));
    await assert.rejects(() => identity.changePassword('abc'), /too weak/);
    stubFetch(() => jsonRes({ error: { message: 'CREDENTIAL_TOO_OLD_LOGIN_AGAIN' } }, 400));
    await assert.rejects(() => identity.changePassword('a-much-better-password'), /sign in again/i);
  });

  it('confirms the change to the backend and surfaces a 409', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    const calls = stubFetch(() => jsonRes({ ok: true }));
    await identity.confirmPasswordChanged();
    assert.equal(calls[0].url, '/api/v1/auth/password-changed');
    assert.equal(calls[0].init?.method, 'POST');
    stubFetch(() => jsonRes({ detail: 'Password has not been changed yet.' }, 409));
    await assert.rejects(() => identity.confirmPasswordChanged(), /not been changed/);
  });

  it('reads the profile of a pending user without a role', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    stubFetch(() =>
      jsonRes({ user_id: 'a@b.com', role: null, department: '', status: 'pending', must_change_password: false, display_name: 'A' }),
    );
    const profile = await identity.fetchIdentityProfile();
    assert.equal(profile?.status, 'pending');
    assert.equal(profile?.role, null);
  });

  it('treats an unknown status as disabled, never as active', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    stubFetch(() => jsonRes({ user_id: 'a@b.com', role: 'Admin', department: 'Admin', status: 'weird', must_change_password: false }));
    assert.equal((await identity.fetchIdentityProfile())?.status, 'disabled');
  });

  it('returns no profile when signed out or when the token is refused', async () => {
    const calls = stubFetch(() => jsonRes({}));
    assert.equal(await identity.fetchIdentityProfile(), null);
    assert.equal(calls.length, 0);
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    stubFetch(() => jsonRes({ detail: 'Authentication required' }, 401));
    assert.equal(await identity.fetchIdentityProfile(), null);
  });

  it('sign-out forgets the whole session', async () => {
    stubFetch(() => jsonRes(SIGN_IN_OK));
    await identity.signInWithPassword('a@b.com', 'pw');
    stubFetch(() => jsonRes({ revoked: false, message: 'ok' }));
    await identity.signOutIdentity();
    assert.equal(client.getAccessToken(), null);
    assert.equal(storageMap.has('vspl.refreshToken'), false);
    assert.equal(storageMap.has('vspl.tokenExpiry'), false);
  });
});

describe('new-password rules', () => {
  it('requires ten characters, a matching confirmation and a different password', () => {
    assert.match(identity.validateNewPassword('short', 'short') ?? '', /at least 10/);
    assert.match(identity.validateNewPassword('long-enough-1', 'long-enough-2') ?? '', /do not match/);
    assert.match(identity.validateNewPassword('same-as-temp-1', 'same-as-temp-1', 'same-as-temp-1') ?? '', /different/);
    assert.equal(identity.validateNewPassword('long-enough-1', 'long-enough-1', 'temp'), null);
  });
});

describe('user-management API client', () => {
  beforeEach(() => {
    storageMap.clear();
    client.setAccessToken('id-admin');
    client.clearApiCache();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    client.setAccessToken(null);
  });

  it('lists users, optionally by status', async () => {
    const calls = stubFetch(() => jsonRes({ items: [], total: 0 }));
    await users.listUsers();
    await users.listUsers('pending');
    assert.equal(calls[0].url, '/api/v1/users');
    assert.equal(calls[1].url, '/api/v1/users?status=pending');
    assert.equal(new Headers(calls[0].init?.headers).get('Authorization'), 'Bearer id-admin');
  });

  it('creates a user without sending empty optional fields and returns the one-time password', async () => {
    const calls = stubFetch(() =>
      jsonRes({ user: { id: 7, email: 'ravi.s@example.com' }, temporary_password: 'Temp-Pass-1' }, 201),
    );
    const result = await users.createUser({ email: ' ravi.s@example.com ', display_name: 'Ravi S', role: 'Stores', department: '  ' });
    assert.equal(result.temporary_password, 'Temp-Pass-1');
    assert.equal(calls[0].init?.method, 'POST');
    assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { email: 'ravi.s@example.com', display_name: 'Ravi S', role: 'Stores' });
  });

  it('calls the approve, reject, update, disable, enable and reset endpoints', async () => {
    const calls = stubFetch(() => jsonRes({ user: { id: 3 }, temporary_password: 'x' }));
    await users.approveUser(3, 'Foundry', 'Foundry');
    await users.rejectUser(3);
    await users.updateUser(3, { role: 'Management' });
    await users.disableUser(3);
    await users.enableUser(3);
    await users.resetUserPassword(3);
    assert.deepEqual(
      calls.map((c) => `${c.init?.method} ${c.url}`),
      [
        'POST /api/v1/users/3/approve',
        'POST /api/v1/users/3/reject',
        'PATCH /api/v1/users/3',
        'POST /api/v1/users/3/disable',
        'POST /api/v1/users/3/enable',
        'POST /api/v1/users/3/reset-password',
      ],
    );
    assert.deepEqual(JSON.parse(String(calls[0].init?.body)), { role: 'Foundry', department: 'Foundry' });
    assert.deepEqual(JSON.parse(String(calls[2].init?.body)), { role: 'Management' });
  });

  it('reads the audit log', async () => {
    const calls = stubFetch(() => jsonRes({ items: [] }));
    await users.listUserAuditLog(25);
    assert.equal(calls[0].url, '/api/v1/users/audit-log?limit=25');
  });

  it('surfaces the server message when an action is refused', async () => {
    stubFetch(() => jsonRes({ detail: 'You cannot disable your own account.' }, 409));
    await assert.rejects(() => users.disableUser(1), /cannot disable your own account/);
    stubFetch(() => jsonRes({ detail: 'Access denied' }, 403));
    await assert.rejects(() => users.listUsers(), /Access denied/);
  });
});
