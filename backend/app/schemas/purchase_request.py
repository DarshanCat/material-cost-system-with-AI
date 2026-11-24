"""
Purchase Request Pydantic Schemas for SCM Planning and Plant Head Layer-1 Authorization.
"""

from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class PRLineCreate(BaseModel):
    line_number: int
    material_item_id: int
    uom_id: int
    quantity: float
    estimated_rate: Optional[float] = None
    remarks: Optional[str] = None


class PRLineResponse(BaseModel):
    id: Optional[int] = None
    line_number: int
    material_item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_id: int
    uom_code: Optional[str] = None
    quantity: float
    estimated_rate: Optional[float] = None
    remarks: Optional[str] = None


class PRCreate(BaseModel):
    department_id: int
    target_date: Optional[date] = None
    justification: str
    lines: List[PRLineCreate] = []


class PRStatusAction(BaseModel):
    comments: Optional[str] = None


class PRResponse(BaseModel):
    id: int
    pr_number: str
    department_id: int
    department_name: str
    requisitioner_id: str
    requisitioner_role: str
    request_date: date
    target_date: date
    justification: str
    status: str
    plant_head_approved_by: Optional[str] = None
    plant_head_approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[PRLineResponse] = []
    audit_logs: List[dict] = []

    model_config = ConfigDict(from_attributes=True)
