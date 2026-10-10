"""
Physical Inventory Stock Audit API Endpoints.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.physical_audit import PhysicalAuditHeader
from app.schemas.physical_audit import (
    PhysicalAuditCreate,
    PhysicalAuditResponse,
    PhysicalAuditLineResponse,
    PhysicalAuditAuditLogResponse,
    PhysicalAuditStatusAction,
)
from app.services.physical_audit_service import (
    create_physical_audit,
    submit_physical_audit,
    approve_physical_audit,
)

router = APIRouter()


def _serialize_audit(audit: PhysicalAuditHeader) -> PhysicalAuditResponse:
    lines = [
        PhysicalAuditLineResponse(
            id=l.id,
            audit_id=l.audit_id,
            line_number=l.line_number,
            material_item_id=l.material_item_id,
            uom_id=l.uom_id,
            system_quantity=l.system_quantity,
            physical_quantity=l.physical_quantity,
            variance=l.variance,
            reason=l.reason,
            remarks=l.remarks,
            item_code=l.material_item.item_code if l.material_item else None,
            item_name=l.material_item.name if l.material_item else None,
            uom_code=l.uom.code if l.uom else None,
        )
        for l in audit.lines
    ]

    audits = [
        PhysicalAuditAuditLogResponse(
            id=a.id,
            action=a.action,
            from_status=a.from_status,
            to_status=a.to_status,
            actor_id=a.actor_id,
            comments=a.comments,
            timestamp=a.timestamp,
        )
        for a in audit.audit_logs
    ]

    return PhysicalAuditResponse(
        id=audit.id,
        audit_number=audit.audit_number,
        audit_date=audit.audit_date,
        department_id=audit.department_id,
        department_name=audit.department.name if audit.department else None,
        status=audit.status,
        notes=audit.notes,
        created_by=audit.created_by,
        created_at=audit.created_at,
        updated_at=audit.updated_at,
        lines=lines,
        audit_logs=audits,
    )


@router.post("/", response_model=PhysicalAuditResponse, status_code=status.HTTP_201_CREATED)
def create_new_physical_audit(
    payload: PhysicalAuditCreate,
    created_by: str = Query("Admin", description="User recording physical count"),
    db: Session = Depends(get_db),
):
    audit = create_physical_audit(db, payload, created_by)
    return _serialize_audit(audit)


@router.get("/", response_model=List[PhysicalAuditResponse])
def list_physical_audits(
    status: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(PhysicalAuditHeader).order_by(desc(PhysicalAuditHeader.created_at))
    if status:
        query = query.where(PhysicalAuditHeader.status == status.upper())
    if department_id:
        query = query.where(PhysicalAuditHeader.department_id == department_id)
    if from_date:
        query = query.where(PhysicalAuditHeader.audit_date >= from_date)
    if to_date:
        query = query.where(PhysicalAuditHeader.audit_date <= to_date)

    audits = db.execute(query.offset(skip).limit(limit)).scalars().all()
    return [_serialize_audit(a) for a in audits]


@router.get("/{audit_id}", response_model=PhysicalAuditResponse)
def get_physical_audit_by_id(audit_id: int, db: Session = Depends(get_db)):
    audit = db.get(PhysicalAuditHeader, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Physical audit record not found.")
    return _serialize_audit(audit)


@router.post("/{audit_id}/submit", response_model=PhysicalAuditResponse)
def submit_physical_audit_action(
    audit_id: int,
    action: PhysicalAuditStatusAction,
    actor_id: str = Query("Admin"),
    db: Session = Depends(get_db),
):
    audit = submit_physical_audit(db, audit_id, actor_id, action.comments)
    return _serialize_audit(audit)


@router.post("/{audit_id}/approve", response_model=PhysicalAuditResponse)
def approve_physical_audit_action(
    audit_id: int,
    action: PhysicalAuditStatusAction,
    actor_id: str = Query("Admin"),
    db: Session = Depends(get_db),
):
    audit = approve_physical_audit(db, audit_id, actor_id, action.comments)
    return _serialize_audit(audit)
