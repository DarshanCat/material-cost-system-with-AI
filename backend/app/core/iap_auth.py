"""
Google Identity-Aware Proxy (IAP) authentication provider (AUTH_PROVIDER=iap).

IAP sits in front of the service and signs every request it lets through with a short-lived JWT in the
`X-Goog-IAP-JWT-Assertion` header. This provider trusts ONLY that signed token:
  * the signature must verify against Google's published IAP keys (ES256, matched by `kid`);
  * `iss` must be https://cloud.google.com/iap, `aud` must equal IAP_AUDIENCE, and the token must not be expired;
  * the verified e-mail must be in the administrator-controlled IAP_ROLE_MAP, which assigns exactly one of
    the five application roles. An unknown e-mail is not authenticated.
The unsigned `X-Goog-Authenticated-User-*` headers are never read, because they can be forged if IAP is bypassed.
Any failure returns "not authenticated" (the caller answers 401); nothing falls back to a default identity.

IAP_ROLE_MAP is JSON, either {"user@example.com": "Stores"} or
{"user@example.com": {"role": "Stores", "department": "General/Stores"}}.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Mapping, Optional

import httpx
import jwt
from fastapi import Request

from app.core.security import AuthenticatedUser, UserRole

logger = logging.getLogger("vspl.auth.iap")

IAP_HEADER = "x-goog-iap-jwt-assertion"
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
IAP_ALGORITHM = "ES256"

_KEY_CACHE_SECONDS = 3600
_MIN_REFRESH_SECONDS = 60  # an unknown key id triggers at most one refresh per minute
_CLOCK_LEEWAY_SECONDS = 30

# Default department label when the role map only gives a role.
_DEFAULT_DEPARTMENT = {
    UserRole.STORES: "General/Stores",
    UserRole.FOUNDRY: "Foundry",
    UserRole.PURCHASE: "Purchase",
    UserRole.MANAGEMENT: "Management",
    UserRole.ADMIN: "Admin",
    UserRole.QUALITY: "Quality",
    UserRole.ACCOUNTS: "Accounts",
}

KeyLoader = Callable[[], Mapping[str, Any]]


class IapConfigurationError(RuntimeError):
    pass


def parse_role_map(raw: str) -> dict[str, tuple[UserRole, str]]:
    """Parse IAP_ROLE_MAP into {lower-case e-mail: (role, department)}. Raises on anything malformed."""
    if not raw or not raw.strip():
        raise IapConfigurationError("IAP_ROLE_MAP is empty; no one could be authenticated.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IapConfigurationError(f"IAP_ROLE_MAP is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict) or not data:
        raise IapConfigurationError("IAP_ROLE_MAP must be a non-empty JSON object of e-mail to role.")
    result: dict[str, tuple[UserRole, str]] = {}
    for email, entry in data.items():
        key = str(email).strip().lower()
        if "@" not in key:
            raise IapConfigurationError(f"IAP_ROLE_MAP key is not an e-mail address: {email!r}")
        role_name = entry.get("role") if isinstance(entry, dict) else entry
        try:
            role = UserRole(role_name)
        except ValueError as exc:
            raise IapConfigurationError(f"IAP_ROLE_MAP gives {email!r} an unknown role {role_name!r}") from exc
        department = str(entry.get("department")) if isinstance(entry, dict) and entry.get("department") else _DEFAULT_DEPARTMENT[role]
        result[key] = (role, department)
    return result


def _fetch_google_keys() -> Mapping[str, Any]:
    response = httpx.get(IAP_KEYS_URL, timeout=5.0)
    response.raise_for_status()
    return {k["kid"]: k for k in response.json().get("keys", []) if "kid" in k}


class IapProvider:
    name = "iap"

    def __init__(self, audience: str, role_map: Mapping[str, tuple[UserRole, str]], key_loader: Optional[KeyLoader] = None):
        if not audience:
            raise IapConfigurationError("IAP_AUDIENCE is not set.")
        if not role_map:
            raise IapConfigurationError("IAP role map is empty.")
        self._audience = audience
        self._role_map = dict(role_map)
        self._key_loader = key_loader or _fetch_google_keys
        self._lock = threading.Lock()
        self._keys: Mapping[str, Any] = {}
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
                    logger.warning("Could not load IAP public keys: %s", exc.__class__.__name__)
                    self._loaded_at = now - _KEY_CACHE_SECONDS + _MIN_REFRESH_SECONDS
            jwk = self._keys.get(kid)
        if jwk is None:
            return None
        return jwt.PyJWK(dict(jwk)).key

    def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        token = request.headers.get(IAP_HEADER, "").strip()
        if not token:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != IAP_ALGORITHM or not header.get("kid"):
                return None
            key = self._get_key(str(header["kid"]))
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key,
                algorithms=[IAP_ALGORITHM],
                audience=self._audience,
                issuer=IAP_ISSUER,
                leeway=_CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "aud", "iss", "email"]},
            )
            email = str(claims["email"]).strip().lower()
            mapped = self._role_map.get(email)
            if mapped is None:
                logger.warning("IAP user is signed in to Google but has no application role.")
                return None
            role, department = mapped
            return AuthenticatedUser(user_id=email, role=role, department=department)
        except Exception:  # noqa: BLE001 - any verification problem means "not authenticated"
            return None
