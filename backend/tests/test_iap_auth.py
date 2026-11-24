"""
Google IAP authentication provider (AUTH_PROVIDER=iap): signature, claims, role mapping, fail-closed behaviour,
startup validation, and the production hardening added with it (docs off, security headers, single-origin frontend).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import app.core.auth as auth_module
from app.core.config import settings
from app.core.iap_auth import IAP_ISSUER, IapConfigurationError, IapProvider, parse_role_map

BACKEND_DIR = Path(__file__).resolve().parents[1]
AUDIENCE = "/projects/123456789/locations/asia-south1/services/vspl-mms"
KID = "test-key-1"

ROLE_MAP_JSON = json.dumps(
    {
        "Stores.User@Example.com": "Stores",
        "mgmt@example.com": {"role": "Management", "department": "Plant Head"},
        "admin@example.com": "Admin",
    }
)


@pytest.fixture(scope="module")
def keypair():
    return ec.generate_private_key(ec.SECP256R1())


def _jwk(private_key, kid=KID):
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return jwk


def _token(private_key, *, email="stores.user@example.com", aud=AUDIENCE, iss=IAP_ISSUER, exp_delta=600, kid=KID, extra=None, drop=()):
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "iat": now, "exp": now + exp_delta, "email": email, "sub": "accounts.google.com:1"}
    claims.update(extra or {})
    for key in drop:
        claims.pop(key, None)
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": kid})


@pytest.fixture
def iap_client(anon_client: TestClient, keypair, monkeypatch):
    """The application in IAP mode, with Google's keys replaced by a test key set."""
    calls = {"loads": 0}

    def loader():
        calls["loads"] += 1
        return {KID: _jwk(keypair)}

    provider = IapProvider(AUDIENCE, parse_role_map(ROLE_MAP_JSON), key_loader=loader)
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "iap")
    monkeypatch.setattr(auth_module, "_build_iap_provider", lambda: provider)
    anon_client.iap_calls = calls
    anon_client.iap_provider = provider
    return anon_client


def _me(client, token=None, headers=None):
    hdrs = dict(headers or {})
    if token:
        hdrs["X-Goog-IAP-JWT-Assertion"] = token
    return client.get("/api/v1/auth/me", headers=hdrs)


def test_valid_token_authenticates_and_maps_role(iap_client, keypair):
    res = _me(iap_client, _token(keypair))
    assert res.status_code == 200
    assert res.json() == {"user_id": "stores.user@example.com", "role": "Stores", "department": "General/Stores"}


def test_role_map_entry_can_carry_a_department(iap_client, keypair):
    res = _me(iap_client, _token(keypair, email="mgmt@example.com"))
    assert res.status_code == 200
    assert res.json()["role"] == "Management" and res.json()["department"] == "Plant Head"


@pytest.mark.parametrize(
    "label,kwargs",
    [
        ("wrong audience", {"aud": "/projects/1/locations/x/services/other"}),
        ("wrong issuer", {"iss": "https://accounts.google.com"}),
        ("expired", {"exp_delta": -3600}),
        ("missing email claim", {"drop": ("email",)}),
        ("missing issued-at claim", {"drop": ("iat",)}),
        ("e-mail not in the role map", {"email": "stranger@example.com"}),
        ("unknown key id", {"kid": "not-a-google-key"}),
    ],
)
def test_invalid_tokens_are_not_authenticated(iap_client, keypair, label, kwargs):
    assert _me(iap_client, _token(keypair, **kwargs)).status_code == 401, label


def test_tampered_payload_is_rejected(iap_client, keypair):
    header, payload, signature = _token(keypair).split(".")
    forged = jwt.utils.base64url_encode(json.dumps({"iss": IAP_ISSUER, "aud": AUDIENCE, "iat": 1, "exp": 4102444800, "email": "admin@example.com"}).encode()).decode()
    assert _me(iap_client, ".".join([header, forged, signature])).status_code == 401


def test_token_signed_by_another_key_is_rejected(iap_client):
    other = ec.generate_private_key(ec.SECP256R1())
    assert _me(iap_client, _token(other)).status_code == 401


