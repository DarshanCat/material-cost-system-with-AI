"""
Pydantic Schemas for Heat Log & Furnace-Charge Dry-Run Reconciliation Preview.
Strictly read-only data structures for evaluating Issue-to-Heat bath reconciliation.
"""

from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class ReconciliationVarianceClass(str, Enum):
    OK = "OK"
    SHORT_ISSUE = "SHORT_ISSUE"
    EXCESS_ISSUE = "EXCESS_ISSUE"
    DECIMAL_SUSPECT = "DECIMAL_SUSPECT"
    UNMATCHED_SLIP = "UNMATCHED_SLIP"
    UNMATCHED_HEAT = "UNMATCHED_HEAT"
    UOM_MISMATCH = "UOM_MISMATCH"
    MISSING_CODE = "MISSING_CODE"
    FLOOR_CONSUMABLE = "FLOOR_CONSUMABLE"


class HeatReconciliationLineMatch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    heat_number: str
    heat_date: Optional[str] = None
    item_code: Optional[str] = None
    material_description: str
    uom: str
    issued_quantity: Decimal
    charged_quantity: Decimal
    variance: Decimal
    variance_percentage: Optional[Decimal] = None
    tolerance_limit: Decimal
    variance_class: ReconciliationVarianceClass
    match_method: str
    is_multi_addition: bool = False
    source_file: Optional[str] = None
    notes: str


class HeatReconciliationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_read_only: bool = True
    total_heats_evaluated: int
    matched_heats_count: int
    unmatched_heats_count: int

    total_charge_rows_evaluated: int
    exact_matches_count: int
    tolerance_ok_count: int
    variance_excess_count: int
    variance_short_count: int
    unmatched_charge_lines_count: int
    floor_consumables_segregated_count: int
    zero_qty_lines_suppressed_count: int
    uom_mismatches_count: int
    missing_code_count: int

    total_issued_weight_kg: Decimal
    total_charged_weight_kg: Decimal

    matches: List[HeatReconciliationLineMatch] = []
    message: str
