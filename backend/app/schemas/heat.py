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
    
    # Liquid Heel & Furnace Mass-Balance tracking
    opening_liquid_heel_kg: Optional[Decimal] = Field(None, ge=0)
    closing_liquid_heel_kg: Optional[Decimal] = Field(None, ge=0)
    heel_measurement_method: Optional[str] = None
    is_cold_start: bool = False
    is_furnace_empty: bool = False
    opening_heel_source_heat_id: Optional[int] = None

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

    # Liquid Heel & Furnace Mass-Balance tracking
    opening_liquid_heel_kg: Optional[Decimal] = None
    closing_liquid_heel_kg: Optional[Decimal] = None
    heel_measurement_method: Optional[str] = None
    heel_recorded_by: Optional[str] = None
    heel_verified_by: Optional[str] = None
    heel_verified_at: Optional[datetime] = None
    heel_verification_status: str = "UNRECORDED"
    is_cold_start: bool = False
    is_furnace_empty: bool = False
    opening_heel_source_heat_id: Optional[int] = None

    created_by: str
    created_at: datetime
    updated_at: datetime
    charge_lines: List[HeatChargeLineRead] = []
    parts_produced: List[HeatPartsProducedRead] = []


class HeelVerificationRequest(BaseModel):
    decision: str = Field(..., pattern="^(VERIFY|REJECT)$")
    comments: Optional[str] = None


class HeelProposeCarryForwardResponse(BaseModel):
    can_carry_forward: bool
    furnace_id: str
    source_heat_id: Optional[int] = None
    source_heat_number: Optional[str] = None
    proposed_opening_heel_kg: Optional[Decimal] = None
    is_cold_start: bool = False
    verification_status: Optional[str] = None
    message: str
