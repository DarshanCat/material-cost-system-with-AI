"""
Goods Receipt Note (GRN) Models.
Supports external vendor receipts, internal VSPL movements, and segregation yard inward.
Quantities and financial values strictly stored as NUMERIC (Decimal).
"""

from datetime import date, datetime, timezone
from enum import Enum
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    Boolean,
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


class GRNSourceType(str, Enum):
    EXTERNAL_VENDOR = "EXTERNAL_VENDOR"
    INTERNAL_VSPL = "INTERNAL_VSPL"
    SEGREGATION_YARD = "SEGREGATION_YARD"


class GRNStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    REVERSED = "REVERSED"


class GRNHeader(Base):
    """
    GRN Header transaction record.
    Document numbering follows convention: GRN-YYYYMMDD-XXXX.
    """
    __tablename__ = "grn_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default=GRNSourceType.EXTERNAL_VENDOR.value)
    
    # Vendor references (mandatory for EXTERNAL_VENDOR, optional for internal)
    vendor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("vendors.id"), nullable=True, index=True
    )
    vendor_invoice_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    reference_document: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=GRNStatus.DRAFT.value, index=True)
    
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

    # Quality inspection (recorded by the Quality role while the GRN is SUBMITTED; gates approval)
    quality_document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quality_inspection_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    quality_inspection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_inspected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quality_inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Payment (recorded by the Accounts role once the GRN is APPROVED)
    payment_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    amount_paid: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    payment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    vendor = relationship("Vendor", backref="grns")
    lines: Mapped[List["GRNLineItem"]] = relationship(
        "GRNLineItem", back_populates="header", cascade="all, delete-orphan", order_by="GRNLineItem.line_number"
    )
    audit_logs: Mapped[List["GRNAuditLog"]] = relationship(
        "GRNAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="GRNAuditLog.timestamp"
    )

    __table_args__ = (
        Index("ix_grn_vendor_invoice", "vendor_id", "vendor_invoice_no", "invoice_date"),
    )


class GRNLineItem(Base):
    """
    GRN Line Item record.
    Stores precise Decimal quantities and pre-GST rates.
    """
    __tablename__ = "grn_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(Integer, ForeignKey("grn_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    # Quantities stored as NUMERIC(15, 4)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    
    # Rate per UOM excluding GST stored as NUMERIC(15, 2)
    rate_ex_gst: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    # GST percentage stored as NUMERIC(5, 2)
    gst_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    header = relationship("GRNHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class GRNAuditLog(Base):
    """Audit log for GRN transitions and administrative actions."""
    __tablename__ = "grn_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(Integer, ForeignKey("grn_headers.id", ondelete="CASCADE"), nullable=False, index=True)
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

    header = relationship("GRNHeader", back_populates="audit_logs")


class GRNAttachment(Base):
    """A supporting document (vendor invoice, delivery challan, test certificate, photo) attached to a GRN.

    The file itself lives in the attachment store (local folder or Cloud Storage); this row is its record. Rows are
    never edited; a document is removed (DRAFT only) or kept for the life of the GRN. Every add and remove is also
    written to the GRN audit log."""
    __tablename__ = "grn_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(Integer, ForeignKey("grn_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
