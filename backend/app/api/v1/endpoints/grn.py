"""
Goods Receipt Note (GRN) API Endpoints.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.grn import (
    GRNCreate,
    GRNResponse,
    GRNLineItemResponse,
    GRNAuditLogResponse,
    GRNStatusAction,
)
from app.models.grn import GRNHeader, GRNLineItem
from app.services.grn_service import create_grn, submit_grn, approve_grn, cancel_grn

router = APIRouter()


def _serialize_grn(header: GRNHeader, warnings: Optional[List[str]] = None) -> GRNResponse:
    lines = []
    for l in header.lines:
        lines.append(
            GRNLineItemResponse(
                id=l.id,
                grn_id=l.grn_id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                uom_id=l.uom_id,
                quantity=l.quantity,
                rate_ex_gst=l.rate_ex_gst,
                gst_percent=l.gst_percent,
                remarks=l.remarks,
                item_code=l.material_item.item_code if l.material_item else None,
                item_name=l.material_item.name if l.material_item else None,
                uom_code=l.uom.code if l.uom else None,
            )
        )
    audits = [
        GRNAuditLogResponse(
            id=a.id,
            action=a.action,
            from_status=a.from_status,
            to_status=a.to_status,
            actor_id=a.actor_id,
            comments=a.comments,
            timestamp=a.timestamp,
        )
        for a in header.audit_logs
    ]

    return GRNResponse(
        id=header.id,
        grn_number=header.grn_number,
        receipt_date=header.receipt_date,
        source_type=header.source_type,
        vendor_id=header.vendor_id,
        vendor_name=header.vendor.name if header.vendor else None,
        vendor_invoice_no=header.vendor_invoice_no,
        invoice_date=header.invoice_date,
        reference_document=header.reference_document,
        notes=header.notes,
        status=header.status,
        created_by=header.created_by,
        created_at=header.created_at,
        updated_at=header.updated_at,
        lines=lines,
        audit_logs=audits,
        validation_warnings=warnings or [],
    )


@router.post("/", response_model=GRNResponse, status_code=status.HTTP_201_CREATED)
def create_new_grn(
    payload: GRNCreate,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    header, warnings = create_grn(db, payload, user.user_id)
    return _serialize_grn(header, warnings)


@router.get("/", response_model=List[GRNResponse])
def list_grns(
    status: Optional[str] = Query(None, description="Filter by GRN status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    from_date: Optional[date] = Query(None, description="Filter receipt date from"),
    to_date: Optional[date] = Query(None, description="Filter receipt date to"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    query = select(GRNHeader).order_by(desc(GRNHeader.created_at))
    if status:
        query = query.where(GRNHeader.status == status.upper())
    if source_type:
        query = query.where(GRNHeader.source_type == source_type.upper())
    if from_date:
        query = query.where(GRNHeader.receipt_date >= from_date)
    if to_date:
        query = query.where(GRNHeader.receipt_date <= to_date)

    query = query.offset(skip).limit(limit)
    headers = db.execute(query).scalars().all()
    return [_serialize_grn(h) for h in headers]


@router.get("/{grn_id}", response_model=GRNResponse)
def get_grn_by_id(
    grn_id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    grn = db.get(GRNHeader, grn_id)
    if not grn:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="GRN not found")
    return _serialize_grn(grn)


@router.post("/{grn_id}/submit", response_model=GRNResponse)
def submit_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    grn = submit_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)


@router.post("/{grn_id}/approve", response_model=GRNResponse)
def approve_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    grn = approve_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)


@router.post("/{grn_id}/cancel", response_model=GRNResponse)
def cancel_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    grn = cancel_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)
