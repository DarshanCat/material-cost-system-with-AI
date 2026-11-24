"""
Google Identity Platform provider (AUTH_PROVIDER=identity): token verification, the user record as the authority,
admin approval, admin-created users with temporary passwords, forced password change, disable/enable.
"""

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.core.auth as auth_module
from app.core.config import settings
from app.core.identity_auth import IdentityAdminError, IdentityProvider, get_identity_admin
from app.main import app as fastapi_app
from app.models.app_user import AppUser, AppUserAuditLog

PROJECT = "vspl-mms-test"
KID = "kid-1"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public_pem(key) -> str:
    return key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def _token(key, *, email, uid="uid-1", aud=PROJECT, iss=None, exp_delta=600, kid=KID, alg="RS256", extra=None):
    now = int(time.time())
    claims = {
        "iss": iss or f"https://securetoken.google.com/{PROJECT}",
        "aud": aud,
        "iat": now,
        "auth_time": now,
        "exp": now + exp_delta,
        "sub": uid,
        "email": email,
        "firebase": {"sign_in_provider": "password"},
    }
    claims.update(extra or {})
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


class FakeAdmin:
    def __init__(self):
        self.created = []
        self.password_set = []
        self.disabled = []
        self.password_updated = None
        self.fail_create = False
        self.fail_disable = False
        self._n = 0

    def create_user(self, email, password, display_name):
        if self.fail_create:
            raise IdentityAdminError("A sign-in account with this e-mail already exists.")
        self._n += 1
        self.created.append((email, password))
        return f"uid-new-{self._n}"

    def set_password(self, uid, password):
        self.password_set.append((uid, password))

    def set_disabled(self, uid, disabled):
        if self.fail_disable:
            raise IdentityAdminError("down")
        self.disabled.append((uid, disabled))

    def password_updated_at(self, uid):
        return self.password_updated

    def delete_user(self, uid):
        pass


@pytest.fixture
def ctx(anon_client: TestClient, db_session, rsa_key, monkeypatch):
    provider = IdentityProvider(PROJECT, lambda: db_session, key_loader=lambda: {KID: _public_pem(rsa_key)})
    admin = FakeAdmin()
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "identity")
    monkeypatch.setattr(settings, "IDENTITY_PROJECT_ID", PROJECT)
    monkeypatch.setattr(settings, "IDENTITY_API_KEY", "public-web-key")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAILS", "boss@example.com")
    monkeypatch.setattr(auth_module, "_build_identity_provider", lambda: provider)
    fastapi_app.dependency_overrides[get_identity_admin] = lambda: admin

    class Ctx:
        client = anon_client
        db = db_session
        key = rsa_key
        fake = admin

        @staticmethod
        def headers(email, uid="uid-1", **kw):
            return {"Authorization": f"Bearer {_token(rsa_key, email=email, uid=uid, **kw)}"}

        @staticmethod
        def make_user(email, role, uid=None, status="active", must_change=False, temp_set=None, source="password"):
            user = AppUser(
                email=email, role=role, department="", status=status, auth_uid=uid or f"uid-{email}",
                auth_source=source, must_change_password=must_change, temp_password_set_at=temp_set,
            )
            db_session.add(user)
            db_session.commit()
            return user

    yield Ctx
    fastapi_app.dependency_overrides.pop(get_identity_admin, None)


def _me(c, headers=None):
    return c.client.get("/api/v1/auth/me", headers=headers or {})


# --- token verification -------------------------------------------------------------------------------

def test_status_gives_the_browser_the_public_key_and_nothing_secret(ctx):
    body = ctx.client.get("/api/v1/auth/status").json()
    assert body == {"provider": "identity", "login_available": True, "identity_api_key": "public-web-key", "microsoft_enabled": False}


