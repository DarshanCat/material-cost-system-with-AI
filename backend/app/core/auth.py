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
import time
from typing import Optional, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings, DEFAULT_SECRET_KEY
from app.core.security import (
    AuthenticatedUser,
    UserRole,
    get_current_user_context,
)

logger = logging.getLogger("vspl.auth")

DEV_PROVIDER_ALLOWED_ENVIRONMENTS = {"development", "test"}
_TOKEN_PREFIX = "dev1"

# Fixed, server-side development accounts: a client may only pick one of these by role name.
DEV_USERS: dict[UserRole, AuthenticatedUser] = {
    UserRole.STORES: AuthenticatedUser(user_id="usr_stores_01", role=UserRole.STORES, department="General/Stores"),
    UserRole.FOUNDRY: AuthenticatedUser(user_id="usr_foundry_01", role=UserRole.FOUNDRY, department="Foundry"),
    UserRole.PURCHASE: AuthenticatedUser(user_id="usr_purchase_01", role=UserRole.PURCHASE, department="Purchase"),
    UserRole.MANAGEMENT: AuthenticatedUser(user_id="usr_mgmt_01", role=UserRole.MANAGEMENT, department="Management"),
    UserRole.ADMIN: AuthenticatedUser(user_id="usr_admin_01", role=UserRole.ADMIN, department="Admin"),
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
        "exp": int(time.time()) + ttl * 60,
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{_TOKEN_PREFIX}.{payload_b64}.{_sign(payload_b64)}"


class DevTokenProvider:
    name = "dev"

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            prefix, payload_b64, signature = token.strip().split(".")
            if prefix != _TOKEN_PREFIX:
                return None
            if not hmac.compare_digest(signature, _sign(payload_b64)):
                return None
            payload = json.loads(_b64d(payload_b64))
            if int(payload["exp"]) < time.time():
                return None
            role = UserRole(payload["role"])  # unknown role -> ValueError -> unauthenticated
            user_id = str(payload["sub"]).strip()
            if not user_id:
                return None
            return AuthenticatedUser(user_id=user_id, role=role, department=str(payload.get("dept", "")))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None


def get_auth_provider() -> AuthProvider:
    """Resolve the configured provider. Anything unrecognised or unsafe resolves to fail-closed."""
    if settings.AUTH_PROVIDER == "dev":
        if settings.ENVIRONMENT in DEV_PROVIDER_ALLOWED_ENVIRONMENTS:
            return DevTokenProvider()
        logger.error("AUTH_PROVIDER=dev is not permitted in ENVIRONMENT=%s; denying all access.", settings.ENVIRONMENT)
    return NoAuthProvider()


def validate_security_configuration() -> None:
    """Called at startup. Refuses unsafe production configuration; warns when nobody can log in."""
    if settings.ENVIRONMENT == "production":
        if settings.AUTH_PROVIDER == "dev":
            raise RuntimeError("Refusing to start: AUTH_PROVIDER=dev is not allowed in production.")
        if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
            raise RuntimeError("Refusing to start: SECRET_KEY is the insecure default in production.")
    if settings.AUTH_PROVIDER not in ("none", "dev"):
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


class DevLoginRequest(BaseModel):
    role: str


class UserInfo(BaseModel):
    user_id: str
    role: str
    department: str


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


@router.get("/status", response_model=AuthStatus, summary="Authentication provider status (public)")
def auth_status() -> AuthStatus:
    provider = get_auth_provider()
    return AuthStatus(provider=provider.name, login_available=provider.name == "dev")


@router.get("/me", response_model=UserInfo, summary="Verified identity of the caller")
def whoami(user: AuthenticatedUser = Depends(get_current_user_context)) -> UserInfo:
    return UserInfo(user_id=user.user_id, role=user.role.value, department=user.department)


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
