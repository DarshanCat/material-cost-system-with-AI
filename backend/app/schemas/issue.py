"""
Pydantic Schemas for Material Issues.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.issue import IssueStatus


class MaterialIssueLineItemBase(BaseModel):
    line_number: int = Field(..., ge=1)
    material_item_id: int
    uom_id: int
    quantity: Decimal = Field(..., gt=0)
    remarks: Optional[str] = None


class MaterialIssueLineItemCreate(MaterialIssueLineItemBase):
    pass


class MaterialIssueLineItemResponse(MaterialIssueLineItemBase):
    id: int
    issue_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IssueAuditLogResponse(BaseModel):
    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialIssueCreate(BaseModel):
    issue_date: date
    issuing_department_id: int
    receiving_department_id: int
    heat_reference_number: Optional[str] = None
    notes: Optional[str] = None
    lines: List[MaterialIssueLineItemCreate] = Field(..., min_length=1)

    @field_validator("heat_reference_number")
    @classmethod
    def normalize_heat_number(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean = v.strip().upper()
            if not clean.startswith("H-") and not clean.startswith("HEAT-"):
                return f"H-{clean}"
            return clean
        return None


class MaterialIssueUpdate(BaseModel):
    issue_date: Optional[date] = None
    issuing_department_id: Optional[int] = None
    receiving_department_id: Optional[int] = None
    heat_reference_number: Optional[str] = None
    notes: Optional[str] = None
    lines: Optional[List[MaterialIssueLineItemCreate]] = None


class MaterialIssueResponse(BaseModel):
    id: int
    issue_slip_number: str
    issue_date: date
    issuing_department_id: int
    issuing_department_name: Optional[str] = None
    receiving_department_id: int
    receiving_department_name: Optional[str] = None
    heat_reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[MaterialIssueLineItemResponse] = []
    audit_logs: List[IssueAuditLogResponse] = []
    validation_warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class IssueStatusAction(BaseModel):
    comments: Optional[str] = None
