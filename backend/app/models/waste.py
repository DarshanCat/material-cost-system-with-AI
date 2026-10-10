"""
Waste Disposition Models.
Tracks foundry scrap, returns, borings, gatings, and runner/riser dispositions.
Disposition types: SCRAP_OUTWARD, INTERNAL_RECOVERY, INSPECTION_HOLD.
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


class WasteType(str, Enum):
    BORINGS = "BORINGS"
    GATINGS_RUNNERS = "GATINGS_RUNNERS"
    RETURNS = "RETURNS"
    REJECTED_CASTINGS = "REJECTED_CASTINGS"
    SLAG = "SLAG"
    OTHER_SCRAP = "OTHER_SCRAP"


class DispositionType(str, Enum):
    INTERNAL_RECOVERY = "INTERNAL_RECOVERY"  # Remelting inside foundry
    SCRAP_OUTWARD = "SCRAP_OUTWARD"          # Sold or moved off premises
    INSPECTION_HOLD = "INSPECTION_HOLD"      # Awaiting metallurgical/QA review


class WasteStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class WasteDispositionHeader(Base):
    """
    Waste Disposition Header transaction record.
    Document numbering convention: WST-YYYYMMDD-XXXX.
    """
    __tablename__ = "waste_disposition_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    waste_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    disposition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    waste_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    disposition_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    source_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    destination_notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WasteStatus.DRAFT.value, index=True)
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

    source_department = relationship("Department")
    lines: Mapped[List["WasteDispositionLineItem"]] = relationship(
        "WasteDispositionLineItem", back_populates="header", cascade="all, delete-orphan", order_by="WasteDispositionLineItem.line_number"
    )
    audit_logs: Mapped[List["WasteAuditLog"]] = relationship(
        "WasteAuditLog", back_populates="header", cascade="all, delete-orphan", order_by="WasteAuditLog.timestamp"
    )


class WasteDispositionLineItem(Base):
    """
    Waste Disposition Line Item record.
    Quantities stored as NUMERIC(15, 4).
    """
    __tablename__ = "waste_disposition_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    waste_id: Mapped[int] = mapped_column(Integer, ForeignKey("waste_disposition_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    header = relationship("WasteDispositionHeader", back_populates="lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")


class WasteAuditLog(Base):
    """Audit log for Waste Disposition lifecycle."""
    __tablename__ = "waste_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    waste_id: Mapped[int] = mapped_column(Integer, ForeignKey("waste_disposition_headers.id", ondelete="CASCADE"), nullable=False, index=True)
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

    header = relationship("WasteDispositionHeader", back_populates="audit_logs")
