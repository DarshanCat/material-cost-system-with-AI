"""
Pydantic Schemas for Physical Inventory Stock Audits.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PhysicalAuditLineBase(BaseModel):
    line_number: int = Field(..., ge=1)
    material_item_id: int
    uom_id: int
    system_quantity: Decimal
    physical_quantity: Decimal = Field(..., ge=0)
    variance: Decimal
    reason: Optional[str] = None
    remarks: Optional[str] = None


class PhysicalAuditLineCreate(BaseModel):
    material_item_id: int
    uom_id: int
    physical_quantity: Decimal = Field(..., ge=0)
    reason: Optional[str] = None
    remarks: Optional[str] = None


class PhysicalAuditLineResponse(PhysicalAuditLineBase):
    id: int
    audit_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PhysicalAuditAuditLogResponse(BaseModel):
    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PhysicalAuditCreate(BaseModel):
    audit_date: date
    department_id: Optional[int] = None
    notes: Optional[str] = None
    lines: List[PhysicalAuditLineCreate] = Field(..., min_length=1)


class PhysicalAuditResponse(BaseModel):
    id: int
    audit_number: str
    audit_date: date
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[PhysicalAuditLineResponse] = []
    audit_logs: List[PhysicalAuditAuditLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PhysicalAuditStatusAction(BaseModel):
    comments: Optional[str] = None