def test_active_user_is_authenticated_with_role(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    res = _me(ctx, ctx.headers("store@example.com"))
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "Stores" and body["status"] == "active" and body["must_change_password"] is False
    assert ctx.client.get("/api/v1/departments", headers=ctx.headers("store@example.com")).status_code == 200


def test_role_is_enforced_for_business_routes(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    assert ctx.client.get("/api/v1/users", headers=ctx.headers("store@example.com")).status_code == 403


@pytest.mark.parametrize(
    "kwargs",
    [
        {"aud": "another-project"},
        {"iss": "https://securetoken.google.com/another-project"},
        {"exp_delta": -600},
        {"kid": "unknown-kid"},
    ],
)
def test_invalid_tokens_are_rejected(ctx, kwargs):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    assert _me(ctx, ctx.headers("store@example.com", **kwargs)).status_code == 401


def test_token_signed_by_another_key_is_rejected(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    headers = {"Authorization": f"Bearer {_token(other, email='store@example.com')}"}
    assert _me(ctx, headers).status_code == 401


def test_tampered_none_and_hs256_tokens_are_rejected(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    good = _token(ctx.key, email="store@example.com")
    head, payload, sig = good.split(".")
    assert _me(ctx, {"Authorization": f"Bearer {head}.{payload[:-2]}AA.{sig}"}).status_code == 401
    none_token = jwt.encode({"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "uid-1", "email": "store@example.com",
                             "exp": int(time.time()) + 600, "iat": int(time.time())}, key="", algorithm="none", headers={"kid": KID})
    assert _me(ctx, {"Authorization": f"Bearer {none_token}"}).status_code == 401
    hs = jwt.encode({"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "uid-1", "email": "store@example.com",
                     "exp": int(time.time()) + 600, "iat": int(time.time())}, key="a-shared-secret-of-sufficient-length-0123456789", algorithm="HS256", headers={"kid": KID})
    assert _me(ctx, {"Authorization": f"Bearer {hs}"}).status_code == 401


def test_no_token_and_garbage_are_401(ctx):
    assert _me(ctx).status_code == 401
    assert _me(ctx, {"Authorization": "Bearer not-a-token"}).status_code == 401
    assert ctx.client.get("/api/v1/departments").status_code == 401


def test_a_different_sign_in_account_for_a_known_email_is_refused(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-original")
    assert _me(ctx, ctx.headers("store@example.com", uid="uid-impostor")).status_code == 401


# --- approval ------------------------------------------------------------------------------------------

def test_unknown_person_is_pending_with_no_access_until_approved(ctx):
    res = _me(ctx, ctx.headers("new.person@example.com", uid="uid-new"))
    assert res.status_code == 200
    assert res.json()["status"] == "pending" and res.json()["role"] is None
    assert ctx.client.get("/api/v1/departments", headers=ctx.headers("new.person@example.com", uid="uid-new")).status_code == 401

    ctx.make_user("boss@example.com", "Admin", uid="uid-boss")
    boss = ctx.headers("boss@example.com", uid="uid-boss")
    pending = ctx.client.get("/api/v1/users?status=pending", headers=boss).json()
    assert [u["email"] for u in pending["items"]] == ["new.person@example.com"]
    uid = pending["items"][0]["id"]

    bad = ctx.client.post(f"/api/v1/users/{uid}/approve", json={"role": "Superuser"}, headers=boss)
    assert bad.status_code == 422
    ok = ctx.client.post(f"/api/v1/users/{uid}/approve", json={"role": "Purchase"}, headers=boss)
    assert ok.status_code == 200 and ok.json()["role"] == "Purchase" and ok.json()["status"] == "active"
    assert ctx.client.get("/api/v1/departments", headers=ctx.headers("new.person@example.com", uid="uid-new")).status_code == 200
    actions = [a.action for a in ctx.db.execute(select(AppUserAuditLog)).scalars()]
    assert "first_sign_in_pending" in actions and "approved" in actions


def test_rejected_person_stays_out(ctx):
    _me(ctx, ctx.headers("new.person@example.com", uid="uid-new"))
    ctx.make_user("boss@example.com", "Admin", uid="uid-boss")
    boss = ctx.headers("boss@example.com", uid="uid-boss")
    uid = ctx.client.get("/api/v1/users?status=pending", headers=boss).json()["items"][0]["id"]
    assert ctx.client.post(f"/api/v1/users/{uid}/reject", json={"reason": "not staff"}, headers=boss).status_code == 200
    assert _me(ctx, ctx.headers("new.person@example.com", uid="uid-new")).json()["status"] == "rejected"
    assert ctx.client.get("/api/v1/departments", headers=ctx.headers("new.person@example.com", uid="uid-new")).status_code == 401


def test_bootstrap_list_creates_the_first_admin_who_must_set_their_own_password(ctx):
    h = ctx.headers("boss@example.com", uid="uid-boss")
    res = _me(ctx, h)
    assert res.json()["role"] == "Admin" and res.json()["status"] == "active" and res.json()["must_change_password"] is True
    assert ctx.client.get("/api/v1/users", headers=h).status_code == 401  # blocked until the password is replaced
    ctx.fake.password_updated = datetime.now(timezone.utc) + timedelta(seconds=5)
    assert ctx.client.post("/api/v1/auth/password-changed", headers=h).json() == {"ok": True}
    assert ctx.client.get("/api/v1/users", headers=h).status_code == 200


def test_bootstrap_list_does_not_apply_to_other_emails(ctx):
    assert _me(ctx, ctx.headers("someone@example.com", uid="uid-x")).json()["status"] == "pending"


def test_non_admin_cannot_approve_or_list(ctx):
    ctx.make_user("store@example.com", "Stores", uid="uid-1")
    h = ctx.headers("store@example.com")
    assert ctx.client.get("/api/v1/users", headers=h).status_code == 403
    assert ctx.client.post("/api/v1/users/1/approve", json={"role": "Admin"}, headers=h).status_code == 403


# --- admin-created users + forced password change ---------------------------------------------------

def _boss(ctx):
    ctx.make_user("boss@example.com", "Admin", uid="uid-boss")
    return ctx.headers("boss@example.com", uid="uid-boss")


def test_admin_creates_user_with_temporary_password_shown_once(ctx):
    boss = _boss(ctx)
    res = ctx.client.post("/api/v1/users", json={"email": "Ravi.S@Example.com", "display_name": "Ravi S", "role": "Stores"}, headers=boss)
    assert res.status_code == 201
    body = res.json()
    pw = body["temporary_password"]
    assert len(pw) >= 14 and body["user"]["email"] == "ravi.s@example.com" and body["user"]["must_change_password"] is True
    assert ctx.fake.created == [("ravi.s@example.com", pw)]
    # never stored, never listed, never audited
    listing = ctx.client.get("/api/v1/users", headers=boss)
    assert pw not in listing.text and "password" not in {k for u in listing.json()["items"] for k in u if k != "must_change_password"}
    assert all(pw not in a.detail for a in ctx.db.execute(select(AppUserAuditLog)).scalars())
    assert res.headers.get("cache-control", "").startswith("no-store")


def test_created_user_is_blocked_until_the_password_is_really_changed(ctx):
    boss = _boss(ctx)
    created = ctx.client.post("/api/v1/users", json={"email": "ravi@example.com", "display_name": "R", "role": "Stores"}, headers=boss).json()
    uid = ctx.fake.created and "uid-new-1"
    h = ctx.headers("ravi@example.com", uid=uid)
    me = _me(ctx, h).json()
    assert me["must_change_password"] is True and me["role"] == "Stores"
    assert ctx.client.get("/api/v1/departments", headers=h).status_code == 401  # blocked until the change

    ctx.fake.password_updated = None
    assert ctx.client.post("/api/v1/auth/password-changed", headers=h).status_code == 409
    row = ctx.db.get(AppUser, created["user"]["id"])
    ctx.fake.password_updated = row.temp_password_set_at.replace(tzinfo=timezone.utc) - timedelta(seconds=5)  # still the old password
    assert ctx.client.post("/api/v1/auth/password-changed", headers=h).status_code == 409
    ctx.fake.password_updated = datetime.now(timezone.utc) + timedelta(seconds=5)  # a later change
    assert ctx.client.post("/api/v1/auth/password-changed", headers=h).json() == {"ok": True}
    assert ctx.client.get("/api/v1/departments", headers=h).status_code == 200


def test_duplicate_email_invalid_role_and_service_failure(ctx):
    boss = _boss(ctx)
    base = {"email": "dup@example.com", "display_name": "D", "role": "Stores"}
    assert ctx.client.post("/api/v1/users", json={**base, "role": "Wizard"}, headers=boss).status_code == 422
    assert ctx.client.post("/api/v1/users", json={**base, "email": "not-an-email"}, headers=boss).status_code == 422
    assert ctx.client.post("/api/v1/users", json=base, headers=boss).status_code == 201
    assert ctx.client.post("/api/v1/users", json=base, headers=boss).status_code == 409
    ctx.fake.fail_create = True
    failed = ctx.client.post("/api/v1/users", json={**base, "email": "other@example.com"}, headers=boss)
    assert failed.status_code == 502
    assert ctx.db.execute(select(AppUser).where(AppUser.email == "other@example.com")).first() is None


def test_creating_a_user_requires_admin(ctx):
    ctx.make_user("mgmt@example.com", "Management", uid="uid-m")
    res = ctx.client.post("/api/v1/users", json={"email": "x@example.com", "role": "Stores"}, headers=ctx.headers("mgmt@example.com", uid="uid-m"))
    assert res.status_code == 403


def test_reset_password_blocks_until_changed(ctx):
    boss = _boss(ctx)
    user = ctx.make_user("ravi@example.com", "Stores", uid="uid-r")
    res = ctx.client.post(f"/api/v1/users/{user.id}/reset-password", headers=boss)
    assert res.status_code == 200 and res.json()["temporary_password"]
    assert ctx.fake.password_set[0][0] == "uid-r"
    assert ctx.client.get("/api/v1/departments", headers=ctx.headers("ravi@example.com", uid="uid-r")).status_code == 401


# --- role change, disable, enable -----------------------------------------------------------------

def test_change_role_takes_effect_and_is_audited(ctx):
    boss = _boss(ctx)
    user = ctx.make_user("store@example.com", "Stores", uid="uid-1")
    h = ctx.headers("store@example.com")
    assert ctx.client.get("/api/v1/users", headers=h).status_code == 403
    res = ctx.client.patch(f"/api/v1/users/{user.id}", json={"role": "Admin"}, headers=boss)
    assert res.status_code == 200 and res.json()["role"] == "Admin"
    assert ctx.client.get("/api/v1/users", headers=h).status_code == 200
    detail = [a.detail for a in ctx.db.execute(select(AppUserAuditLog).where(AppUserAuditLog.action == "updated")).scalars()]
    assert any("Stores -> Admin" in d for d in detail)


def test_admin_cannot_change_or_disable_their_own_account(ctx):
    boss = _boss(ctx)
    me = ctx.db.execute(select(AppUser).where(AppUser.email == "boss@example.com")).scalar_one()
    assert ctx.client.patch(f"/api/v1/users/{me.id}", json={"role": "Stores"}, headers=boss).status_code == 409
    assert ctx.client.post(f"/api/v1/users/{me.id}/disable", headers=boss).status_code == 409
    assert ctx.client.post(f"/api/v1/users/{me.id}/reset-password", headers=boss).status_code == 409


def test_disable_stops_access_at_once_even_if_the_sign_in_service_is_down(ctx):
    boss = _boss(ctx)
    user = ctx.make_user("store@example.com", "Stores", uid="uid-1")
    h = ctx.headers("store@example.com")
    assert ctx.client.get("/api/v1/departments", headers=h).status_code == 200
    ctx.fake.fail_disable = True
    assert ctx.client.post(f"/api/v1/users/{user.id}/disable", headers=boss).json()["status"] == "disabled"
    assert ctx.client.get("/api/v1/departments", headers=h).status_code == 401
    assert _me(ctx, h).json()["status"] == "disabled"
    ctx.fake.fail_disable = False
    assert ctx.client.post(f"/api/v1/users/{user.id}/enable", headers=boss).json()["status"] == "active"
    assert ctx.client.get("/api/v1/departments", headers=h).status_code == 200
    assert ctx.fake.disabled[-1] == ("uid-1", False)


def test_audit_log_endpoint(ctx):
    boss = _boss(ctx)
    ctx.client.post("/api/v1/users", json={"email": "a@example.com", "role": "Foundry"}, headers=boss)
    items = ctx.client.get("/api/v1/users/audit-log", headers=boss).json()["items"]
    assert items[0]["action"] == "user_created" and items[0]["actor"] == "boss@example.com"


# --- other modes unaffected ---------------------------------------------------------------------------

def test_user_admin_is_not_available_in_dev_mode(client, admin_headers):
    assert client.get("/api/v1/users", headers=admin_headers).status_code == 404
    assert client.get("/api/v1/auth/status").json() == {"provider": "dev", "login_available": True}


def test_password_changed_is_hidden_outside_identity_mode(client, admin_headers):
    assert client.post("/api/v1/auth/password-changed", headers=admin_headers).status_code == 404


def test_startup_validation_requires_project_and_api_key(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "identity")
    monkeypatch.setattr(settings, "IDENTITY_PROJECT_ID", "")
    monkeypatch.setattr(settings, "IDENTITY_API_KEY", "")
    with pytest.raises(RuntimeError):
        auth_module.validate_security_configuration()
    monkeypatch.setattr(settings, "IDENTITY_PROJECT_ID", PROJECT)
    with pytest.raises(RuntimeError):
        auth_module.validate_security_configuration()
    monkeypatch.setattr(settings, "IDENTITY_API_KEY", "key")
    monkeypatch.setattr(auth_module, "_build_identity_provider", lambda: IdentityProvider(PROJECT, lambda: None))
    auth_module.validate_security_configuration()


def test_misconfigured_identity_provider_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "identity")
    monkeypatch.setattr(settings, "IDENTITY_PROJECT_ID", "")
    auth_module._IDENTITY_PROVIDER_CACHE.clear()
    assert auth_module.get_auth_provider().name == "none"
