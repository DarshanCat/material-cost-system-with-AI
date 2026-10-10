"""
Material Issue Models.
Supports departmental material issuance and furnace heat allocation tracking.
Document numbering: ISS-YYYYMMDD-XXXX. Heat ref format: H-102603-3721.
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


class IssueStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class MaterialIssueHeader(Base):
    """
    Material Issue Header transaction record.
    Tracks issues between plant departments with optional heat allocation.
    """
    __tablename__ = "material_issue_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_slip_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    issuing_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    receiving_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    
    # Heat reference code (e.g. H-102603-3721) for foundry melting issues
    heat_reference_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=IssueStatus.DRAFT.value, index=True)
    
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

    issuing_department = relationship("Department", foreign_keys=[issuing_department_id])
    receiving_department = relationship("Department", foreign_keys=[receiving_department_id])
    
    lines: Mapped[List["MaterialIssueLineItem"]] = relationship(
        "MaterialIssueLineItem", back_populates="header", cascade="all, delete-orphan", order_by="MaterialIssueLineItem.line_number"
    )
    audit_logs: Mapped[List["IssueAuditLog"]] = relationship(
        "IssueAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="IssueAuditLog.timestamp"
    )

    __table_args__ = (
        Index("ix_issue_slip_date_recv", "issue_slip_number", "issue_date", "receiving_department_id"),
    )


class MaterialIssueLineItem(Base):
    """
    Material Issue Line Item record.
    Quantities stored as NUMERIC(15, 4).
    """
    __tablename__ = "material_issue_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_issue_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    header = relationship("MaterialIssueHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class IssueAuditLog(Base):
    """Audit log for Material Issue transitions."""
    __tablename__ = "issue_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_issue_headers.id", ondelete="CASCADE"), nullable=False, index=True)
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

    header = relationship("MaterialIssueHeader", back_populates="audit_logs")
