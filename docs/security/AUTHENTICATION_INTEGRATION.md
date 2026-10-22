# Authentication & Authorization — Sprint 1 status and integration guide

Scope: backlog SW-01, SW-02, TST-01 (and the authentication contract of SW-03). Date: 2026-10-22.

## 1. What changed

* **Identity** is established only by a server-verified `Authorization: Bearer <token>` credential, checked by the configured `AuthProvider` (`backend/app/core/auth.py`). `X-User-*` headers, query parameters (`created_by`, `actor_id`) and body fields (`approver_id`, `created_by`) no longer establish who the caller is.
* **Fail closed.** Default `AUTH_PROVIDER=none` authenticates nobody, so every protected route returns **401**. Unknown provider names, a missing/invalid/expired/tampered token, a wrong scheme, and a token whose role is not one of the five known roles all return 401. A role is never defaulted (the old "fall back to Stores" is removed).
* **Authorization.** Every route except `GET /api/v1/health`, `GET /api/v1/auth/status` and the dev-only `POST /api/v1/auth/dev-login` now depends on `require_permission(...)` (403 when the role lacks the permission). The ad-hoc role-string checks in heats, heat import, reconciliation and aliases were replaced by the permission matrix with the same role sets.
* **Actor attribution** (`created_by`, `actor_id`, `posted_by`, `reviewer_id`, `approver_id`) is taken from the verified user. `?actor_id=`/`?created_by=` query parameters were removed; a client-supplied `approver_id` / `created_by` in a body is overwritten.
* **Startup guard.** With `ENVIRONMENT=production` the app refuses to start if `AUTH_PROVIDER=dev` or `SECRET_KEY` is the default.
* **Frontend.** All 72 `fetch()` calls go through `frontend/src/api/client.ts` (`apiFetch`), which attaches only the bearer token and signals 401s to the shell. No identity headers are sent. The role dropdown is a *development sign-in request* shown only when the backend reports `login_available`; with no provider the UI shows "Not signed in" and locks protected modules.
* **Latent defects found and fixed on the way:** `GET /reconciliation/runs` always raised `NameError` (`func` not imported, `reconciliation_service.py`); the Costing Dashboard called two URLs that do not exist (`/costing/valuation`, `/costing/items/{id}/rate-history`), now `/costing/valuation/historical` and `/costing/rates/history/{id}`.

## 2. PROVISIONAL role matrix (needs Plant Head / Management sign-off)

The repository defined no approval/reversal roles except Rule L8 (physical-audit approval by Management or Admin) and Rule L5 ("authorized supervisor" reversals). Defaults chosen, least-privilege, Admin holds everything:

| Action | Roles |
|---|---|
| Create/submit/cancel GRN, issue, waste; excel import; create physical audit | Stores (+Admin) |
| Approve GRN, issue, waste; approve physical audit; reverse ledger entry | Management, Admin |
| Post opening balances (and preview/template) | **Admin only** |
| Read GRN/issue/waste/ledger | per existing read permissions (Stores, Foundry*, Purchase*, Management) |
| Create heats / import heat logs; run reconciliation, confirm/reject candidates | Foundry, Management, Admin (unchanged) |
| Resolve reconciliation exceptions; approve/reject aliases | Management, Admin (unchanged) |
| Reconciliation/heat reads | Foundry, Management, Admin, **Stores** (granted so Stores can see reconciliation of its own issues - confirm) |
| `/health/db-check` | Management, Admin (`audit:read`) |

Decisions needed: confirm or change this matrix; whether Management may post opening balances; whether single-person approval (no maker-checker, SW-04) is acceptable until SW-04 is built.

## 3. What is still required for REAL authentication (not decided, not implemented)

The IT Head must choose the mechanism. Everything else is ready: implement one class with `name` and `authenticate(request) -> AuthenticatedUser | None` in `backend/app/core/auth.py`, return it from `get_auth_provider()` for a new `AUTH_PROVIDER` value, and replace the `dev-login` branch in `frontend/src/api/client.ts`.

| Candidate | Needs from the organisation |
|---|---|
| Local JWT | Users table + password policy/hashing, token lifetime/refresh, secret management, user admin UI (SW-11) |
| Microsoft Entra ID | Tenant/app registration, client id, allowed audience/issuer, group-to-role mapping for the five roles, redirect URIs |
| Server session cookie | Session store, cookie flags/TLS, CSRF protection, logout/expiry rules |

Common requirements: HTTPS on the plant LAN (INF-03), a unique stable `user_id` per person, the role mapping, a deprovisioning process, and replacing `SECRET_KEY`. Database migration impact: **none** for this sprint (no schema change). A local-JWT choice would add a users table (new Alembic revision, not created).

## 4. Remaining gaps (not production ready)

* No production provider exists; `dev` tokens are not a production scheme. `AUTH_PROVIDER=dev` lets anyone who can reach the loopback interface choose any role.
* No maker-checker (SW-04), no document-reversal workflow (SW-07), no user/audit admin (SW-11).
* The Costing Dashboard's response *shapes* do not match backend schemas (e.g. `total_active_items` vs `total_items`, `current_weighted_average_rate` vs `weighted_average_rate`); only the auth and URL contract was fixed. Needs its own contract-alignment task.
* PostgreSQL behaviour is unverified; all tests run on in-memory SQLite.
* CORS allows credentials with `allow_headers=["*"]`; restrict origins/headers when deploying.
* Rate limiting, audit-log of denied attempts and token revocation are not implemented.

## 5. Test evidence

`backend/tests/test_security_routes.py` — route classification completeness (a new route fails the suite until classified), unauthenticated 401 and forged-header 401 for every protected route, invalid/expired/tampered/unknown-role/wrong-scheme/foreign-key tokens, the full route × role matrix (every route × five roles), rejected mutations leaving all table row counts and the GRN status unchanged, actor attribution (GRN, ledger reversal, opening balance, heats), fail-closed provider configuration, production startup guard, dev-login restrictions.
