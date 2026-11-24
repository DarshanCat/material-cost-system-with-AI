from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20, description="Department code (e.g. PAT, LAB)")
    name: str = Field(..., min_length=2, max_length=100, description="Department name (e.g. Pattern Shop)")


class DepartmentRead(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
