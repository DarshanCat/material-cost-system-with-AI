"""
User lifecycle rules: first sign-in handling, admin approval, role changes, temporary passwords.

All state changes write an audit row (who did what to whom, when) in the same transaction.
"""

from __future__ import annotations

import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import AuthenticatedUser, UserRole
from app.models.app_user import AppUser, AppUserAuditLog, UserStatus

DEFAULT_DEPARTMENT = {
    UserRole.STORES: "General/Stores",
    UserRole.FOUNDRY: "Foundry",
    UserRole.PURCHASE: "Purchase",
    UserRole.MANAGEMENT: "Management",
    UserRole.ADMIN: "Admin",
    UserRole.QUALITY: "Quality",
    UserRole.ACCOUNTS: "Accounts",
}

_LAST_LOGIN_WRITE_INTERVAL = timedelta(minutes=5)


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def bootstrap_admin_emails() -> set[str]:
    raw = (settings.BOOTSTRAP_ADMIN_EMAILS or "").strip()
    if not raw:
        return set()
    if raw.startswith("["):
        try:
            return {normalize_email(e) for e in json.loads(raw) if normalize_email(e)}
        except (ValueError, TypeError):
            return set()
    return {normalize_email(e) for e in raw.split(",") if normalize_email(e)}


def audit(db: Session, user_email: str, action: str, actor: str, detail: str = "") -> None:
    db.add(AppUserAuditLog(user_email=user_email, action=action, actor=actor, detail=detail[:2000]))


def parse_role(value: str) -> UserRole:
    try:
        return UserRole(value)
    except ValueError as exc:
        raise ValueError(f"Unknown role {value!r}. Allowed: {', '.join(r.value for r in UserRole)}") from exc


def generate_temporary_password(length: int = 16) -> str:
    """Random temporary password with upper, lower, digit and symbol (Identity Platform accepts all of them)."""
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%*-_"]
    chars = [secrets.choice(p) for p in pools]
    alphabet = "".join(pools)
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def resolve_identity(db: Session, *, email: str, uid: str, display_name: str = "", source: str = "password") -> Optional[AppUser]:
    """
    Find (or create) the application user for a verified sign-in.

    - Known e-mail: returns the record (and binds the Identity Platform uid on first use). A different uid for
      the same e-mail is refused (None), so a re-created identity cannot inherit someone else's role.
    - Unknown e-mail on the bootstrap list: becomes an active Admin (the first administrator).
    - Any other unknown e-mail: a Pending record with no role, waiting for administrator approval.
    """
    email = normalize_email(email)
    if not email or not uid:
        return None
    user = db.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user is None:
        is_bootstrap = email in bootstrap_admin_emails()
        user = AppUser(
            email=email,
            display_name=display_name[:120],
            role=UserRole.ADMIN.value if is_bootstrap else None,
            department=DEFAULT_DEPARTMENT[UserRole.ADMIN] if is_bootstrap else "",
            status=UserStatus.ACTIVE.value if is_bootstrap else UserStatus.PENDING.value,
            auth_uid=uid,
            auth_source=source,
            # The first administrator's password was issued to them by the person who set the system up, so it is
            # treated as temporary: they must replace it before doing anything else (not applicable to Microsoft).
            must_change_password=is_bootstrap and source == "password",
            temp_password_set_at=now if (is_bootstrap and source == "password") else None,
            last_login_at=now,
            created_by="system",
            decided_by="system" if is_bootstrap else None,
            decided_at=now if is_bootstrap else None,
        )
        db.add(user)
        audit(db, email, "bootstrap_admin" if is_bootstrap else "first_sign_in_pending", "system",
              "First administrator created from the bootstrap list." if is_bootstrap else "Waiting for approval.")
        try:
            db.commit()
        except IntegrityError:  # two first sign-ins raced
            db.rollback()
            user = db.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
            if user is None:
                return None
        return user

    if user.auth_uid and user.auth_uid != uid:
        return None
    changed = False
    if not user.auth_uid:
        user.auth_uid = uid
        changed = True
    last = user.last_login_at
    if last is not None and last.tzinfo is None:  # SQLite returns naive timestamps
        last = last.replace(tzinfo=timezone.utc)
    if last is None or now - last > _LAST_LOGIN_WRITE_INTERVAL:
        user.last_login_at = now
        changed = True
    if changed:
        db.commit()
    return user


def to_authenticated(user: AppUser) -> Optional[AuthenticatedUser]:
    """The identity used by business routes: only an active, approved user who has finished the forced password change."""
    if user.status != UserStatus.ACTIVE.value or user.must_change_password or not user.role:
        return None
    try:
        role = UserRole(user.role)
    except ValueError:
        return None
    return AuthenticatedUser(user_id=user.email, role=role, department=user.department or DEFAULT_DEPARTMENT[role])


def count_active_admins(db: Session) -> int:
    return len(
        db.execute(
            select(AppUser.id).where(AppUser.status == UserStatus.ACTIVE.value, AppUser.role == UserRole.ADMIN.value)
        ).all()
    )
