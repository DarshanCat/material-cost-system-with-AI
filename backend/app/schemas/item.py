from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ItemCategoryRead(BaseModel):
    # `category` is the stored category text (the standard category name, e.g. 'Bolts & Nuts'), usable as
    # the `category` filter of GET /items.
    category: str
    code: str
    name: str
    description: str
    department_code: Optional[str] = None
    cost_head: Optional[str] = None


class MaterialItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    subcategory: Optional[str] = Field(None, max_length=50)
    reconciliation_category: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    # Required when renaming (description correction) or retiring / reactivating; recorded in item history.
    change_reason: Optional[str] = Field(None, max_length=1000)


class ItemCodeRegistryRead(BaseModel):
    item_code: str
    department_code: str
    category_code: str
    serial: int
    item_request_id: Optional[int] = None
    standard_version: str
    issued_by: str
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemHistoryEventRead(BaseModel):
    id: int
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    item_request_id: Optional[int] = None
    actor_id: str
    actor_role: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemHistoryResponse(BaseModel):
    item_id: int
    item_code: str
    registry_installed: bool
    # None for items that predate the generator (loaded or created before revision 008).
    registry: Optional[ItemCodeRegistryRead] = None
    events: List[ItemHistoryEventRead] = []


class MaterialItemRead(BaseModel):
    id: int
    item_code: str
    name: str
    department_id: int
    category: str
    subcategory: Optional[str] = None
    reconciliation_category: Optional[str] = None
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
