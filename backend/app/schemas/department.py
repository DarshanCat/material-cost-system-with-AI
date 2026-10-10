from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DepartmentRead(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
