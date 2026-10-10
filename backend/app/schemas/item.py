from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class MaterialItemRead(BaseModel):
    id: int
    item_code: str
    name: str
    department_id: int
    category: str
    subcategory: Optional[str] = None
    base_uom_id: int
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Reference data helper fields
    department_name: Optional[str] = None
    uom_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedItemsResponse(BaseModel):
    items: List[MaterialItemRead]
    total: int
    page: int
    size: int
