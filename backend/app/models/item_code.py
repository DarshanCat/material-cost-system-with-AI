"""
Item code allocation, permanent code registry and item master audit history.

Schema introduced by Alembic revision 008_item_code_registry (NOT executed automatically).

- ItemCodeSequence: one row per (department, category) holding the highest serial ever allocated by the
  generator. Locked with SELECT ... FOR UPDATE during allocation so concurrent approvals serialise.
- ItemCodeRegistry: every code issued by the generator, permanently. Append-only (ORM guard, SQLite and
  PostgreSQL triggers). Codes are never deleted or reused, including codes of retired (inactive) items.
- ItemMasterAuditLog: append-only history of registration, retirement, reactivation and approved
  corrections to material items.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ItemCodeSequence(Base):
    __tablename__ = "item_code_sequences"
    __table_args__ = (
        CheckConstraint("last_serial >= 0 AND last_serial <= 999", name="last_serial_range"),
    )

    department_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    category_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    last_serial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ItemCodeRegistry(Base):
    __tablename__ = "item_code_registry"
    __table_args__ = (
        CheckConstraint("serial >= 1 AND serial <= 999", name="serial_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    department_code: Mapped[str] = mapped_column(String(3), nullable=False)
    category_code: Mapped[str] = mapped_column(String(2), nullable=False)
    serial: Mapped[int] = mapped_column(Integer, nullable=False)
    material_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_items.id"), unique=True, nullable=False
    )
    item_request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("item_requests.id"), nullable=True)
    standard_version: Mapped[str] = mapped_column(String(10), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(100), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ItemMasterAction:
    REGISTERED = "REGISTERED"
    RENAMED = "RENAMED"
    RETIRED = "RETIRED"
    REACTIVATED = "REACTIVATED"
    METADATA_UPDATED = "METADATA_UPDATED"


class ItemMasterAuditLog(Base):
    __tablename__ = "item_master_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("item_requests.id"), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
