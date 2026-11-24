from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class UOMCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, description="UOM code (e.g. PCS, DRUM, M3)")
    name: str = Field(..., min_length=1, max_length=100, description="Unit name (e.g. Pieces, Drums, Cubic Meter)")
    decimal_precision: int = Field(0, ge=0, le=4, description="Permitted decimal precision (0 to 4 decimals)")


class UOMRead(BaseModel):
    id: int
    code: str
    name: str
    decimal_precision: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
