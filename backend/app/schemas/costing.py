"""
Pydantic Schemas for Phase 6 Costing, Inventory Valuation, and Financial Runs.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Inventory Valuation Schemas ---

class ItemValuationResponse(BaseModel):
    material_item_id: int
    item_code: str
    item_name: str
    department_name: Optional[str] = None
    category: str
    inventory_quantity: Decimal
    uom_code: str
    weighted_average_rate: Optional[Decimal] = None
    extended_value: Optional[Decimal] = None
    as_of_date: date
    valuation_status: str
    rate_source: Optional[str] = None
    anomaly_notes: Optional[str] = None


class InventoryValuationReport(BaseModel):
    as_of_date: date
    total_items: int
    valued_items_count: int
    unvalued_items_count: int
    zero_stock_items_count: int
    negative_stock_items_count: int
    total_inventory_valuation: Decimal
    items: List[ItemValuationResponse]


# --- Item Cost History & Reconstruction Schemas ---

class ItemCostJournalStep(BaseModel):
    stock_ledger_entry_id: Optional[int] = None
    entry_number: Optional[str] = None
    transaction_date: date
    movement_type: str
    quantity_delta: Decimal
    running_quantity: Decimal
    receipt_rate: Optional[Decimal] = None
    applied_rate: Optional[Decimal] = None
    resulting_average_rate: Optional[Decimal] = None
    movement_extended_value: Optional[Decimal] = None
    cumulative_value: Optional[Decimal] = None
    status: str
    notes: Optional[str] = None


class ItemRateHistoryResponse(BaseModel):
    material_item_id: int
    item_code: str
    item_name: str
    uom_code: str
    current_quantity: Decimal
    weighted_average_rate: Optional[Decimal] = None
    valuation_status: str
    rate_source: Optional[str] = None
    steps: List[ItemCostJournalStep]


# --- Heat Costing Schemas ---

class HeatCostLineResponse(BaseModel):
    heat_charge_line_id: int
    line_number: int
    material_item_id: Optional[int] = None
    canonical_item_code: Optional[str] = None
    canonical_item_name: Optional[str] = None
    raw_material_description: str
    charged_quantity: Decimal
    applicable_rate: Optional[Decimal] = None
    line_cost: Optional[Decimal] = None
    rate_source: Optional[str] = None
    is_included: bool
    status: str
    remarks: Optional[str] = None


class HeatCostResponse(BaseModel):
    heat_id: int
    heat_number: str
    heat_date: date
    furnace_id: Optional[str] = None
    total_charged_quantity: Decimal
    total_material_cost: Decimal
    metal_tapped_weight: Optional[Decimal] = None
    cost_denominator_value: Optional[Decimal] = None
    denominator_type: str
    cost_per_kg: Optional[Decimal] = None
    cost_scope: str
    status: str
    total_lines: int
    valued_lines: int
    unvalued_lines: int
    lines: List[HeatCostLineResponse] = []


# --- Part Costing Schemas ---

class PartCostResponse(BaseModel):
    heat_parts_produced_id: int
    part_number: str
    part_name: str
    part_item_id: Optional[int] = None
    quantity_produced: Decimal
    unit_cast_weight: Optional[Decimal] = None
    cost_per_kg: Optional[Decimal] = None
    part_material_cost_per_unit: Optional[Decimal] = None
    total_part_material_cost: Optional[Decimal] = None
    cost_scope: str
    status: str
    notes: Optional[str] = None


# --- Opening Valuation Versioning & Approval Schemas (SW-06) ---

class OpeningValuationAuditLogResponse(BaseModel):
    id: int
    valuation_id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime


class ItemOpeningValuationCreate(BaseModel):
    material_item_id: int
    baseline_date: date = Field(default_factory=lambda: date(2026, 10, 12))
    opening_rate_ex_gst: Decimal = Field(..., gt=0, description="Proposed unit rate excluding GST")
    notes: Optional[str] = None


class ItemOpeningValuationResponse(BaseModel):
    id: int
    material_item_id: int
    item_code: str
    item_name: str
    version: int = 1
    baseline_date: date
    opening_rate_ex_gst: Optional[Decimal] = None
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    superseded_by_id: Optional[int] = None
    superseded_at: Optional[datetime] = None
    notes: Optional[str] = None
    audit_logs: Optional[List[OpeningValuationAuditLogResponse]] = None


class OpeningValuationActionRequest(BaseModel):
    comments: Optional[str] = None


class OpeningValuationRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Mandatory audit justification for rejection")


# --- Costing Run Schemas ---

class CostingRunTriggerRequest(BaseModel):
    period_start: date = Field(default_factory=lambda: date(2026, 10, 12))
    period_end: date = Field(default_factory=lambda: date.today())
    as_of_date: date = Field(default_factory=lambda: date.today())
    denominator_policy: str = Field(default="METAL_TAPPED")
    notes: Optional[str] = None


class CostingRunSummaryResponse(BaseModel):
    id: int
    run_number: str
    calculation_version: str
    period_start: date
    period_end: date
    as_of_date: date
    denominator_policy: str
    cost_scope: str
    status: str
    total_items_evaluated: int
    valued_items_count: int
    unvalued_items_count: int
    total_inventory_valuation: Decimal
    total_heats_evaluated: int
    completed_heats_count: int
    partial_heats_count: int
    total_heat_material_cost: Decimal
    summary_notes: Optional[str] = None
    created_by: str
    created_at: datetime


class CostingRunDetailResponse(CostingRunSummaryResponse):
    item_snapshots: List[ItemValuationResponse] = []
    heat_costs: List[HeatCostResponse] = []
    part_costs: List[PartCostResponse] = []


class CostingRunComparisonResponse(BaseModel):
    summary: Dict[str, Any]
    item_differences: List[Dict[str, Any]]
