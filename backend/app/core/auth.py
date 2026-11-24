"""
Authentication provider seam.

The production authentication mechanism has NOT been approved by the IT Head (JWT, Microsoft
Entra ID and session cookies are all still candidates). This module therefore provides:

  * `AuthProvider`      - the single interface a real provider must implement.
  * `NoAuthProvider`    - default (AUTH_PROVIDER=none). Authenticates nobody, so every protected
                          route answers 401. This is the fail-closed production default.
  * `DevTokenProvider`  - development/test ONLY (AUTH_PROVIDER=dev). Verifies HMAC-signed bearer
                          tokens minted by the server-side `/auth/dev-login` endpoint (loopback
                          only) or by `issue_dev_token` in tests. It is NOT a production scheme
                          and the application refuses to start with it when ENVIRONMENT=production.

Nothing here reads X-User-* headers; identity only comes from a verified credential.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from typing import Optional, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings, DEFAULT_SECRET_KEY
from app.core.identity_auth import get_identity_admin
from app.db.session import get_db
from app.core.security import (
    AuthenticatedUser,
    UserRole,
    get_current_user_context,
)

logger = logging.getLogger("vspl.auth")

DEV_PROVIDER_ALLOWED_ENVIRONMENTS = {"development", "test", "uat"}
_TOKEN_PREFIX = "dev1"
_MAX_REVOKED_TOKENS = 10000

# Process-local revocation registry for zero-schema dev/test bearer tokens.
# Note: production auth providers must use persistent shared revocation/session state.
_REVOCATION_LOCK = threading.Lock()
_REVOKED_JTIS: dict[str, int] = {}
_REVOKED_TOKEN_HASHES: dict[str, int] = {}

# Fixed, server-side development accounts: a client may only pick one of these by role name.
DEV_USERS: dict[UserRole, AuthenticatedUser] = {
    UserRole.STORES: AuthenticatedUser(user_id="usr_stores_01", role=UserRole.STORES, department="General/Stores"),
    UserRole.FOUNDRY: AuthenticatedUser(user_id="usr_foundry_01", role=UserRole.FOUNDRY, department="Foundry"),
    UserRole.PURCHASE: AuthenticatedUser(user_id="usr_purchase_01", role=UserRole.PURCHASE, department="Purchase"),
    UserRole.MANAGEMENT: AuthenticatedUser(user_id="usr_mgmt_01", role=UserRole.MANAGEMENT, department="Management"),
    UserRole.ADMIN: AuthenticatedUser(user_id="usr_admin_01", role=UserRole.ADMIN, department="Admin"),
    UserRole.QUALITY: AuthenticatedUser(user_id="usr_quality_01", role=UserRole.QUALITY, department="Quality"),
    UserRole.ACCOUNTS: AuthenticatedUser(user_id="usr_accounts_01", role=UserRole.ACCOUNTS, department="Accounts"),
}


class AuthProvider(Protocol):
    """A provider turns a request into a verified user, or None when unauthenticated."""

    name: str

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        ...


class NoAuthProvider:
    name = "none"

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        return None


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    key = settings.SECRET_KEY.encode("utf-8")
    return _b64e(hmac.new(key, f"{_TOKEN_PREFIX}.{payload_b64}".encode("ascii"), hashlib.sha256).digest())


def issue_dev_token(user: AuthenticatedUser, ttl_minutes: Optional[int] = None) -> str:
    """Mint a signed development token. Refuses outside development/test environments."""
    if settings.ENVIRONMENT not in DEV_PROVIDER_ALLOWED_ENVIRONMENTS:
        raise RuntimeError("Development tokens can only be issued in development/test environments.")
    ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES if ttl_minutes is None else ttl_minutes
    payload = {
        "sub": user.user_id,
        "role": user.role.value,
        "dept": user.department,
        "jti": secrets.token_urlsafe(16),
        "exp": int(time.time()) + ttl * 60,
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{_TOKEN_PREFIX}.{payload_b64}.{_sign(payload_b64)}"


def _prune_revoked_locked(now: int) -> None:
    for store in (_REVOKED_JTIS, _REVOKED_TOKEN_HASHES):
        expired = [k for k, exp in store.items() if exp < now]
        for k in expired:
            store.pop(k, None)
        while len(store) > _MAX_REVOKED_TOKENS:
            oldest_key = min(store, key=store.__getitem__)
            store.pop(oldest_key, None)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def revoke_token(token: str, exp: Optional[int] = None, jti: Optional[str] = None) -> None:
    """Revoke a bearer token in the process-local registry until its expiry."""
    now = int(time.time())
    expiry = exp if exp is not None else now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    tok_hash = _token_hash(token)
    with _REVOCATION_LOCK:
        _prune_revoked_locked(now)
        _REVOKED_TOKEN_HASHES[tok_hash] = expiry
        if jti:
            _REVOKED_JTIS[jti] = expiry


def is_token_revoked(token: str, jti: Optional[str] = None) -> bool:
    now = int(time.time())
    tok_hash = _token_hash(token)
    with _REVOCATION_LOCK:
        _prune_revoked_locked(now)
        if tok_hash in _REVOKED_TOKEN_HASHES:
            return True
        if jti and jti in _REVOKED_JTIS:
            return True
    return False


def clear_revoked_tokens() -> None:
    """Reset in-memory revoked tokens (intended for isolated tests)."""
    with _REVOCATION_LOCK:
        _REVOKED_JTIS.clear()
        _REVOKED_TOKEN_HASHES.clear()


class DevTokenProvider:
    name = "dev"

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            stripped = token.strip()
            prefix, payload_b64, signature = stripped.split(".")
            if prefix != _TOKEN_PREFIX:
                return None
            if not hmac.compare_digest(signature, _sign(payload_b64)):
                return None
            payload = json.loads(_b64d(payload_b64))
            if int(payload["exp"]) < time.time():
                return None
            jti = payload.get("jti")
            if is_token_revoked(stripped, str(jti) if jti else None):
                return None
            role = UserRole(payload["role"])  # unknown role -> ValueError -> unauthenticated
            user_id = str(payload["sub"]).strip()
            if not user_id:
                return None
            return AuthenticatedUser(user_id=user_id, role=role, department=str(payload.get("dept", "")))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None


_IAP_PROVIDER_CACHE: dict = {}


def _build_iap_provider():
    """Build (and cache) the Google IAP provider. Imported lazily so other providers need no extra packages."""
    key = (settings.IAP_AUDIENCE, settings.IAP_ROLE_MAP)
    cached = _IAP_PROVIDER_CACHE.get("provider")
    if cached is not None and _IAP_PROVIDER_CACHE.get("key") == key:
        return cached
    from app.core.iap_auth import IapProvider, parse_role_map

    provider = IapProvider(settings.IAP_AUDIENCE, parse_role_map(settings.IAP_ROLE_MAP))
    _IAP_PROVIDER_CACHE.update(provider=provider, key=key)
    return provider


_IDENTITY_PROVIDER_CACHE: dict = {}


def _build_identity_provider():
    """Build (and cache) the Google Identity Platform provider (imported lazily)."""
    key = settings.IDENTITY_PROJECT_ID
    cached = _IDENTITY_PROVIDER_CACHE.get("provider")
    if cached is not None and _IDENTITY_PROVIDER_CACHE.get("key") == key:
        return cached
    from app.core.identity_auth import IdentityProvider
    from app.db.session import SessionLocal

    provider = IdentityProvider(settings.IDENTITY_PROJECT_ID, SessionLocal)
    _IDENTITY_PROVIDER_CACHE.update(provider=provider, key=key)
    return provider


def get_auth_provider() -> AuthProvider:
    """Resolve the configured provider. Anything unrecognised or unsafe resolves to fail-closed."""
    if settings.AUTH_PROVIDER == "dev":
        if settings.ENVIRONMENT in DEV_PROVIDER_ALLOWED_ENVIRONMENTS:
            return DevTokenProvider()
        logger.error("AUTH_PROVIDER=dev is not permitted in ENVIRONMENT=%s; denying all access.", settings.ENVIRONMENT)
    elif settings.AUTH_PROVIDER == "identity":
        try:
            return _build_identity_provider()
        except Exception as exc:  # noqa: BLE001 - a broken configuration must never authenticate anyone
            logger.error("AUTH_PROVIDER=identity is misconfigured (%s); denying all access.", exc.__class__.__name__)
    elif settings.AUTH_PROVIDER == "iap":
        try:
            return _build_iap_provider()
        except Exception as exc:  # noqa: BLE001 - a broken IAP configuration must never authenticate anyone
            logger.error("AUTH_PROVIDER=iap is misconfigured (%s); denying all access.", exc.__class__.__name__)
    return NoAuthProvider()


def validate_security_configuration() -> None:
    """Called at startup. Refuses unsafe production configuration; warns when nobody can log in."""
    if settings.ENVIRONMENT == "uat":
        db_url = settings.sync_database_url
        if "supabase.com" in db_url or "pooler.supabase.com" in db_url or "tymssfqofumbfyxktvxt" in db_url:
            raise RuntimeError(
                "Refusing to start: Backend is configured for UAT mode (ENVIRONMENT=uat) "
                "but target database is production Supabase. UAT must be isolated to sandbox on port 5434."
            )
        if "5434" not in db_url and "vspl_mm_uat_sandbox" not in db_url:
            raise RuntimeError(
                "Refusing to start: Backend is in UAT mode but target database does not match "
                "isolated sandbox 'vspl_mm_uat_sandbox' on port 5434."
            )
    if settings.ENVIRONMENT == "production":
        if settings.AUTH_PROVIDER == "dev":
            raise RuntimeError("Refusing to start: AUTH_PROVIDER=dev is not allowed in production.")
        if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
            raise RuntimeError("Refusing to start: SECRET_KEY is the insecure default in production.")
    if settings.AUTH_PROVIDER == "iap":
        # A half-configured IAP provider must stop the service from starting, in every environment.
        from app.core.iap_auth import IapConfigurationError, parse_role_map

        if not settings.IAP_AUDIENCE:
            raise RuntimeError("Refusing to start: AUTH_PROVIDER=iap requires IAP_AUDIENCE.")
        try:
            parse_role_map(settings.IAP_ROLE_MAP)
        except IapConfigurationError as exc:
            raise RuntimeError(f"Refusing to start: {exc}") from exc
        if settings.ENVIRONMENT == "production" and settings.SECRET_KEY == DEFAULT_SECRET_KEY:
            raise RuntimeError("Refusing to start: SECRET_KEY is the insecure default in production.")
    elif settings.AUTH_PROVIDER == "identity":
        if not settings.IDENTITY_PROJECT_ID or not settings.IDENTITY_API_KEY:
            raise RuntimeError("Refusing to start: AUTH_PROVIDER=identity requires IDENTITY_PROJECT_ID and IDENTITY_API_KEY.")
        if not settings.BOOTSTRAP_ADMIN_EMAILS.strip():
            logger.warning("BOOTSTRAP_ADMIN_EMAILS is empty: the first administrator must already exist in the user table.")
    elif settings.AUTH_PROVIDER not in ("none", "dev"):
        logger.error("Unknown AUTH_PROVIDER '%s'; all protected routes will return 401.", settings.AUTH_PROVIDER)
    if get_auth_provider().name == "none":
        logger.warning("No authentication provider is active: every protected route returns HTTP 401.")


# ----------------------------------------------------------------------------------------------
# /auth endpoints
# ----------------------------------------------------------------------------------------------

router = APIRouter()

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class AuthStatus(BaseModel):
    provider: str
    login_available: bool
    # Only for AUTH_PROVIDER=identity: the public web API key the browser needs to sign in.
    identity_api_key: Optional[str] = None
    microsoft_enabled: Optional[bool] = None


class DevLoginRequest(BaseModel):
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LogoutResponse(BaseModel):
    revoked: bool
    message: str


class UserInfo(BaseModel):
    user_id: str
    role: str
    department: str


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


@router.get(
    "/status",
    response_model=AuthStatus,
    response_model_exclude_none=True,
    summary="Authentication provider status (public)",
)
def auth_status() -> AuthStatus:
    provider = get_auth_provider()
    if provider.name == "identity":
        return AuthStatus(
            provider="identity",
            login_available=True,
            identity_api_key=settings.IDENTITY_API_KEY,
            microsoft_enabled=settings.MICROSOFT_SIGNIN_ENABLED,
        )
    return AuthStatus(provider=provider.name, login_available=provider.name == "dev")


@router.get("/me", summary="Verified identity of the caller")
def whoami(request: Request):
    provider = get_auth_provider()
    if provider.name == "identity":
        # Pending / rejected / disabled people and people who must change their password get an answer here (so the
        # browser can show the right screen); every other route still answers 401 for them.
        return provider.describe(request)
    user = get_current_user_context(request)
    return UserInfo(user_id=user.user_id, role=user.role.value, department=user.department)


@router.post("/password-changed", summary="Confirm the forced first-login password change (identity provider)")
def password_changed(request: Request, db=Depends(get_db), admin=Depends(get_identity_admin)):
    provider = get_auth_provider()
    if provider.name != "identity":
        get_current_user_context(request)  # unauthenticated callers still get 401, never a hint about this route
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    verified = provider.verify(request)
    if verified is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing, invalid or expired credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from app.models.app_user import AppUser
    from sqlalchemy import select as _select
    from app.services.user_service import audit

    user = db.execute(_select(AppUser).where(AppUser.email == verified.email)).scalar_one_or_none()
    if user is None or user.auth_uid != verified.uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a registered account.")
    if not user.must_change_password:
        return {"ok": True}
    try:
        changed_at = admin.password_updated_at(verified.uid)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not confirm the password change. Try again.")
    # The temporary password was set at temp_password_set_at; only a later change counts.
    reference = user.temp_password_set_at
    if changed_at is None or reference is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The password has not been changed yet.")
    if reference.tzinfo is None:
        from datetime import timezone as _tz
        reference = reference.replace(tzinfo=_tz.utc)
    if changed_at <= reference:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The password has not been changed yet.")
    user.must_change_password = False
    audit(db, user.email, "password_changed", user.email, "Temporary password replaced by the user.")
    db.commit()
    return {"ok": True}


@router.post("/dev-login", response_model=DevLoginResponse, summary="Development-only sign-in (loopback)")
def dev_login(payload: DevLoginRequest, request: Request) -> DevLoginResponse:
    if get_auth_provider().name != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    client_host = request.client.host if request.client else ""
    allowed = client_host in _LOOPBACK_HOSTS or (settings.ENVIRONMENT == "test" and client_host == "testclient")
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Development sign-in is restricted to loopback.")
    try:
        role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")
    user = DEV_USERS[role]
    return DevLoginResponse(
        access_token=issue_dev_token(user),
        user=UserInfo(user_id=user.user_id, role=user.role.value, department=user.department),
    )


DEV_CREDENTIALS = {
    "admin@vspl.com": ("admin123", UserRole.ADMIN),
    "usr_admin_01": ("admin123", UserRole.ADMIN),
    "mgmt@vspl.com": ("mgmt123", UserRole.MANAGEMENT),
    "usr_mgmt_01": ("mgmt123", UserRole.MANAGEMENT),
    "stores@vspl.com": ("stores123", UserRole.STORES),
    "usr_stores_01": ("stores123", UserRole.STORES),
    "foundry@vspl.com": ("foundry123", UserRole.FOUNDRY),
    "usr_foundry_01": ("foundry123", UserRole.FOUNDRY),
    "purchase@vspl.com": ("purchase123", UserRole.PURCHASE),
    "usr_purchase_01": ("purchase123", UserRole.PURCHASE),
    "quality@vspl.com": ("quality123", UserRole.QUALITY),
    "usr_quality_01": ("quality123", UserRole.QUALITY),
    "accounts@vspl.com": ("accounts123", UserRole.ACCOUNTS),
    "usr_accounts_01": ("accounts123", UserRole.ACCOUNTS),
}


@router.post("/login", response_model=DevLoginResponse, summary="Credential sign-in")
def credential_login(payload: LoginRequest) -> DevLoginResponse:
    # The built-in development credentials work only while the development provider is active; with any other
    # provider (none, iap) credential sign-in is not configured.
    if get_auth_provider().name != "dev":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Credential-based login is not configured on this backend. Production identity provider approval is pending.",
        )
    user_key = payload.username.strip().lower()
    if user_key in DEV_CREDENTIALS:
        expected_pw, role = DEV_CREDENTIALS[user_key]
        if payload.password == expected_pw:
            user = DEV_USERS[role]
            return DevLoginResponse(
                access_token=issue_dev_token(user),
                user=UserInfo(user_id=user.user_id, role=user.role.value, department=user.department),
            )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )


@router.post("/logout", response_model=LogoutResponse, summary="Sign out and revoke the active bearer token")
def logout(
    request: Request,
    _user: AuthenticatedUser = Depends(get_current_user_context),
) -> LogoutResponse:
    header = request.headers.get("Authorization", "")
    _, _, token = header.partition(" ")
    stripped = token.strip()
    if not stripped:
        # No bearer token to revoke (for example Google IAP sign-in): the session is ended by IAP itself.
        return LogoutResponse(
            revoked=False,
            message="No bearer token to revoke. Sign out of your Google account session through the proxy.",
        )
    exp: Optional[int] = None
    jti: Optional[str] = None
    try:
        _, payload_b64, _ = stripped.split(".")
        payload = json.loads(_b64d(payload_b64))
        exp = int(payload["exp"]) if "exp" in payload else None
        raw_jti = payload.get("jti")
        jti = str(raw_jti) if raw_jti else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass
    revoke_token(stripped, exp=exp, jti=jti)
    return LogoutResponse(revoked=True, message="Signed out cleanly and token revoked.")