def test_algorithm_confusion_and_none_are_rejected(iap_client, keypair):
    # A symmetric (HS256) token carrying the right key id, and an unsigned token with alg=none: only ES256 is accepted.
    now = int(time.time())
    claims = {"iss": IAP_ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 600, "email": "admin@example.com"}
    hs256 = jwt.encode(claims, "x" * 40, algorithm="HS256", headers={"kid": KID})
    assert _me(iap_client, hs256).status_code == 401
    none_token = ".".join(
        [
            jwt.utils.base64url_encode(json.dumps({"alg": "none", "kid": KID}).encode()).decode(),
            jwt.utils.base64url_encode(json.dumps(claims).encode()).decode(),
            "",
        ]
    )
    assert _me(iap_client, none_token).status_code == 401


def test_no_header_and_garbage_header_are_not_authenticated(iap_client):
    assert _me(iap_client).status_code == 401
    assert _me(iap_client, "garbage").status_code == 401
    assert _me(iap_client, "a.b.c").status_code == 401


def test_unsigned_google_identity_headers_are_never_trusted(iap_client, keypair):
    spoof = {"X-Goog-Authenticated-User-Email": "accounts.google.com:admin@example.com", "X-Goog-Authenticated-User-Id": "1"}
    assert _me(iap_client, headers=spoof).status_code == 401
    # A valid Stores token plus a spoofed Admin header is still Stores.
    res = _me(iap_client, _token(keypair), headers=spoof)
    assert res.status_code == 200 and res.json()["role"] == "Stores"


def test_development_tokens_and_login_do_not_work_in_iap_mode(iap_client):
    assert iap_client.post("/api/v1/auth/dev-login", json={"role": "Admin"}).status_code == 404
    status = iap_client.get("/api/v1/auth/status").json()
    assert status == {"provider": "iap", "login_available": False}
    assert iap_client.post("/api/v1/auth/login", json={"username": "a", "password": "b"}).status_code == 501


def test_key_loader_failure_fails_closed(anon_client: TestClient, keypair, monkeypatch):
    def broken():
        raise RuntimeError("network down")

    provider = IapProvider(AUDIENCE, parse_role_map(ROLE_MAP_JSON), key_loader=broken)
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "iap")
    monkeypatch.setattr(auth_module, "_build_iap_provider", lambda: provider)
    assert _me(anon_client, _token(keypair)).status_code == 401


def test_unknown_key_id_does_not_trigger_unbounded_key_refreshes(iap_client, keypair):
    for _ in range(5):
        assert _me(iap_client, _token(keypair, kid="rotated-away")).status_code == 401
    assert iap_client.iap_calls["loads"] <= 2


def test_roles_are_enforced_end_to_end(iap_client, keypair):
    stores = _token(keypair)
    mgmt = _token(keypair, email="mgmt@example.com")
    assert iap_client.get("/api/v1/costing/runs", headers={"X-Goog-IAP-JWT-Assertion": stores}).status_code == 403
    assert iap_client.get("/api/v1/costing/runs", headers={"X-Goog-IAP-JWT-Assertion": mgmt}).status_code == 200
    assert iap_client.get("/api/v1/health/db-check").status_code == 401


def test_logout_without_a_bearer_token_does_not_fake_a_revocation(iap_client, keypair):
    res = iap_client.post("/api/v1/auth/logout", headers={"X-Goog-IAP-JWT-Assertion": _token(keypair)})
    assert res.status_code == 200 and res.json()["revoked"] is False


# ---------------------------------------------------------------------------------------------------------
# Role map and startup validation
# ---------------------------------------------------------------------------------------------------------

def test_role_map_parsing_normalises_e_mail_case():
    parsed = parse_role_map(ROLE_MAP_JSON)
    assert set(parsed) == {"stores.user@example.com", "mgmt@example.com", "admin@example.com"}


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "not json", "[]", "{}", '{"nobody": "Stores"}', '{"a@example.com": "Superuser"}', '{"a@example.com": 5}'],
)
def test_malformed_role_maps_are_refused(raw):
    with pytest.raises(IapConfigurationError):
        parse_role_map(raw)


