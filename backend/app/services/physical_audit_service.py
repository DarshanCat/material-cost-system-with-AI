"""
Physical Inventory Stock Audit Service.
Calculates variance = (Physical Count - System Balance at Cutoff) and
posts approved adjustments to the stock ledger.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.physical_audit import (
    PhysicalAuditHeader,
    PhysicalAuditLine,
    PhysicalAuditAuditLog,
    AuditStatus,
)
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.schemas.physical_audit import PhysicalAuditCreate
from app.services.ledger_service import get_material_stock_balance, post_audit_adjustment_to_ledger


def generate_audit_number(db: Session, audit_date: date) -> str:
    """Generates sequential document serial: AUD-YYYYMMDD-XXXX."""
    date_str = audit_date.strftime("%Y%m%d")
    prefix = f"AUD-{date_str}-"
    
    count_today = db.execute(
        select(func.count(PhysicalAuditHeader.id)).where(PhysicalAuditHeader.audit_number.like(f"{prefix}%"))
    ).scalar_one()
    
    return f"{prefix}{count_today + 1:04d}"


def create_physical_audit(
    db: Session,
    data: PhysicalAuditCreate,
    created_by: str,
) -> PhysicalAuditHeader:
    """
    Creates draft physical inventory count record.
    Calculates system balance as of audit cutoff date and variance.
    """
    audit_num = generate_audit_number(db, data.audit_date)

    header = PhysicalAuditHeader(
        audit_number=audit_num,
        audit_date=data.audit_date,
        department_id=data.department_id,
        notes=data.notes,
        status=AuditStatus.DRAFT.value,
        created_by=created_by,
    )
    db.add(header)
    db.flush()

    for idx, line in enumerate(data.lines, start=1):
        item = db.get(MaterialItem, line.material_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: Material item ID {line.material_item_id} not found.",
            )
        uom = db.get(UOM, line.uom_id)
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: UOM ID {line.uom_id} not found.",
            )

        # Compute system quantity at audit cutoff date
        sys_qty, _, _, _ = get_material_stock_balance(db, line.material_item_id, as_of_date=data.audit_date)
        
        # Variance formula: Physical Count - System Quantity
        variance = line.physical_quantity - sys_qty

        audit_line = PhysicalAuditLine(
            audit_id=header.id,
            line_number=idx,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            system_quantity=sys_qty,
            physical_quantity=line.physical_quantity,
            variance=variance,
            reason=line.reason,
            remarks=line.remarks,
        )
        db.add(audit_line)

    audit_log = PhysicalAuditAuditLog(
        audit_id=header.id,
        action="CREATED",
        from_status=None,
        to_status=AuditStatus.DRAFT.value,
        actor_id=created_by,
        comments="Physical audit recorded with calculated cutoff variances.",
    )
    db.add(audit_log)
    db.commit()
    db.refresh(header)
    return header


def submit_physical_audit(
    db: Session,
    audit_id: int,
    actor_id: str,
    comments: Optional[str] = None,
) -> PhysicalAuditHeader:
    audit = db.get(PhysicalAuditHeader, audit_id)
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical audit not found.")
    if audit.status != AuditStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit audit in status '{audit.status}'. Only DRAFT can be submitted.",
        )

    prev_status = audit.status
    audit.status = AuditStatus.SUBMITTED.value
    log = PhysicalAuditAuditLog(
        audit_id=audit.id,
        action="SUBMITTED",
        from_status=prev_status,
        to_status=audit.status,
        actor_id=actor_id,
        comments=comments or "Physical audit submitted for management review.",
    )
    db.add(log)
    db.commit()
    db.refresh(audit)
    return audit


def approve_physical_audit(
    db: Session,
    audit_id: int,
    actor_id: str,
    comments: Optional[str] = None,
) -> PhysicalAuditHeader:
    """
    Approves physical audit and atomically posts variance adjustment entries to stock ledger.
    """
    audit = db.get(PhysicalAuditHeader, audit_id)
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical audit not found.")
    if audit.status != AuditStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve audit in status '{audit.status}'. Must be SUBMITTED first.",
        )

    prev_status = audit.status
    audit.status = AuditStatus.APPROVED.value
    log = PhysicalAuditAuditLog(
        audit_id=audit.id,
        action="APPROVED",
        from_status=prev_status,
        to_status=audit.status,
        actor_id=actor_id,
        comments=comments or "Physical audit approved. Posting variance adjustments to stock ledger.",
    )
    db.add(log)
    db.flush()

    # Atomically post to stock ledger
    post_audit_adjustment_to_ledger(db, audit, actor_id)

    db.commit()
    db.refresh(audit)
    return audit
