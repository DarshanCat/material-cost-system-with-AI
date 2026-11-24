"""
Purchase Request (PR) Models for SCM Planning and Plant Head Layer-1 Approval.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PRStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONVERTED_TO_PO = "CONVERTED_TO_PO"
    CANCELLED = "CANCELLED"


class PRHeader(Base):
    """
    Purchase Request Header record.
    Raised by SCM / Planning Department, approved by Plant Head.
    Document numbering: PR-YYYYMM-XXXX
    """
    __tablename__ = "pr_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    
    requisitioner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    requisitioner_role: Mapped[str] = mapped_column(String(50), default="SCM / Planning")
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=PRStatus.DRAFT.value, index=True)
    
    plant_head_approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plant_head_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
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
    lines: Mapped[List["PRLineItem"]] = relationship(
        "PRLineItem", back_populates="header", cascade="all, delete-orphan", order_by="PRLineItem.line_number"
    )
    audit_logs: Mapped[List["PRAuditLog"]] = relationship(
        "PRAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="PRAuditLog.timestamp"
    )


class PRLineItem(Base):
    """
    Purchase Request Line Item.
    """
    __tablename__ = "pr_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, ForeignKey("pr_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    estimated_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    header = relationship("PRHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class PRAuditLog(Base):
    """
    Audit log for PR status transitions.
    """
    __tablename__ = "pr_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int] = mapped_column(Integer, ForeignKey("pr_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    header = relationship("PRHeader", back_populates="audit_logs")
