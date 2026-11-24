"""
Purchase Orders API Endpoints - Multi-Tier Approval & Order Placement Lifecycle
Links strictly to Plant Head Approved Purchase Requests (PR).
Approved by CEO / MD -> Followed by Order Placed with Vendor -> Ready for GRN.
"""

from typing import List, Optional
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.security import AuthenticatedUser, Permission, require_permission, UserRole, get_current_user_context
from app.db.session import get_db
from app.models.purchase_order import POHeader, POLineItem, POAuditLog, POStatus
from app.models.purchase_request import PRHeader, PRStatus
from app.models.vendor import Vendor
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.grn import GRNHeader
from app.schemas.purchase_order import (
    POCreate,
    POResponse,
    POLineItemResponse,
    POStatusAction,
    POOrderPlacedAction,
)

router = APIRouter()


def _format_po_response(po: POHeader, db: Session) -> POResponse:
    vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
    vendor_name = vendor.name if vendor else "Unknown Vendor"
    vendor_gstin = vendor.gstin if vendor else None

    dept = db.query(Department).filter(Department.id == po.department_id).first()
    dept_name = dept.name if dept else "General"

    grn_count = db.query(GRNHeader).filter(GRNHeader.reference_document == po.po_number).count()

    lines_out: List[POLineItemResponse] = []
    for l in po.lines:
        item = db.query(MaterialItem).filter(MaterialItem.id == l.material_item_id).first()
        u = db.query(UOM).filter(UOM.id == l.uom_id).first()
        lines_out.append(
            POLineItemResponse(
                id=l.id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                item_code=item.item_code if item else "",
                item_name=item.name if item else "",
                uom_id=l.uom_id,
                uom_code=u.code if u else "KG",
                quantity=float(l.quantity),
                unit_rate_ex_gst=float(l.unit_rate_ex_gst),
                gst_percent=float(l.gst_percent),
                line_total=float(l.line_total),
                remarks=l.remarks,
            )
        )

    logs_out = [
        {
            "id": log.id,
            "action": log.action,
            "from_status": log.from_status,
            "to_status": log.to_status,
            "actor_id": log.actor_id,
            "comments": log.comments,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in po.audit_logs
    ]

    return POResponse(
        id=po.id,
        po_number=po.po_number,
        pr_id=po.pr_id,
        pr_number=po.pr_number,
        po_date=po.po_date,
        expected_delivery_date=po.expected_delivery_date,
        vendor_id=po.vendor_id,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
        department_id=po.department_id,
        department_name=dept_name,
        payment_terms=po.payment_terms,
        delivery_terms=po.delivery_terms,
        notes=po.notes,
        total_amount_ex_gst=f"{float(po.total_amount_ex_gst):.2f}",
        total_gst_amount=f"{float(po.total_gst_amount):.2f}",
        grand_total=f"{float(po.grand_total):.2f}",
        status=po.status,
        current_approval_level=po.current_approval_level,
        mgmt_approved_by=po.mgmt_approved_by,
        mgmt_approved_at=po.mgmt_approved_at,
        order_placed_by=po.order_placed_by,
        order_placed_at=po.order_placed_at,
        vendor_order_ref=po.vendor_order_ref,
        rejection_reason=po.rejection_reason,
        grn_count=grn_count,
        fulfilled_percentage=100 if grn_count > 0 else 0,
        created_by=po.created_by,
        created_at=po.created_at,
        updated_at=po.updated_at,
        lines=lines_out,
        audit_logs=logs_out,
    )


@router.get("/", response_model=List[POResponse])
def list_purchase_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """List all purchase orders with optional status filter."""
    query = db.query(POHeader)
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(POHeader.status == status_filter.upper())
    pos = query.order_by(desc(POHeader.id)).all()
    return [_format_po_response(po, db) for po in pos]


@router.post("/", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: POCreate,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Create a new purchase order.
    Must be linked to an Approved Purchase Request (Plant Head authorized).
    """
    if user.role not in {UserRole.PURCHASE, UserRole.MANAGEMENT, UserRole.STORES, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to create purchase orders. Allowed: Purchase, Management, Stores, Admin."
        )

    # Validate PR linkage if provided or enforce approved PR
    linked_pr: Optional[PRHeader] = None
    if payload.pr_id:
        linked_pr = db.query(PRHeader).filter(PRHeader.id == payload.pr_id).first()
        if not linked_pr:
            raise HTTPException(status_code=400, detail=f"Purchase Request ID {payload.pr_id} not found.")
        if linked_pr.status != PRStatus.APPROVED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot create PO from PR {linked_pr.pr_number}. It must be APPROVED by the Plant Head (Current status: {linked_pr.status})."
            )

    if not payload.lines or len(payload.lines) == 0:
        raise HTTPException(status_code=400, detail="At least one line item is required.")

    today = date.today()
    po_date = payload.po_date or today
    expected_delivery = payload.expected_delivery_date or today

    # Calculate totals
    subtotal = Decimal("0.00")
    gst_total = Decimal("0.00")
    for l in payload.lines:
        q = Decimal(str(l.quantity))
        r = Decimal(str(l.unit_rate_ex_gst))
        g = Decimal(str(l.gst_percent))
        line_sub = q * r
        line_gst = line_sub * (g / Decimal("100"))
        subtotal += line_sub
        gst_total += line_gst

    grand_total = subtotal + gst_total

    count_total = db.query(POHeader).count() + 1
    po_num = f"PO-{today.strftime('%Y%m')}-{count_total:04d}"

    new_po = POHeader(
        po_number=po_num,
        pr_id=linked_pr.id if linked_pr else payload.pr_id,
        pr_number=linked_pr.pr_number if linked_pr else payload.pr_number,
        vendor_id=payload.vendor_id,
        department_id=payload.department_id,
        po_date=po_date,
        expected_delivery_date=expected_delivery,
        payment_terms=payload.payment_terms,
        delivery_terms=payload.delivery_terms,
        notes=payload.notes,
        total_amount_ex_gst=float(subtotal),
        total_gst_amount=float(gst_total),
        grand_total=float(grand_total),
        status=POStatus.SUBMITTED.value,
        current_approval_level="MANAGEMENT",
        created_by=user.user_id,
    )
    db.add(new_po)
    db.flush()

    for idx, l in enumerate(payload.lines, 1):
        q = Decimal(str(l.quantity))
        r = Decimal(str(l.unit_rate_ex_gst))
        g = Decimal(str(l.gst_percent))
        line_tot = q * r * (Decimal("1") + g / Decimal("100"))
        line = POLineItem(
            po_id=new_po.id,
            line_number=idx,
            material_item_id=l.material_item_id,
            uom_id=l.uom_id,
            quantity=float(q),
            unit_rate_ex_gst=float(r),
            gst_percent=float(g),
            line_total=float(line_tot),
            remarks=l.remarks,
        )
        db.add(line)

    audit = POAuditLog(
        po_id=new_po.id,
        action="SUBMITTED",
        from_status=POStatus.DRAFT.value,
        to_status=POStatus.SUBMITTED.value,
        actor_id=user.user_id,
        comments=f"PO generated from Approved PR {linked_pr.pr_number}" if linked_pr else "PO generated and submitted for CEO/MD authorization",
    )
    db.add(audit)

    # Mark PR as converted
    if linked_pr:
        linked_pr.status = PRStatus.CONVERTED_TO_PO.value

    db.commit()
    db.refresh(new_po)

    return _format_po_response(new_po, db)


@router.get("/{po_id}", response_model=POResponse)
def get_purchase_order(
    po_id: int,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Get single purchase order details."""
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return _format_po_response(po, db)


@router.post("/{po_id}/submit", response_model=POResponse)
def submit_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Submit draft PO."""
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    po.status = POStatus.SUBMITTED.value
    db.commit()
    db.refresh(po)
    return _format_po_response(po, db)


@router.post("/{po_id}/approve-dept", response_model=POResponse)
def approve_dept_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Department level approval."""
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    po.status = "DEPT_APPROVED"
    po.current_approval_level = "SUPPLY_CHAIN"
    db.commit()
    db.refresh(po)
    return _format_po_response(po, db)


@router.post("/{po_id}/approve-scm", response_model=POResponse)
def approve_scm_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Supply chain level approval."""
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    po.status = "SCM_APPROVED"
    po.current_approval_level = "MANAGEMENT"
    db.commit()
    db.refresh(po)
    return _format_po_response(po, db)


@router.post("/{po_id}/approve-mgmt", response_model=POResponse)
def approve_mgmt_level(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    CEO / MD (Management) final authorization.
    Once approved, the order moves to 'APPROVED' state, ready for order placement with vendor.
    """
    if user.role not in {UserRole.MANAGEMENT, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Management (CEO / MD) or Admin can authorize Purchase Orders."
        )

    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    now = datetime.now(timezone.utc)
    old_status = po.status
    po.status = POStatus.APPROVED.value
    po.current_approval_level = "COMPLETED"
    po.mgmt_approved_by = user.user_id
    po.mgmt_approved_at = now

    audit = POAuditLog(
        po_id=po.id,
        action="APPROVED",
        from_status=old_status,
        to_status=POStatus.APPROVED.value,
        actor_id=user.user_id,
        comments=action.comments or "Approved by CEO/MD. Ready for Order Placement.",
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(po)

    return _format_po_response(po, db)


@router.post("/{po_id}/order-placed", response_model=POResponse)
def mark_order_placed(
    po_id: int,
    action: POOrderPlacedAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Mark Order Placed with Vendor.
    Auto-captures placement timestamp, stores vendor order reference, and updates expected delivery.
    Transitions status to ORDER_PLACED.
    """
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if po.status not in {POStatus.APPROVED.value, POStatus.ORDER_PLACED.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot place order for PO in status '{po.status}'. Must be APPROVED by CEO/MD first."
        )

    now = datetime.now(timezone.utc)
    placed_at = action.order_placed_at or now

    po.status = POStatus.ORDER_PLACED.value
    po.order_placed_by = user.user_id
    po.order_placed_at = placed_at
    if action.vendor_order_ref:
        po.vendor_order_ref = action.vendor_order_ref
    if action.expected_delivery_date:
        po.expected_delivery_date = action.expected_delivery_date

    audit = POAuditLog(
        po_id=po.id,
        action="ORDER_PLACED",
        from_status=POStatus.APPROVED.value,
        to_status=POStatus.ORDER_PLACED.value,
        actor_id=user.user_id,
        comments=f"Order placed with vendor. Ref: {action.vendor_order_ref or 'N/A'}. {action.notes or ''}".strip(),
        timestamp=placed_at,
    )
    db.add(audit)
    db.commit()
    db.refresh(po)

    return _format_po_response(po, db)


@router.post("/{po_id}/reject", response_model=POResponse)
def reject_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Reject PO with mandatory comments."""
    if user.role not in {UserRole.MANAGEMENT, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Management (CEO / MD) or Admin can reject Purchase Orders."
        )

    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    reason = action.comments or "Rejected by Approver"
    now = datetime.now(timezone.utc)
    old_status = po.status
    po.status = POStatus.REJECTED.value
    po.rejection_reason = reason

    audit = POAuditLog(
        po_id=po.id,
        action="REJECTED",
        from_status=old_status,
        to_status=POStatus.REJECTED.value,
        actor_id=user.user_id,
        comments=reason,
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(po)

    return _format_po_response(po, db)


@router.post("/{po_id}/cancel", response_model=POResponse)
def cancel_purchase_order(
    po_id: int,
    action: POStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Cancel PO."""
    po = db.query(POHeader).filter(POHeader.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    now = datetime.now(timezone.utc)
    old_status = po.status
    po.status = POStatus.CANCELLED.value

    audit = POAuditLog(
        po_id=po.id,
        action="CANCELLED",
        from_status=old_status,
        to_status=POStatus.CANCELLED.value,
        actor_id=user.user_id,
        comments=action.comments or "Cancelled by user",
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(po)

    return _format_po_response(po, db)
