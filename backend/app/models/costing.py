"""
Costing and Inventory Valuation Data Models.
Implements Weighted-Average Costing, Inventory Valuation Snapshots,
Heat Material Costing, Part Costing, and Cost Calculation Journals for VSPL.
Strictly uses NUMERIC(15, 4) for rates/quantities and NUMERIC(15, 2) for valuations.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DenominatorPolicy(str, Enum):
    METAL_TAPPED = "METAL_TAPPED"
    GOOD_CASTING_KG = "GOOD_CASTING_KG"


class CostScope(str, Enum):
    MATERIAL_ONLY = "MATERIAL_ONLY"
    BURDENED_MANUFACTURING = "BURDENED_MANUFACTURING"


class OpeningValuationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class ValuationStatus(str, Enum):
    VALUED = "VALUED"
    UNVALUED_NO_RATE = "UNVALUED_NO_RATE"
    OPENING_VALUATION_MISSING = "OPENING_VALUATION_MISSING"
    NEGATIVE_STOCK_FLAG = "NEGATIVE_STOCK_FLAG"
    ZERO_STOCK = "ZERO_STOCK"
    UNINITIALIZED = "UNINITIALIZED"
    POLICY_PENDING = "POLICY_PENDING"
    INSUFFICIENT_COST_DATA = "INSUFFICIENT_COST_DATA"


class HeatCostStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL_COST = "PARTIAL_COST"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    INSUFFICIENT_COST_DATA = "INSUFFICIENT_COST_DATA"


class PartCostStatus(str, Enum):
    CALCULATED = "CALCULATED"
    MISSING_WEIGHT = "MISSING_WEIGHT"
    INVALID_UOM = "INVALID_UOM"
    INSUFFICIENT_COST_DATA = "INSUFFICIENT_COST_DATA"
    POLICY_PENDING = "POLICY_PENDING"


class CostingRunStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class CostingRun(Base):
    """
    Versioned, immutable Costing Run header.
    A new run never erases prior results.
    """
    __tablename__ = "costing_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(20), default="v1.0.0", nullable=False)
    
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    denominator_policy: Mapped[str] = mapped_column(
        String(30), default=DenominatorPolicy.METAL_TAPPED.value, nullable=False
    )
    internal_recovery_policy: Mapped[str] = mapped_column(String(30), default="POLICY_PENDING", nullable=False)
    cost_scope: Mapped[str] = mapped_column(
        String(30), default=CostScope.MATERIAL_ONLY.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=CostingRunStatus.IN_PROGRESS.value, nullable=False, index=True
    )
    
    # Run Summary Metrics
    total_items_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valued_items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unvalued_items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_inventory_valuation: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    
    total_heats_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_heats_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_heats_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_heat_material_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    
    summary_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    item_snapshots: Mapped[List["ItemCostSnapshot"]] = relationship(
        "ItemCostSnapshot", back_populates="costing_run", cascade="all, delete-orphan"
    )
    heat_costs: Mapped[List["HeatCostRecord"]] = relationship(
        "HeatCostRecord", back_populates="costing_run", cascade="all, delete-orphan"
    )
    part_costs: Mapped[List["PartCostRecord"]] = relationship(
        "PartCostRecord", back_populates="costing_run", cascade="all, delete-orphan"
    )
    journal_entries: Mapped[List["ItemCostJournalEntry"]] = relationship(
        "ItemCostJournalEntry", back_populates="costing_run", cascade="all, delete-orphan"
    )


class ItemCostSnapshot(Base):
    """
    Auditable snapshot of an item's quantity balance, reconstructed weighted-average rate,
    and extended inventory value as of a run's cutoff date.
    """
    __tablename__ = "item_cost_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    costing_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("costing_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    inventory_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    weighted_average_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    extended_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    valuation_status: Mapped[str] = mapped_column(
        String(30), default=ValuationStatus.VALUED.value, nullable=False, index=True
    )
    uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False)
    rate_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    anomaly_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    costing_run = relationship("CostingRun", back_populates="item_snapshots")
    material_item = relationship("MaterialItem")
    uom = relationship("UOM")

    __table_args__ = (
        Index("ix_item_snapshot_run_item", "costing_run_id", "material_item_id", unique=True),
    )


class ItemCostJournalEntry(Base):
    """
    Auditable step-by-step movement cost journal tracking weighted-average rate evolution.
    Preserves exact historical calculation inputs and outputs for audit verification.
    """
    __tablename__ = "item_cost_journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    costing_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("costing_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=False, index=True
    )
    stock_ledger_entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("stock_ledger_entries.id"), nullable=True, index=True
    )
    
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    running_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    
    receipt_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    applied_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    resulting_average_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    
    movement_extended_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    cumulative_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    status: Mapped[str] = mapped_column(String(30), default="APPLIED", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    costing_run = relationship("CostingRun", back_populates="journal_entries")
    material_item = relationship("MaterialItem")
    stock_ledger_entry = relationship("StockLedgerEntry")

    __table_args__ = (
        Index("ix_cost_journal_item_tx", "material_item_id", "transaction_date"),
    )


class HeatCostRecord(Base):
    """
    Induction Furnace Heat Cost record.
    Captures total material charge cost and cost per kg of liquid metal tapped.
    NOTE: Heat costing NEVER creates stock movements.
    """
    __tablename__ = "heat_cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    costing_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("costing_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_headers.id"), nullable=False, index=True
    )
    heat_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    heat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    total_charged_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), default=Decimal("0.0000"), nullable=False
    )
    total_material_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    
    metal_tapped_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    cost_denominator_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    denominator_type: Mapped[str] = mapped_column(
        String(30), default=DenominatorPolicy.METAL_TAPPED.value, nullable=False
    )
    cost_per_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    
    cost_scope: Mapped[str] = mapped_column(
        String(30), default=CostScope.MATERIAL_ONLY.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default=HeatCostStatus.COMPLETE.value, nullable=False, index=True
    )
    
    total_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valued_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unvalued_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    costing_run = relationship("CostingRun", back_populates="heat_costs")
    heat = relationship("HeatHeader")
    lines: Mapped[List["HeatCostLine"]] = relationship(
        "HeatCostLine", back_populates="heat_cost_record", cascade="all, delete-orphan"
    )
    part_costs: Mapped[List["PartCostRecord"]] = relationship(
        "PartCostRecord", back_populates="heat_cost_record", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_heat_cost_run_heat", "costing_run_id", "heat_id", unique=True),
    )


class HeatCostLine(Base):
    """
    Line-level charge cost breakdown for a heat.
    Records applicable rate as of heat date and rate source.
    """
    __tablename__ = "heat_cost_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    heat_cost_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_cost_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heat_charge_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_charge_lines.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    material_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=True, index=True
    )
    raw_material_description: Mapped[str] = mapped_column(String(255), nullable=False)
    charged_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    
    applicable_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    line_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    rate_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    is_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="VALUED", nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    heat_cost_record = relationship("HeatCostRecord", back_populates="lines")
    heat_charge_line = relationship("HeatChargeLine")
    material_item = relationship("MaterialItem")


class PartCostRecord(Base):
    """
    Part Material Cost calculation based on unit cast weight and heat cost per kg.
    Provisional material-only cost; does not create finished-goods movements.
    """
    __tablename__ = "part_cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    costing_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("costing_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heat_cost_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_cost_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heat_parts_produced_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_parts_produced.id"), nullable=False, index=True
    )
    
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    part_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=True, index=True
    )
    
    quantity_produced: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unit_cast_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    weight_uom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=True)
    
    cost_per_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    part_material_cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    total_part_material_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    cost_scope: Mapped[str] = mapped_column(
        String(30), default=CostScope.MATERIAL_ONLY.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default=PartCostStatus.CALCULATED.value, nullable=False, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    costing_run = relationship("CostingRun", back_populates="part_costs")
    heat_cost_record = relationship("HeatCostRecord", back_populates="part_costs")
    heat_parts_produced = relationship("HeatPartsProduced")
    part_item = relationship("MaterialItem")
    weight_uom = relationship("UOM")


class ItemOpeningValuation(Base):
    """
    Explicitly approved opening stock valuation rates for 12 October 2026.
    Resolves missing opening rates when management provides authorized valuations.
    Versioned and auditable with maker-checker controls (SW-06).
    """
    __tablename__ = "item_opening_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    baseline_date: Mapped[date] = mapped_column(Date, default=date(2026, 10, 12), nullable=False)
    
    opening_rate_ex_gst: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default=OpeningValuationStatus.PROPOSED.value, nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    superseded_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("item_opening_valuations.id"), nullable=True
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    material_item = relationship("MaterialItem")
    superseded_by = relationship("ItemOpeningValuation", remote_side=[id])
    audit_logs: Mapped[List["ItemOpeningValuationAuditLog"]] = relationship(
        "ItemOpeningValuationAuditLog",
        back_populates="valuation",
        cascade="all, delete-orphan",
        order_by="ItemOpeningValuationAuditLog.timestamp",
    )

    __table_args__ = (
        UniqueConstraint("material_item_id", "version", name="uq_opening_valuation_item_version"),
        Index("ix_opening_valuation_item", "material_item_id"),
        Index("ix_opening_valuation_status", "status"),
    )


class ItemOpeningValuationAuditLog(Base):
    """Audit log for Item Opening Valuation lifecycle (SW-06)."""
    __tablename__ = "item_opening_valuation_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    valuation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("item_opening_valuations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    valuation = relationship("ItemOpeningValuation", back_populates="audit_logs")
