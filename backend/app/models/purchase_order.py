"""
Purchase Order (PO) Models for P2P Procurement Cycle.
Linked to Plant Head Approved Purchase Requests (PR).
Approved by CEO/MD, followed by Order Placed with Vendor.
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


class POStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ORDER_PLACED = "ORDER_PLACED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class POHeader(Base):
    """
    Purchase Order Header record.
    Must be linked to an approved Purchase Request.
    """
    __tablename__ = "po_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    pr_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pr_headers.id"), nullable=True, index=True)
    pr_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(100), default="Net 30 Days")
    delivery_terms: Mapped[Optional[str]] = mapped_column(String(255), default="Door Delivery to VSPL Works")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    total_amount_ex_gst: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    total_gst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    grand_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=POStatus.DRAFT.value, index=True)
    current_approval_level: Mapped[str] = mapped_column(String(30), default="MANAGEMENT")
    
    mgmt_approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mgmt_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    order_placed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    order_placed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    vendor_order_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
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

    vendor = relationship("Vendor")
    department = relationship("Department")
    pr = relationship("PRHeader")
    lines: Mapped[List["POLineItem"]] = relationship(
        "POLineItem", back_populates="header", cascade="all, delete-orphan", order_by="POLineItem.line_number"
    )
    audit_logs: Mapped[List["POAuditLog"]] = relationship(
        "POAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="POAuditLog.timestamp"
    )


class POLineItem(Base):
    """
    Purchase Order Line Item.
    """
    __tablename__ = "po_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, ForeignKey("po_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    unit_rate_ex_gst: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=18.0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    header = relationship("POHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class POAuditLog(Base):
    """
    Audit log for PO lifecycle transitions.
    """
    __tablename__ = "po_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, ForeignKey("po_headers.id", ondelete="CASCADE"), nullable=False, index=True)
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

    header = relationship("POHeader", back_populates="audit_logs")
