"""
Purchase Order Pydantic Schemas for 3-Tier Approval and P2P Procurement Cycle.
"""

from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class POLineItemCreate(BaseModel):
    line_number: int
    material_item_id: int
    uom_id: int
    quantity: float
    unit_rate_ex_gst: float
    gst_percent: float
    line_total: float
    remarks: Optional[str] = None


class POLineItemResponse(BaseModel):
    id: Optional[int] = None
    line_number: int
    material_item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_id: int
    uom_code: Optional[str] = None
    quantity: float
    unit_rate_ex_gst: float
    gst_percent: float
    line_total: float
    remarks: Optional[str] = None


class POCreate(BaseModel):
    vendor_id: int
    department_id: int
    po_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    payment_terms: str = "Net 30 Days"
    delivery_terms: Optional[str] = "Door Delivery to VSPL Works"
    notes: Optional[str] = None
    lines: List[POLineItemCreate] = []


class POStatusAction(BaseModel):
    comments: Optional[str] = None


class POResponse(BaseModel):
    id: int
    po_number: str
    po_date: date
    expected_delivery_date: date
    vendor_id: int
    vendor_name: str
    vendor_gstin: Optional[str] = None
    department_id: int
    department_name: str
    payment_terms: str
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None
    total_amount_ex_gst: str
    total_gst_amount: str
    grand_total: str
    status: str
    current_approval_level: str
    dept_approved_by: Optional[str] = None
    dept_approved_at: Optional[datetime] = None
    scm_approved_by: Optional[str] = None
    scm_approved_at: Optional[datetime] = None
    mgmt_approved_by: Optional[str] = None
    mgmt_approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    grn_count: Optional[int] = 0
    fulfilled_percentage: Optional[int] = 0
    created_by: str
    created_at: datetime
    updated_at: datetime
    lines: List[POLineItemResponse] = []
    audit_logs: List[dict] = []

    model_config = ConfigDict(from_attributes=True)
