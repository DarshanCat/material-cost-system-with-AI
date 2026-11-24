"""
Pydantic Schemas for Goods Receipt Notes (GRN).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.grn import GRNSourceType, GRNStatus


class GRNLineItemBase(BaseModel):
    line_number: int = Field(..., ge=1)
    material_item_id: int
    uom_id: int
    quantity: Decimal = Field(..., gt=0)
    rate_ex_gst: Optional[Decimal] = Field(None, ge=0)
    gst_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    remarks: Optional[str] = None


class GRNLineItemCreate(GRNLineItemBase):
    pass


class GRNLineItemResponse(GRNLineItemBase):
    id: int
    grn_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GRNAuditLogResponse(BaseModel):
    id: int
    action: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class GRNCreate(BaseModel):
    receipt_date: date
    source_type: GRNSourceType = GRNSourceType.EXTERNAL_VENDOR
    vendor_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = None
    invoice_date: Optional[date] = None
    reference_document: Optional[str] = None
    notes: Optional[str] = None
    lines: List[GRNLineItemCreate] = Field(..., min_length=1)

    @field_validator("vendor_id")
    @classmethod
    def validate_vendor_for_external(cls, v, info):
        source = info.data.get("source_type")
        if source == GRNSourceType.EXTERNAL_VENDOR and not v:
            raise ValueError("Vendor reference is mandatory for EXTERNAL_VENDOR receipts.")
        return v


class GRNUpdate(BaseModel):
    receipt_date: Optional[date] = None
    vendor_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = None
    invoice_date: Optional[date] = None
    reference_document: Optional[str] = None
    notes: Optional[str] = None
    lines: Optional[List[GRNLineItemCreate]] = None


class GRNResponse(BaseModel):
    id: int
    grn_number: str
    receipt_date: date
    source_type: str
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    vendor_invoice_no: Optional[str] = None
    invoice_date: Optional[date] = None
    reference_document: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[GRNLineItemResponse] = []
    audit_logs: List[GRNAuditLogResponse] = []
    validation_warnings: List[str] = []
    quality_document_number: Optional[str] = None
    quality_inspection_status: Optional[str] = None
    quality_inspection_notes: Optional[str] = None
    quality_inspected_by: Optional[str] = None
    quality_inspected_at: Optional[datetime] = None
    payment_status: Optional[str] = None
    amount_paid: Optional[Decimal] = None
    payment_reference: Optional[str] = None
    payment_date: Optional[date] = None
    payment_mode: Optional[str] = None
    payment_notes: Optional[str] = None
    paid_by: Optional[str] = None
    payable_total: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class GRNStatusAction(BaseModel):
    comments: Optional[str] = None
    quality_document_number: Optional[str] = None
    quality_inspection_status: Optional[str] = None
    quality_inspection_notes: Optional[str] = None


class GRNQualityAction(BaseModel):
    """Result of the Quality team's inspection of a submitted GRN."""
    quality_inspection_status: str  # PASSED | CONDITIONALLY_ACCEPTED | REJECTED
    quality_document_number: Optional[str] = Field(None, max_length=100)
    quality_inspection_notes: Optional[str] = Field(None, max_length=2000)


class GRNPaymentAction(BaseModel):
    """One payment against an approved GRN (the server decides PAID / PARTIALLY_PAID from the amounts)."""
    amount_paid: Decimal = Field(..., gt=0, max_digits=15, decimal_places=2)
    payment_reference: str = Field(..., min_length=1, max_length=100)
    payment_date: Optional[date] = None
    payment_mode: str = "NEFT_RTGS"
    payment_notes: Optional[str] = Field(None, max_length=1000)
