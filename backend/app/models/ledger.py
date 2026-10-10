"""
Stock Ledger Data Models.
Authoritative, append-only inventory journal for Vijay Spheroidals Pvt. Ltd. (VSPL).
Quantities strictly stored as NUMERIC(15, 4).
"""

from datetime import date, datetime, timezone
from enum import Enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MovementType(str, Enum):
    OPENING_BALANCE = "OPENING_BALANCE"
    INWARD_RECEIPT = "INWARD_RECEIPT"
    INTERNAL_INWARD = "INTERNAL_INWARD"
    OUTWARD_ISSUE = "OUTWARD_ISSUE"
    SCRAP_OUTWARD = "SCRAP_OUTWARD"
    INTERNAL_RECOVERY = "INTERNAL_RECOVERY"
    PHYSICAL_AUDIT_ADJUSTMENT = "PHYSICAL_AUDIT_ADJUSTMENT"
    REVERSAL = "REVERSAL"


class SourceDocumentType(str, Enum):
    GRN = "GRN"
    ISSUE = "ISSUE"
    WASTE = "WASTE"
    OPENING_BALANCE = "OPENING_BALANCE"
    AUDIT_ADJUSTMENT = "AUDIT_ADJUSTMENT"
    MANUAL_REVERSAL = "MANUAL_REVERSAL"


class StockLedgerEntry(Base):
    """
    Immutable, append-only stock movement entry.
    Ordinary application workflows cannot UPDATE or DELETE rows in this table.
    """
    __tablename__ = "stock_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    posting_group_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    
    material_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=False, index=True)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    
    # Source Document Traceability
    source_document_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_line_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_document_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    posted_by: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Reversal Tracking
    reversal_of_entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("stock_ledger_entries.id"), nullable=True, index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")
    original_entry = relationship("StockLedgerEntry", remote_side=[id], foreign_keys=[reversal_of_entry_id])

    __table_args__ = (
        # Idempotency constraint: A specific line of a source document cannot be posted more than once
        UniqueConstraint("source_document_type", "source_line_id", name="uq_source_doc_line_posting"),
        Index("ix_ledger_item_date", "material_item_id", "transaction_date"),
    )
