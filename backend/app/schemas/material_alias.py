"""
Pydantic schemas for Material Description Alias Master.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class MaterialAliasCreate(BaseModel):
    alias_text: str = Field(..., min_length=1, max_length=255)
    material_item_id: int
    status: str = "APPROVED"


class MaterialAliasReview(BaseModel):
    decision_notes: Optional[str] = None


class MaterialAliasReject(BaseModel):
    decision_notes: str = Field(..., min_length=1)


class MaterialAliasAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias_id: int
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime


class MaterialAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias_text: str
    normalized_alias_key: str
    material_item_id: int
    is_active: bool
    status: str
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    audit_logs: List[MaterialAliasAuditLogRead] = []
