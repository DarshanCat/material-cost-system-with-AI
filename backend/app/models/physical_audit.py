"""
Physical Inventory Stock Audit Models.
Tracks physical count reconciliation, calculated variances, and approval lifecycle.
Document numbering: AUD-YYYYMMDD-XXXX.
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


class AuditStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class PhysicalAuditHeader(Base):
    """
    Physical Inventory Stock Audit Header.
    Defines the audit cutoff date and supervisor approval state.
    """
    __tablename__ = "physical_audit_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    audit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AuditStatus.DRAFT.value, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
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

    department = relationship("Department")
    lines: Mapped[List["PhysicalAuditLine"]] = relationship(
        "PhysicalAuditLine", back_populates="header", cascade="all, delete-orphan", order_by="PhysicalAuditLine.line_number"
    )
    audit_logs: Mapped[List["PhysicalAuditAuditLog"]] = relationship(
        "PhysicalAuditAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="PhysicalAuditAuditLog.timestamp"
    )


class PhysicalAuditLine(Base):
    """
    Physical Inventory Stock Audit Line.
    Records system quantity at cutoff, physical count, and calculated variance.
    Variance = Physical Count - System Quantity at Cutoff.
    """
    __tablename__ = "physical_audit_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(Integer, ForeignKey("physical_audit_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    physical_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    header = relationship("PhysicalAuditHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class PhysicalAuditAuditLog(Base):
    """Audit log for Physical Inventory Stock Audit state transitions."""
    __tablename__ = "physical_audit_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(Integer, ForeignKey("physical_audit_headers.id", ondelete="CASCADE"), nullable=False, index=True)
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

    header = relationship("PhysicalAuditHeader", back_populates="audit_logs")
