from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.services.validators import validate_gstin_format


class VendorCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full legal vendor name")
    gstin: Optional[str] = Field(None, max_length=15, description="15-character Indian GSTIN (optional)")
    address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean = v.strip().upper()
            if not validate_gstin_format(clean):
                raise ValueError(
                    "Invalid GSTIN format. Expected 15-character Indian GSTIN "
                    "(e.g., 29AABCU9603R1Z2). Does NOT verify live registration."
                )
            return clean
        return None


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Updated legal vendor name")
    gstin: Optional[str] = Field(None, max_length=15, description="15-character Indian GSTIN (optional)")
    address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if v:
            clean = v.strip().upper()
            if not validate_gstin_format(clean):
                raise ValueError(
                    "Invalid GSTIN format. Expected 15-character Indian GSTIN "
                    "(e.g., 29AABCU9603R1Z2)."
                )
            return clean
        return None


class VendorRead(BaseModel):
    id: int
    name: str
    normalized_name: str
    gstin: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedVendorsResponse(BaseModel):
    items: List[VendorRead]
    total: int
    page: int
    size: int
