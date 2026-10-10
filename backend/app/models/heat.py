"""
Induction Furnace Heat Log Models.
Supports Heat Headers, Charge Details, and Parts Produced.
Document numbering follows H-XXXXXX-XXXX where applicable.
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


class ProductionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class HeatChargeValidationStatus(str, Enum):
    VALID = "VALID"
    UNMAPPED_ALIAS = "UNMAPPED_ALIAS"
    SUSPECT_QTY = "SUSPECT_QTY"


class CastingClassification(str, Enum):
    GOOD = "GOOD"
    REJECTED = "REJECTED"
    REWORK = "REWORK"


class HeatHeader(Base):
    """
    Induction Furnace Heat Header record.
    Represents a single melting batch in an induction furnace.
    """
    __tablename__ = "heat_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    heat_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    original_heat_number: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_heat_number: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    
    heat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    furnace_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    shift: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    metal_tapped_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    metal_tapped_uom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=True)
    
    production_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProductionStatus.COMPLETED.value, index=True
    )
    source_document_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
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

    metal_tapped_uom = relationship("UOM")
    
    charge_lines: Mapped[List["HeatChargeLine"]] = relationship(
        "HeatChargeLine",
        back_populates="heat",
        cascade="all, delete-orphan",
        order_by="HeatChargeLine.line_number",
    )
    parts_produced: Mapped[List["HeatPartsProduced"]] = relationship(
        "HeatPartsProduced",
        back_populates="heat",
        cascade="all, delete-orphan",
        order_by="HeatPartsProduced.line_number",
    )

    __table_args__ = (
        Index("ix_heat_date_furnace", "heat_date", "furnace_id"),
    )


class HeatChargeLine(Base):
    """
    Heat Charge Detail record.
    Tracks raw materials, pig iron, scrap, and alloys charged into the furnace for this heat.
    NOTE: Heat charge details NEVER create stock movements.
    """
    __tablename__ = "heat_charge_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    heat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_headers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Optional link to material item; populated once alias is resolved
    material_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=True, index=True
    )
    original_material_description: Mapped[str] = mapped_column(String(255), nullable=False)
    
    charged_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    
    source_row_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=HeatChargeValidationStatus.VALID.value, index=True
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    heat = relationship("HeatHeader", back_populates="charge_lines")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")

    __table_args__ = (
        Index("ix_heat_charge_heat_line", "heat_id", "line_number", unique=True),
    )


class HeatPartsProduced(Base):
    """
    Parts and castings produced from this heat.
    Tracks production yields without computing finished goods cost or movements.
    """
    __tablename__ = "heat_parts_produced"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    heat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_headers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    part_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=True, index=True
    )
    original_part_description: Mapped[str] = mapped_column(String(255), nullable=False)
    
    quantity_produced: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unit_cast_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    weight_uom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=True)
    
    classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CastingClassification.GOOD.value, index=True
    )
    source_row_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    heat = relationship("HeatHeader", back_populates="parts_produced")
    part_item = relationship("MaterialItem")
    weight_uom = relationship("UOM")

    __table_args__ = (
        Index("ix_heat_parts_heat_line", "heat_id", "line_number", unique=True),
    )
