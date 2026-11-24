"""
Purchase Requests API Endpoints - Layer 1 Governance (SCM Planning -> Plant Head Approval)
"""

from typing import List, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.security import AuthenticatedUser, Permission, require_permission, UserRole, get_current_user_context
from app.db.session import get_db
from app.models.purchase_request import PRHeader, PRLineItem, PRAuditLog, PRStatus
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.purchase_request import (
    PRCreate,
    PRResponse,
    PRLineResponse,
    PRStatusAction,
)

router = APIRouter()


def _format_pr_response(pr: PRHeader, db: Session) -> PRResponse:
    dept = db.query(Department).filter(Department.id == pr.department_id).first()
    dept_name = dept.name if dept else "General"

    lines_out: List[PRLineResponse] = []
    for l in pr.lines:
        item = db.query(MaterialItem).filter(MaterialItem.id == l.material_item_id).first()
        u = db.query(UOM).filter(UOM.id == l.uom_id).first()
        lines_out.append(
            PRLineResponse(
                id=l.id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                item_code=item.item_code if item else "",
                item_name=item.name if item else "",
                uom_id=l.uom_id,
                uom_code=u.code if u else "KG",
                quantity=float(l.quantity),
                estimated_rate=float(l.estimated_rate) if l.estimated_rate is not None else None,
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
        for log in pr.audit_logs
    ]

    return PRResponse(
        id=pr.id,
        pr_number=pr.pr_number,
        department_id=pr.department_id,
        department_name=dept_name,
        requisitioner_id=pr.requisitioner_id,
        requisitioner_role=pr.requisitioner_role,
        request_date=pr.request_date,
        target_date=pr.target_date,
        justification=pr.justification,
        status=pr.status,
        plant_head_approved_by=pr.plant_head_approved_by,
        plant_head_approved_at=pr.plant_head_approved_at,
        rejection_reason=pr.rejection_reason,
        created_by=pr.created_by,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
        lines=lines_out,
        audit_logs=logs_out,
    )


@router.get("/", response_model=List[PRResponse])
def list_purchase_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """List purchase requests with optional status filter."""
    query = db.query(PRHeader)
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(PRHeader.status == status_filter.upper())
    prs = query.order_by(desc(PRHeader.id)).all()
    return [_format_pr_response(pr, db) for pr in prs]


@router.post("/", response_model=PRResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_request(
    payload: PRCreate,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Create a new Purchase Request (PR).
    Under VSPL Governance, PR is raised by SCM / Planning with mandatory operational justification.
    """
    if not payload.justification or len(payload.justification.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mandatory justification required. State operational necessity under financial control audit rules."
        )

    if not payload.lines or len(payload.lines) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one material line item is required."
        )

    today = date.today()
    target_dt = payload.target_date or today

    # Count existing for sequence
    count_today = db.query(PRHeader).count() + 1
    pr_num = f"PR-{today.strftime('%Y%m')}-{str(count_today).padStart(4, '0')}" if hasattr(str, 'padStart') else f"PR-{today.strftime('%Y%m')}-{count_today:04d}"

    new_pr = PRHeader(
        pr_number=pr_num,
        department_id=payload.department_id,
        requisitioner_id=user.user_id,
        requisitioner_role="SCM / Planning" if user.role == UserRole.PURCHASE else user.role.value,
        request_date=today,
        target_date=target_dt,
        justification=payload.justification.strip(),
        status=PRStatus.SUBMITTED.value,
        created_by=user.user_id,
    )
    db.add(new_pr)
    db.flush()

    for idx, l in enumerate(payload.lines, 1):
        line = PRLineItem(
            pr_id=new_pr.id,
            line_number=idx,
            material_item_id=l.material_item_id,
            uom_id=l.uom_id,
            quantity=l.quantity,
            estimated_rate=l.estimated_rate,
            remarks=l.remarks,
        )
        db.add(line)

    audit = PRAuditLog(
        pr_id=new_pr.id,
        action="SUBMITTED",
        from_status=PRStatus.DRAFT.value,
        to_status=PRStatus.SUBMITTED.value,
        actor_id=user.user_id,
        comments="Submitted for Plant Head Layer-1 review",
    )
    db.add(audit)
    db.commit()
    db.refresh(new_pr)

    return _format_pr_response(new_pr, db)


@router.get("/{pr_id}", response_model=PRResponse)
def get_purchase_request(
    pr_id: int,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Get single PR details."""
    pr = db.query(PRHeader).filter(PRHeader.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase Request not found")
    return _format_pr_response(pr, db)


@router.post("/{pr_id}/approve", response_model=PRResponse)
def approve_pr_by_plant_head(
    pr_id: int,
    action: PRStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Layer 1: Plant Head Approval.
    Authorizes SCM / Purchase to proceed with generating a Purchase Order (PO).
    """
    if user.role not in {UserRole.MANAGEMENT, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Plant Head / Management / Admin has authorization to approve Purchase Requests."
        )

    pr = db.query(PRHeader).filter(PRHeader.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase Request not found")

    if pr.status not in {PRStatus.SUBMITTED.value, PRStatus.DRAFT.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PR cannot be approved from current status {pr.status}"
        )

    now = datetime.now(timezone.utc)
    old_status = pr.status
    pr.status = PRStatus.APPROVED.value
    pr.plant_head_approved_by = user.user_id
    pr.plant_head_approved_at = now

    audit = PRAuditLog(
        pr_id=pr.id,
        action="PLANT_HEAD_APPROVED",
        from_status=old_status,
        to_status=PRStatus.APPROVED.value,
        actor_id=user.user_id,
        comments=action.comments or "Approved by Plant Head - Authorized for PO creation",
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(pr)

    return _format_pr_response(pr, db)


@router.post("/{pr_id}/reject", response_model=PRResponse)
def reject_pr_by_plant_head(
    pr_id: int,
    action: PRStatusAction,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Plant Head rejects the Purchase Request with mandatory reason.
    """
    if user.role not in {UserRole.MANAGEMENT, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Plant Head / Management / Admin can reject Purchase Requests."
        )

    pr = db.query(PRHeader).filter(PRHeader.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase Request not found")

    reason = action.comments or "Rejected by Plant Head"
    now = datetime.now(timezone.utc)
    old_status = pr.status
    pr.status = PRStatus.REJECTED.value
    pr.rejection_reason = reason

    audit = PRAuditLog(
        pr_id=pr.id,
        action="PLANT_HEAD_REJECTED",
        from_status=old_status,
        to_status=PRStatus.REJECTED.value,
        actor_id=user.user_id,
        comments=reason,
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(pr)

    return _format_pr_response(pr, db)
