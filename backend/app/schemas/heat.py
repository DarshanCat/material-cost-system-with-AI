"""
Pydantic schemas for Induction Furnace Heat Log and charge details.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class HeatChargeLineCreate(BaseModel):
    original_material_description: str = Field(..., min_length=1, max_length=255)
    charged_quantity: Decimal = Field(..., gt=0)
    uom_id: int
    material_item_id: Optional[int] = None
    source_row_reference: Optional[str] = None
    remarks: Optional[str] = None


class HeatChargeLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    heat_id: int
    line_number: int
    material_item_id: Optional[int] = None
    original_material_description: str
    charged_quantity: Decimal
    uom_id: int
    validation_status: str
    source_row_reference: Optional[str] = None
    remarks: Optional[str] = None


class HeatPartsProducedCreate(BaseModel):
    original_part_description: str = Field(..., min_length=1, max_length=255)
    quantity_produced: Decimal = Field(..., gt=0)
    unit_cast_weight: Optional[Decimal] = None
    weight_uom_id: Optional[int] = None
    part_item_id: Optional[int] = None
    classification: str = "GOOD"
    source_row_reference: Optional[str] = None
    remarks: Optional[str] = None


class HeatPartsProducedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    heat_id: int
    line_number: int
    part_item_id: Optional[int] = None
    original_part_description: str
    quantity_produced: Decimal
    unit_cast_weight: Optional[Decimal] = None
    weight_uom_id: Optional[int] = None
    classification: str
    source_row_reference: Optional[str] = None
    remarks: Optional[str] = None


class HeatCreate(BaseModel):
    heat_number: str = Field(..., min_length=1, max_length=50)
    heat_date: date
    furnace_id: Optional[str] = None
    shift: Optional[str] = None
    metal_tapped_weight: Optional[Decimal] = None
    metal_tapped_uom_id: Optional[int] = None
    production_status: str = "COMPLETED"
    source_document_reference: Optional[str] = None
    notes: Optional[str] = None
    charge_lines: Optional[List[HeatChargeLineCreate]] = None
    parts_produced: Optional[List[HeatPartsProducedCreate]] = None


class HeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    heat_number: str
    original_heat_number: str
    normalized_heat_number: str
    heat_date: date
    furnace_id: Optional[str] = None
    shift: Optional[str] = None
    metal_tapped_weight: Optional[Decimal] = None
    metal_tapped_uom_id: Optional[int] = None
    production_status: str
    source_document_reference: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    charge_lines: List[HeatChargeLineRead] = []
    parts_produced: List[HeatPartsProducedRead] = []
