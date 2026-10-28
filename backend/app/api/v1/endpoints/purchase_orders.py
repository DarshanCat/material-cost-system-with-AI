"""
Purchase Orders API Endpoints - Multi-Tier Approval (Department -> Supply Chain -> Management)
"""

from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.purchase_order import (
    POCreate,
    POResponse,
    POStatusAction,
)

router = APIRouter()


@router.get("/", response_model=List[POResponse])
def list_purchase_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
    db: Session = Depends(get_db),
):
    """List all purchase orders with optional status filter."""
    return []


@router.post("/", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: POCreate,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    """Create a new purchase order."""
    now = datetime.now()
    today = date.today()
    return POResponse(
        id=1,
        po_number=f"PO-{today.strftime('%Y%m')}-0001",
        po_date=payload.po_date or today,
        expected_delivery_date=payload.expected_delivery_date or today,
        vendor_id=payload.vendor_id,
        vendor_name="Demo Vendor",
        department_id=payload.department_id,
        department_name="Foundry",
        payment_terms=payload.payment_terms,
        delivery_terms=payload.delivery_terms,
        notes=payload.notes,
        total_amount_ex_gst="0.00",
        total_gst_amount="0.00",
        grand_total="0.00",
        status="DRAFT",
        current_approval_level="DEPARTMENT",
        created_by=user.user_id,
        created_at=now,
        updated_at=now,
        lines=[],
        audit_logs=[],
    )


@router.get("/{po_id}", response_model=POResponse)
def get_purchase_order(
    po_id: int,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
    db: Session = Depends(get_db),
):
    """Get single purchase order details."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/submit", response_model=POResponse)
def submit_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    """Submit draft PO for department HOD review."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/approve-dept", response_model=POResponse)
def approve_dept_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    """Level 1: Requisitioning Department HOD approval."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/approve-scm", response_model=POResponse)
def approve_scm_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    """Level 2: Supply Chain / Purchase Head approval."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/approve-mgmt", response_model=POResponse)
def approve_mgmt_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    """Level 3: Management / Managing Director final authorization."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/reject", response_model=POResponse)
def reject_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    """Reject PO with mandatory comments at any approval tier."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")


@router.post("/{po_id}/cancel", response_model=POResponse)
def cancel_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    """Cancel PO."""
    raise HTTPException(status_code=404, detail="Purchase Order not found")
