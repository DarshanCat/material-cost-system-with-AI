"""
Google Identity Platform authentication provider (AUTH_PROVIDER=identity).

People sign in with an e-mail and password that an administrator created (or, later, with Microsoft). The browser
receives a short-lived Identity Platform ID token and sends it as `Authorization: Bearer <token>`. This provider
trusts ONLY a token that verifies:
  * RS256 signature against Google's published securetoken keys (matched by `kid`),
  * issuer https://securetoken.google.com/<project>, audience <project>, not expired, subject and e-mail present;
and then the application's own decision in the `app_users` table: the person must be Active, have a role, and have
finished the forced first-login password change. Anything else is "not authenticated" (HTTP 401): unknown,
pending, rejected, disabled, or a different Identity Platform account for a known e-mail.

`IdentityAdmin` is the server-side client the Admin screens use to create accounts, reset passwords and disable
accounts. It uses the Cloud Run service account (no keys in the repository).
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser
from app.models.app_user import AppUser
from app.services.user_service import resolve_identity, to_authenticated

logger = logging.getLogger("vspl.auth.identity")

SECURETOKEN_KEYS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
ALGORITHM = "RS256"
_KEY_CACHE_SECONDS = 3600
_MIN_REFRESH_SECONDS = 60
_CLOCK_LEEWAY_SECONDS = 30

KeyLoader = Callable[[], Mapping[str, str]]
SessionFactory = Callable[[], Session]


class IdentityConfigurationError(RuntimeError):
    pass


def _fetch_google_keys() -> Mapping[str, str]:
    response = httpx.get(SECURETOKEN_KEYS_URL, timeout=5.0)
    response.raise_for_status()
    return dict(response.json())


def _public_key_from_pem(pem: str):
    data = pem.encode("utf-8")
    if b"BEGIN CERTIFICATE" in data:
        return x509.load_pem_x509_certificate(data).public_key()
    return serialization.load_pem_public_key(data)


class VerifiedToken:
    def __init__(self, claims: Mapping[str, Any]):
        self.uid = str(claims["sub"])
        self.email = str(claims["email"]).strip().lower()
        self.display_name = str(claims.get("name") or "")
        firebase = claims.get("firebase") or {}
        self.sign_in_provider = str(firebase.get("sign_in_provider") or "password")


class IdentityProvider:
    name = "identity"

    def __init__(self, project_id: str, session_factory: SessionFactory, key_loader: Optional[KeyLoader] = None):
        if not project_id:
            raise IdentityConfigurationError("IDENTITY_PROJECT_ID is not set.")
        self._project_id = project_id
        self._session_factory = session_factory
        self._key_loader = key_loader or _fetch_google_keys
        self._lock = threading.Lock()
        self._keys: Mapping[str, str] = {}
        self._loaded_at = 0.0

    def _get_key(self, kid: str):
        now = time.time()
        with self._lock:
            stale = now - self._loaded_at > _KEY_CACHE_SECONDS
            unknown = kid not in self._keys
            can_refresh = now - self._loaded_at >= _MIN_REFRESH_SECONDS
            if (stale or unknown) and (can_refresh or not self._keys):
                try:
                    self._keys = dict(self._key_loader())
                    self._loaded_at = now
                except Exception as exc:  # noqa: BLE001 - fail closed on any key-fetch problem
                    logger.warning("Could not load Identity Platform public keys: %s", exc.__class__.__name__)
                    self._loaded_at = now - _KEY_CACHE_SECONDS + _MIN_REFRESH_SECONDS
            pem = self._keys.get(kid)
        if pem is None:
            return None
        return _public_key_from_pem(pem)

    def verify(self, request: Request) -> Optional[VerifiedToken]:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            unverified = jwt.get_unverified_header(token)
            if unverified.get("alg") != ALGORITHM or not unverified.get("kid"):
                return None
            key = self._get_key(str(unverified["kid"]))
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=self._project_id,
                issuer=f"https://securetoken.google.com/{self._project_id}",
                leeway=_CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "aud", "iss", "sub", "email"]},
            )
            if not str(claims.get("sub", "")).strip() or "@" not in str(claims["email"]):
                return None
            auth_time = claims.get("auth_time")
            if auth_time is not None and int(auth_time) > time.time() + _CLOCK_LEEWAY_SECONDS:
                return None
            return VerifiedToken(claims)
        except Exception:  # noqa: BLE001 - any verification problem means "not authenticated"
            return None

    def _user_for(self, verified: VerifiedToken) -> tuple[Optional[AppUser], Session]:
        db = self._session_factory()
        try:
            return resolve_identity(
                db, email=verified.email, uid=verified.uid, display_name=verified.display_name, source=verified.sign_in_provider
            ), db
        except Exception:
            db.close()
            raise

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        verified = self.verify(request)
        if verified is None:
            return None
        try:
            user, db = self._user_for(verified)
        except Exception as exc:  # noqa: BLE001 - a database problem must not authenticate anyone
            logger.error("Identity lookup failed: %s", exc.__class__.__name__)
            return None
        try:
            return to_authenticated(user) if user is not None else None
        finally:
            db.close()

    def describe(self, request: Request) -> dict:
        """What /auth/me tells the browser: who, status, and whether a password change is still required."""
        verified = self.verify(request)
        if verified is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: missing, invalid or expired credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user, db = self._user_for(verified)
        except Exception as exc:  # noqa: BLE001
            logger.error("Identity lookup failed: %s", exc.__class__.__name__)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User directory unavailable.")
        try:
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="This sign-in does not match the registered account. Contact the administrator.",
                )
            return {
                "user_id": user.email,
                "role": user.role,
                "department": user.department or "",
                "status": user.status,
                "must_change_password": bool(user.must_change_password),
                "display_name": user.display_name or "",
            }
        finally:
            db.close()


# ----------------------------------------------------------------------------------------------
# Server-side administration of Identity Platform accounts
# ----------------------------------------------------------------------------------------------

class IdentityAdminError(RuntimeError):
    """A failed Identity Platform administration call. The message is safe to show to an administrator."""


class IdentityAdmin:
    """Thin REST client (Identity Toolkit v1) authorised as the service account the application runs as."""

    def __init__(self, project_id: str):
        # Not validated here: this object is created for every request that declares it, including in sign-in
        # modes that never use it. Calls fail with IdentityAdminError when the project is not configured.
        self._project_id = project_id
        self._session = None

    def _authed(self):
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._session = AuthorizedSession(credentials)
        return self._session

    def _call(self, path: str, body: dict) -> dict:
        if not self._project_id:
            raise IdentityAdminError("The sign-in service is not configured.")
        url = f"https://identitytoolkit.googleapis.com/v1/projects/{self._project_id}/{path}"
        try:
            response = self._authed().post(
                url, json=body, headers={"x-goog-user-project": self._project_id}, timeout=15
            )
        except Exception as exc:  # noqa: BLE001
            raise IdentityAdminError("The sign-in service could not be reached. Try again.") from exc
        if response.status_code >= 400:
            message = ""
            try:
                message = str(response.json().get("error", {}).get("message", ""))
            except Exception:  # noqa: BLE001
                pass
            if message.startswith("EMAIL_EXISTS"):
                raise IdentityAdminError("A sign-in account with this e-mail already exists.")
            if message.startswith("WEAK_PASSWORD"):
                raise IdentityAdminError("The generated password was rejected as weak; try again.")
            logger.error("Identity Platform admin call %s failed: HTTP %s %s", path, response.status_code, message[:80])
            raise IdentityAdminError("The sign-in service rejected the request.")
        return response.json()

    def create_user(self, email: str, password: str, display_name: str) -> str:
        data = self._call("accounts", {"email": email, "password": password, "displayName": display_name, "emailVerified": False})
        return str(data["localId"])

    def set_password(self, uid: str, password: str) -> None:
        self._call("accounts:update", {"localId": uid, "password": password, "validSince": str(int(time.time()))})

    def set_disabled(self, uid: str, disabled: bool) -> None:
        body: dict = {"localId": uid, "disableUser": disabled}
        if disabled:
            body["validSince"] = str(int(time.time()))
        self._call("accounts:update", body)

    def revoke_sessions(self, uid: str) -> None:
        self._call("accounts:update", {"localId": uid, "validSince": str(int(time.time()))})

    def password_updated_at(self, uid: str) -> Optional[datetime]:
        data = self._call("accounts:lookup", {"localId": [uid]})
        users = data.get("users") or []
        if not users:
            return None
        millis = users[0].get("passwordUpdatedAt")
        if millis is None:
            return None
        return datetime.fromtimestamp(float(millis) / 1000.0, tz=timezone.utc)

    def delete_user(self, uid: str) -> None:
        self._call("accounts:delete", {"localId": uid})


_ADMIN_CACHE: dict = {}


def get_identity_admin() -> IdentityAdmin:
    """FastAPI dependency (overridden in tests)."""
    from app.core.config import settings

    admin = _ADMIN_CACHE.get(settings.IDENTITY_PROJECT_ID)
    if admin is None:
        admin = IdentityAdmin(settings.IDENTITY_PROJECT_ID)
        _ADMIN_CACHE[settings.IDENTITY_PROJECT_ID] = admin
    return admin
