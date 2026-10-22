"""
Service for Physical Inventory Audits, variance calculation, and ledger adjustments.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.services.maker_checker import enforce_maker_checker, PHYSICAL_AUDIT
from app.services.posting_guard import ledger_write_guard
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
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)


def generate_audit_number(db: Session, audit_date: date) -> str:
    """Generates sequential document serial: AUD-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.AUDIT, audit_date)


def create_physical_audit(
    db: Session,
    data: PhysicalAuditCreate,
    created_by: str,
) -> PhysicalAuditHeader:
    """
    Creates draft physical inventory count record.
    Calculates system balance as of audit cutoff date and variance.
    """
    # 1. Pre-validate lines and calculate variances
    validated_lines = []
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
        variance = line.physical_quantity - sys_qty
        validated_lines.append((idx, line, sys_qty, variance))

    # 2. Create document using bounded savepoint retry for collision safety
    def _create(audit_num: str) -> PhysicalAuditHeader:
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

        for idx, line, sys_qty, variance in validated_lines:
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
        return header

    header = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.AUDIT,
        create_fn=_create,
        target_date=data.audit_date,
    )
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
    with ledger_write_guard(db):
        return _approve_physical_audit(db, audit_id, actor_id, comments)


def _approve_physical_audit(
    db: Session,
    audit_id: int,
    actor_id: str,
    comments: Optional[str] = None,
) -> PhysicalAuditHeader:
    """
    Approves physical audit and atomically posts variance adjustment entries to stock ledger.
    """
    audit = db.get(PhysicalAuditHeader, audit_id, with_for_update=True)
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical audit not found.")
    enforce_maker_checker(PHYSICAL_AUDIT, audit.created_by, actor_id, f"physical audit {audit.audit_number}")
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
