"""
Return to Store (RTS) Models.
Supports returning unused material, machine shop borings, runners/risers, and rejection scrap back to stores.
Document numbering: RTS-YYYYMM-XXXX.
"""

from datetime import date, datetime, timezone
from enum import Enum
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReturnCondition(str, Enum):
    UNUSED_GOOD = "UNUSED_GOOD"
    MACHINE_SHOP_BORINGS = "MACHINE_SHOP_BORINGS"
    FOUNDRY_RETURNS = "FOUNDRY_RETURNS"
    REJECTED_CASTINGS = "REJECTED_CASTINGS"
    DAMAGED_CONTAMINATED = "DAMAGED_CONTAMINATED"


class ReturnStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MaterialReturnHeader(Base):
    """
    Return to Store (RTS) Header record.
    Tracks material returned from plant departments back to Stores.
    """
    __tablename__ = "material_return_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    returning_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    receiving_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)

    reference_issue_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("material_issue_headers.id"), nullable=True)
    heat_reference_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    condition: Mapped[str] = mapped_column(String(50), nullable=False, default=ReturnCondition.UNUSED_GOOD.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReturnStatus.SUBMITTED.value, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    accepted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    returning_department = relationship("Department", foreign_keys=[returning_department_id])
    receiving_department = relationship("Department", foreign_keys=[receiving_department_id])
    reference_issue = relationship("MaterialIssueHeader", foreign_keys=[reference_issue_id])

    lines: Mapped[List["MaterialReturnLineItem"]] = relationship(
        "MaterialReturnLineItem",
        back_populates="header",
        cascade="all, delete-orphan",
        order_by="MaterialReturnLineItem.line_number",
    )
    audit_logs: Mapped[List["MaterialReturnAuditLog"]] = relationship(
        "MaterialReturnAuditLog",
        back_populates="header",
        cascade="all, delete-orphan",
        order_by="MaterialReturnAuditLog.timestamp",
    )

    __table_args__ = (
        Index("ix_rts_num_date", "return_number", "return_date"),
    )


class MaterialReturnLineItem(Base):
    """
    Return to Store Line Item record.
    Quantities stored as NUMERIC(15, 4).
    """
    __tablename__ = "material_return_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_return_headers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)

    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False, default=ReturnCondition.UNUSED_GOOD.value)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    header = relationship("MaterialReturnHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class MaterialReturnAuditLog(Base):
    """Audit log for Material Return state transitions."""
    __tablename__ = "material_return_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_return_headers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    header = relationship("MaterialReturnHeader", back_populates="audit_logs")
