"""Helpers for building authenticated test requests (signed dev tokens; never X-User-* headers)."""

from app.core.auth import DEV_USERS, issue_dev_token
from app.core.security import UserRole


def bearer(role) -> dict[str, str]:
    """Authorization header for the fixed server-side dev account of `role` (UserRole or its name)."""
    role = UserRole(role)
    return {"Authorization": f"Bearer {issue_dev_token(DEV_USERS[role])}"}
