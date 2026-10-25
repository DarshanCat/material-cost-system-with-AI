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
from app.services.ledger_service import get_material_stock_balance, post_audit_adjustment_to_ledger, _lock_material_items_for_update
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
    supervisor_override: bool = False,
) -> PhysicalAuditHeader:
    with ledger_write_guard(db):
        return _approve_physical_audit(db, audit_id, actor_id, comments, supervisor_override=supervisor_override)


def _approve_physical_audit(
    db: Session,
    audit_id: int,
    actor_id: str,
    comments: Optional[str] = None,
    supervisor_override: bool = False,
) -> PhysicalAuditHeader:
    """
    Approves physical audit and atomically posts variance adjustment entries to stock ledger.
    Revalidates live stock balances and detects stale audit snapshot against cutoff variance (SW-08).
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

    # 1. Lock all material items in deterministic ascending ID order
    all_item_ids = [line.material_item_id for line in audit.lines]
    locked_items = _lock_material_items_for_update(db, all_item_ids)

    # 2. Live revalidation and drift detection (SW-08)
    stale_lines = []
    for line in audit.lines:
        item_id = line.material_item_id
        item = locked_items.get(item_id) or db.get(MaterialItem, item_id)
        item_code = item.item_code if item else f"ID {item_id}"

        live_bal, is_init, _, _ = get_material_stock_balance(db, item_id)
        cutoff_bal_now, _, _, _ = get_material_stock_balance(db, item_id, as_of_date=audit.audit_date)

        cutoff_variance = line.variance  # physical_quantity - system_quantity
        live_discrepancy = line.physical_quantity - live_bal
        drift = live_discrepancy - cutoff_variance

        # Drift exists if live balance has moved from cutoff snapshot, or if backdated entries altered cutoff balance
        if live_bal != line.system_quantity or cutoff_bal_now != line.system_quantity:
            stale_lines.append({
                "item_code": item_code,
                "material_item_id": item_id,
                "cutoff_system_quantity": line.system_quantity,
                "cutoff_variance": cutoff_variance,
                "live_balance": live_bal,
                "live_discrepancy": live_discrepancy,
                "drift": drift,
            })

    if stale_lines and not supervisor_override:
        details = [
            f"Item '{sl['item_code']}': Cutoff balance was {sl['cutoff_system_quantity']} (variance {sl['cutoff_variance']}), "
            f"but live balance is now {sl['live_balance']} (live discrepancy {sl['live_discrepancy']}, drift {sl['drift']})"
            for sl in stale_lines
        ]
        err_msg = (
            f"Physical audit {audit.audit_number} variance revalidation failed: Stale audit snapshot detected. "
            f"Stock has moved since count cutoff date {audit.audit_date}. "
            f"Affected items: {'; '.join(details)}. "
            f"Approval blocked pending supervisor override or re-count."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err_msg,
        )

    if stale_lines and supervisor_override:
        if not comments or not comments.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supervisor override requires explicit comments justifying approval despite variance drift.",
            )
        action_name = "APPROVED_WITH_OVERRIDE"
        log_comments = f"Supervisor override applied by {actor_id}. Variance drift acknowledged. Comments: {comments}"
    else:
        action_name = "APPROVED"
        log_comments = comments or "Physical audit approved. Posting variance adjustments to stock ledger."

    prev_status = audit.status
    audit.status = AuditStatus.APPROVED.value
    log = PhysicalAuditAuditLog(
        audit_id=audit.id,
        action=action_name,
        from_status=prev_status,
        to_status=audit.status,
        actor_id=actor_id,
        comments=log_comments,
    )
    db.add(log)
    db.flush()

    # Atomically post to stock ledger
    post_audit_adjustment_to_ledger(db, audit, actor_id)

    db.commit()
    db.refresh(audit)
    return audit