def test_startup_refuses_a_half_configured_iap_provider(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "iap")
    monkeypatch.setattr(settings, "IAP_ROLE_MAP", ROLE_MAP_JSON)
    monkeypatch.setattr(settings, "IAP_AUDIENCE", "")
    with pytest.raises(RuntimeError, match="IAP_AUDIENCE"):
        auth_module.validate_security_configuration()
    monkeypatch.setattr(settings, "IAP_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(settings, "IAP_ROLE_MAP", "")
    with pytest.raises(RuntimeError, match="IAP_ROLE_MAP"):
        auth_module.validate_security_configuration()
    monkeypatch.setattr(settings, "IAP_ROLE_MAP", ROLE_MAP_JSON)
    auth_module.validate_security_configuration()  # a complete configuration starts


def test_production_with_the_default_secret_is_refused_for_iap(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "iap")
    monkeypatch.setattr(settings, "IAP_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(settings, "IAP_ROLE_MAP", ROLE_MAP_JSON)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", auth_module.DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth_module.validate_security_configuration()


def test_a_broken_iap_configuration_authenticates_nobody(anon_client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "iap")
    monkeypatch.setattr(settings, "IAP_AUDIENCE", "")
    monkeypatch.setattr(settings, "IAP_ROLE_MAP", "")
    assert auth_module.get_auth_provider().name == "none"
    assert anon_client.get("/api/v1/auth/me").status_code == 401


# ---------------------------------------------------------------------------------------------------------
# Production hardening: single-origin frontend, docs off, security headers (run in a fresh interpreter,
# because the application reads these settings when it is imported)
# ---------------------------------------------------------------------------------------------------------

_HARDENING_SCRIPT = r"""
import json, os, sys, pathlib, tempfile
dist = pathlib.Path(tempfile.mkdtemp())
(dist / "index.html").write_text("<html>APP</html>")
(dist / "assets").mkdir()
(dist / "assets" / "app.js").write_text("console.log('x')")
secret = pathlib.Path(tempfile.mkdtemp()) / "secret.txt"
secret.write_text("TOP SECRET")
os.environ.update(
    ENVIRONMENT="production", AUTH_PROVIDER="none", SECRET_KEY="x" * 40,
    DATABASE_URL="postgresql+psycopg://qa:qa@127.0.0.1:1/qa", FRONTEND_DIST_DIR=str(dist),
)
sys.path.insert(0, os.environ["BACKEND_DIR"])
from fastapi.testclient import TestClient
from app.main import app
out = {}
with TestClient(app) as c:
    r = c.get("/");                         out["root"] = (r.status_code, r.text)
    r = c.get("/assets/app.js");            out["asset"] = (r.status_code, r.text)
    r = c.get("/items/some/route");         out["spa_route"] = (r.status_code, r.text)
    r = c.get("/api/v1/does-not-exist");    out["api_404"] = (r.status_code, "APP" in r.text)
    r = c.get("/%2e%2e/" + secret.parent.name + "/secret.txt"); out["traversal"] = (r.status_code, "TOP SECRET" in r.text)
    r = c.get("/docs");                     out["docs"] = ("swagger" in r.text.lower(), "APP" in r.text)
    r = c.get("/api/v1/openapi.json");      out["openapi"] = r.status_code
    r = c.get("/api/v1/health");            out["headers"] = {k: v for k, v in r.headers.items() if k in ("x-content-type-options", "x-frame-options", "referrer-policy", "cache-control", "strict-transport-security")}
print("RESULT=" + json.dumps(out))
"""


def test_production_hardening_in_a_fresh_interpreter():
    import os

    env = dict(os.environ, BACKEND_DIR=str(BACKEND_DIR), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-c", _HARDENING_SCRIPT], env=env, capture_output=True, text=True, timeout=120)
    marker = [line for line in done.stdout.splitlines() if line.startswith("RESULT=")]
    assert marker, done.stdout[-600:] + done.stderr[-600:]
    out = json.loads(marker[0][len("RESULT="):])
    assert out["root"] == [200, "<html>APP</html>"]
    assert out["asset"] == [200, "console.log('x')"]
    assert out["spa_route"] == [200, "<html>APP</html>"]
    assert out["api_404"] == [404, False]          # an unknown API path is a real 404, never the app shell
    assert out["traversal"][1] is False             # files outside the frontend folder are never served
    assert out["docs"] == [False, True]             # /docs is the app shell, not the interactive API documentation
    assert out["openapi"] == 404
    headers = out["headers"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-store"
    assert "max-age" in headers["strict-transport-security"]
