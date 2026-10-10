from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ItemRequestCreate(BaseModel):
    requested_name: str = Field(..., min_length=2, max_length=255)
    proposed_department_id: int
    proposed_category: str = Field(..., min_length=2, max_length=50)
    proposed_subcategory: Optional[str] = Field(None, max_length=50)
    proposed_uom_id: int
    justification: str = Field(..., min_length=5)


class ItemRequestUpdate(BaseModel):
    requested_name: str = Field(..., min_length=2, max_length=255)
    proposed_department_id: int
    proposed_category: str = Field(..., min_length=2, max_length=50)
    proposed_subcategory: Optional[str] = Field(None, max_length=50)
    proposed_uom_id: int
    justification: str = Field(..., min_length=5)


class ItemRequestDecision(BaseModel):
    comments: Optional[str] = None


class ItemRequestAuditLogRead(BaseModel):
    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    actor_role: str
    comments: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemRequestRead(BaseModel):
    id: int
    request_number: str
    requested_name: str
    proposed_department_id: int
    proposed_category: str
    proposed_subcategory: Optional[str] = None
    proposed_uom_id: int
    justification: str

    requester_id: str
    requester_role: str
    requester_department: str

    status: str
    submitted_at: Optional[datetime] = None

    reviewer_id: Optional[str] = None
    decision_at: Optional[datetime] = None
    decision_comments: Optional[str] = None

    linked_item_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Display helper attributes
    department_name: Optional[str] = None
    uom_code: Optional[str] = None
    linked_item_code: Optional[str] = None

    audit_logs: List[ItemRequestAuditLogRead] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedRequestsResponse(BaseModel):
    items: List[ItemRequestRead]
    total: int
    page: int
    size: int
