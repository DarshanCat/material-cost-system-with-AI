"""
Waste Disposition API Endpoints.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.waste import (
    WasteDispositionCreate,
    WasteDispositionResponse,
    WasteDispositionLineItemResponse,
    WasteAuditLogResponse,
    WasteStatusAction,
)
from app.models.waste import WasteDispositionHeader
from app.services.waste_service import (
    create_waste_disposition,
    submit_waste_disposition,
    approve_waste_disposition,
)

router = APIRouter()


def _serialize_waste(header: WasteDispositionHeader, warnings: Optional[List[str]] = None) -> WasteDispositionResponse:
    lines = []
    for l in header.lines:
        lines.append(
            WasteDispositionLineItemResponse(
                id=l.id,
                waste_id=l.waste_id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                uom_id=l.uom_id,
                quantity=l.quantity,
                reason=l.reason,
                remarks=l.remarks,
                item_code=l.material_item.item_code if l.material_item else None,
                item_name=l.material_item.name if l.material_item else None,
                uom_code=l.uom.code if l.uom else None,
            )
        )
    audits = [
        WasteAuditLogResponse(
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

    return WasteDispositionResponse(
        id=header.id,
        waste_number=header.waste_number,
        disposition_date=header.disposition_date,
        waste_type=header.waste_type,
        disposition_type=header.disposition_type,
        source_department_id=header.source_department_id,
        source_department_name=header.source_department.name if header.source_department else None,
        destination_notes=header.destination_notes,
        notes=header.notes,
        status=header.status,
        created_by=header.created_by,
        created_at=header.created_at,
        updated_at=header.updated_at,
        lines=lines,
        audit_logs=audits,
        validation_warnings=warnings or [],
    )


@router.post("/", response_model=WasteDispositionResponse, status_code=status.HTTP_201_CREATED)
def create_new_waste(
    payload: WasteDispositionCreate,
    user: AuthenticatedUser = Depends(require_permission(Permission.WASTE_LOG)),
    db: Session = Depends(get_db),
):
    header, warnings = create_waste_disposition(db, payload, user.user_id)
    return _serialize_waste(header, warnings)


@router.get("/", response_model=List[WasteDispositionResponse])
def list_waste_dispositions(
    status: Optional[str] = Query(None),
    waste_type: Optional[str] = Query(None),
    disposition_type: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.WASTE_READ)),
):
    query = select(WasteDispositionHeader).order_by(desc(WasteDispositionHeader.created_at))
    if status:
        query = query.where(WasteDispositionHeader.status == status.upper())
    if waste_type:
        query = query.where(WasteDispositionHeader.waste_type == waste_type.upper())
    if disposition_type:
        query = query.where(WasteDispositionHeader.disposition_type == disposition_type.upper())
    if from_date:
        query = query.where(WasteDispositionHeader.disposition_date >= from_date)
    if to_date:
        query = query.where(WasteDispositionHeader.disposition_date <= to_date)

    query = query.offset(skip).limit(limit)
    headers = db.execute(query).scalars().all()
    return [_serialize_waste(h) for h in headers]


@router.get("/{waste_id}", response_model=WasteDispositionResponse)
def get_waste_by_id(
    waste_id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.WASTE_READ)),
):
    waste = db.get(WasteDispositionHeader, waste_id)
    if not waste:
        raise HTTPException(status_code=404, detail="Waste disposition record not found")
    return _serialize_waste(waste)


@router.post("/{waste_id}/submit", response_model=WasteDispositionResponse)
def submit_waste_action(
    waste_id: int,
    action: WasteStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.WASTE_LOG)),
    db: Session = Depends(get_db),
):
    waste = submit_waste_disposition(db, waste_id, user.user_id, action.comments)
    return _serialize_waste(waste)


@router.post("/{waste_id}/approve", response_model=WasteDispositionResponse)
def approve_waste_action(
    waste_id: int,
    action: WasteStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.WASTE_APPROVE)),
    db: Session = Depends(get_db),
):
    waste = approve_waste_disposition(db, waste_id, user.user_id, action.comments)
    return _serialize_waste(waste)
