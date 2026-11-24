"""
Application users: who may sign in, with which role, and whether an administrator has approved them.

Passwords are NOT stored here; Google Identity Platform owns credentials. This table holds the application's
authorisation decision (role, status) keyed by e-mail.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserStatus(str, Enum):
    PENDING = "pending"      # signed in once, waiting for an administrator to approve and assign a role
    ACTIVE = "active"
    REJECTED = "rejected"
    DISABLED = "disabled"


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint("status IN ('pending','active','rejected','disabled')", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.PENDING.value, nullable=False, index=True)
    auth_uid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(32), default="password", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    temp_password_set_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AppUserAuditLog(Base):
    __tablename__ = "app_user_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(254), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
