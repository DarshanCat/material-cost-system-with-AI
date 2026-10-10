"""
Pydantic Schemas for Waste Disposition.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.waste import WasteType, DispositionType, WasteStatus


class WasteDispositionLineItemBase(BaseModel):
    line_number: int = Field(..., ge=1)
    material_item_id: int
    uom_id: int
    quantity: Decimal = Field(..., gt=0)
    reason: Optional[str] = None
    remarks: Optional[str] = None


class WasteDispositionLineItemCreate(WasteDispositionLineItemBase):
    pass


class WasteDispositionLineItemResponse(WasteDispositionLineItemBase):
    id: int
    waste_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WasteAuditLogResponse(BaseModel):
    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class WasteDispositionCreate(BaseModel):
    disposition_date: date
    waste_type: WasteType
    disposition_type: DispositionType
    source_department_id: int
    destination_notes: Optional[str] = None
    notes: Optional[str] = None
    lines: List[WasteDispositionLineItemCreate] = Field(..., min_length=1)


class WasteDispositionResponse(BaseModel):
    id: int
    waste_number: str
    disposition_date: date
    waste_type: str
    disposition_type: str
    source_department_id: int
    source_department_name: Optional[str] = None
    destination_notes: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[WasteDispositionLineItemResponse] = []
    audit_logs: List[WasteAuditLogResponse] = []
    validation_warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class WasteStatusAction(BaseModel):
    comments: Optional[str] = None
