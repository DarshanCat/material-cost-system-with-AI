"""
Pydantic schemas for Return to Store (RTS).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class MaterialReturnLineCreate(BaseModel):
    material_item_id: int
    uom_id: int
    quantity: Decimal = Field(..., gt=0)
    condition: str = "UNUSED_GOOD"
    remarks: Optional[str] = None


class MaterialReturnLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    return_id: int
    line_number: int
    material_item_id: int
    uom_id: int
    quantity: Decimal
    condition: str
    remarks: Optional[str] = None
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_code: Optional[str] = None


class MaterialReturnAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime


class MaterialReturnCreate(BaseModel):
    returning_department_id: int
    receiving_department_id: Optional[int] = None
    return_date: Optional[date] = None
    reference_issue_id: Optional[int] = None
    heat_reference_number: Optional[str] = None
    condition: str = "UNUSED_GOOD"
    notes: Optional[str] = None
    lines: List[MaterialReturnLineCreate] = Field(..., min_length=1)


class MaterialReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    return_number: str
    return_date: date
    returning_department_id: int
    returning_department_name: Optional[str] = None
    receiving_department_id: int
    receiving_department_name: Optional[str] = None
    reference_issue_id: Optional[int] = None
    heat_reference_number: Optional[str] = None
    condition: str
    status: str
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_by: str
    accepted_by: Optional[str] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    lines: List[MaterialReturnLineResponse] = []
    audit_logs: List[MaterialReturnAuditResponse] = []


class MaterialReturnRejectRequest(BaseModel):
    comments: str = Field(..., min_length=3)
