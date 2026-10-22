"""
Authoritative Append-Only Stock Ledger Service.
Handles ledger posting, derived balance calculations, idempotency protection,
and compensating reversals.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc
from fastapi import HTTPException, status

from app.services.posting_guard import ledger_write_guard
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.grn import GRNHeader, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, IssueStatus
from app.models.waste import WasteDispositionHeader, WasteStatus, DispositionType
from app.models.physical_audit import PhysicalAuditHeader, AuditStatus
from app.core.config import settings


def generate_ledger_entry_number(db: Session, tx_date: date) -> str:
    """Generates sequential document serial: STK-YYYYMMDD-XXXX."""
    date_str = tx_date.strftime("%Y%m%d")
    prefix = f"STK-{date_str}-"
    
    count_today = db.execute(
        select(func.count(StockLedgerEntry.id)).where(StockLedgerEntry.entry_number.like(f"{prefix}%"))
    ).scalar_one()
    
    return f"{prefix}{count_today + 1:04d}"


def get_material_stock_balance(
    db: Session,
    material_item_id: int,
    as_of_date: Optional[date] = None,
) -> Tuple[Decimal, bool, Optional[date], int]:
    """
    Computes real-time or historical stock balance strictly from ledger entries:
    Balance = SUM(quantity_delta) up to as_of_date.
    Returns: (balance, is_initialized, last_movement_date, movement_count).
    """
    query = select(StockLedgerEntry).where(StockLedgerEntry.material_item_id == material_item_id)
    if as_of_date:
        query = query.where(StockLedgerEntry.transaction_date <= as_of_date)
        
    entries = db.execute(query.order_by(desc(StockLedgerEntry.transaction_date), desc(StockLedgerEntry.id))).scalars().all()
    
    movement_count = len(entries)
    if movement_count == 0:
        return Decimal("0.0000"), False, None, 0
        
    total = sum((e.quantity_delta for e in entries), Decimal("0.0000"))
    last_date = entries[0].transaction_date
    return total, True, last_date, movement_count


def post_grn_to_ledger(
    db: Session,
    grn: GRNHeader,
    actor_id: str,
) -> List[StockLedgerEntry]:
    """
    Posts approved GRN lines to stock ledger idempotently.
    EXTERNAL_VENDOR -> INWARD_RECEIPT (+quantity)
    INTERNAL_VSPL / SEGREGATION_YARD -> INTERNAL_INWARD (+quantity)
    """
    if grn.status != GRNStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post GRN {grn.grn_number} in status '{grn.status}'. Only APPROVED GRNs can be posted to ledger.",
        )

    # Check if already posted
    existing_postings = db.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.GRN.value,
            StockLedgerEntry.source_document_id == grn.id,
        )
    ).scalars().all()
    
    if existing_postings:
        # Already posted idempotently
        return existing_postings

    posting_group = f"POST-GRN-{grn.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    created_entries: List[StockLedgerEntry] = []
    
    movement_type = (
        MovementType.INWARD_RECEIPT.value
        if grn.source_type == GRNSourceType.EXTERNAL_VENDOR.value
        else MovementType.INTERNAL_INWARD.value
    )

    for line in grn.lines:
        entry_num = generate_ledger_entry_number(db, grn.receipt_date)
        entry = StockLedgerEntry(
            entry_number=entry_num,
            posting_group_id=posting_group,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            transaction_date=grn.receipt_date,
            movement_type=movement_type,
            quantity_delta=abs(line.quantity),  # Strictly positive
            source_document_type=SourceDocumentType.GRN.value,
            source_document_id=grn.id,
            source_line_id=line.id,
            source_document_number=grn.grn_number,
            reference_number=grn.vendor_invoice_no,
            reason=f"Approved GRN receipt ({grn.source_type})",
            posted_by=actor_id,
        )
        db.add(entry)
        created_entries.append(entry)
        db.flush()

    return created_entries


def post_issue_to_ledger(
    db: Session,
    issue: MaterialIssueHeader,
    actor_id: str,
) -> List[StockLedgerEntry]:
    """
    Posts approved Material Issue lines to stock ledger idempotently.
    Enforces negative quantity (-quantity) and negative stock governance.
    """
    if issue.status != IssueStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post issue slip {issue.issue_slip_number} in status '{issue.status}'. Only APPROVED issues can be posted to ledger.",
        )

    # Check if already posted
    existing_postings = db.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == issue.id,
        )
    ).scalars().all()
    
    if existing_postings:
        return existing_postings

    # Negative stock policy verification
    if not settings.ALLOW_NEGATIVE_STOCK:
        for line in issue.lines:
            current_bal, is_init, _, _ = get_material_stock_balance(db, line.material_item_id)
            if not is_init:
                item = db.get(MaterialItem, line.material_item_id)
                item_code = item.item_code if item else f"ID {line.material_item_id}"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot issue material '{item_code}': Stock baseline has not been initialized. Establish opening balance first.",
                )
            if current_bal < line.quantity:
                item = db.get(MaterialItem, line.material_item_id)
                item_code = item.item_code if item else f"ID {line.material_item_id}"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient inventory for '{item_code}': Required {line.quantity}, available {current_bal}. Negative stock is disallowed by VSPL governance policy.",
                )

    posting_group = f"POST-ISS-{issue.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    created_entries: List[StockLedgerEntry] = []

    for line in issue.lines:
        entry_num = generate_ledger_entry_number(db, issue.issue_date)
        entry = StockLedgerEntry(
            entry_number=entry_num,
            posting_group_id=posting_group,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            transaction_date=issue.issue_date,
            movement_type=MovementType.OUTWARD_ISSUE.value,
            quantity_delta=-abs(line.quantity),  # Strictly negative
            source_document_type=SourceDocumentType.ISSUE.value,
            source_document_id=issue.id,
            source_line_id=line.id,
            source_document_number=issue.issue_slip_number,
            reference_number=issue.heat_reference_number,
            reason=f"Approved departmental material issue to {issue.receiving_department.name if issue.receiving_department else 'Dept'}",
            posted_by=actor_id,
        )
        db.add(entry)
        created_entries.append(entry)
        db.flush()

    return created_entries


def post_waste_to_ledger(
    db: Session,
    waste: WasteDispositionHeader,
    actor_id: str,
) -> List[StockLedgerEntry]:
    """
    Posts approved Waste Dispositions to stock ledger idempotently.
    - SCRAP_OUTWARD -> SCRAP_OUTWARD (-quantity)
    - INTERNAL_RECOVERY -> INTERNAL_RECOVERY (recorded with quantity 0 / net-neutral transfer record)
    - INSPECTION_HOLD -> No ledger posting (material remains in custody).
    """
    if waste.status != WasteStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post waste record {waste.waste_number} in status '{waste.status}'. Only APPROVED waste records can be posted.",
        )

    # Inspection hold does not move inventory
    if waste.disposition_type == DispositionType.INSPECTION_HOLD.value:
        return []

    # Check if already posted
    existing_postings = db.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.WASTE.value,
            StockLedgerEntry.source_document_id == waste.id,
        )
    ).scalars().all()
    
    if existing_postings:
        return existing_postings

    posting_group = f"POST-WST-{waste.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    created_entries: List[StockLedgerEntry] = []

    for line in waste.lines:
        if waste.disposition_type == DispositionType.SCRAP_OUTWARD.value:
            m_type = MovementType.SCRAP_OUTWARD.value
            qty_delta = -abs(line.quantity)
        else:
            # INTERNAL_RECOVERY: Tracked retention/remelt transfer
            m_type = MovementType.INTERNAL_RECOVERY.value
            qty_delta = Decimal("0.0000")  # Net-neutral within total pool

        entry_num = generate_ledger_entry_number(db, waste.disposition_date)
        entry = StockLedgerEntry(
            entry_number=entry_num,
            posting_group_id=posting_group,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            transaction_date=waste.disposition_date,
            movement_type=m_type,
            quantity_delta=qty_delta,
            source_document_type=SourceDocumentType.WASTE.value,
            source_document_id=waste.id,
            source_line_id=line.id,
            source_document_number=waste.waste_number,
            reference_number=waste.waste_type,
            reason=f"Approved waste disposition: {waste.disposition_type} ({waste.waste_type})",
            posted_by=actor_id,
        )
        db.add(entry)
        created_entries.append(entry)
        db.flush()

    return created_entries


def post_audit_adjustment_to_ledger(
    db: Session,
    audit: PhysicalAuditHeader,
    actor_id: str,
) -> List[StockLedgerEntry]:
    """
    Posts approved Physical Audit variances as PHYSICAL_AUDIT_ADJUSTMENT entries.
    Quantity delta equals approved line variance (Physical - System).
    """
    if audit.status != AuditStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post audit adjustment in status '{audit.status}'. Only APPROVED audits can be posted.",
        )

    # Check if already posted
    existing_postings = db.execute(
        select(StockLedgerEntry).where(
            StockLedgerEntry.source_document_type == SourceDocumentType.AUDIT_ADJUSTMENT.value,
            StockLedgerEntry.source_document_id == audit.id,
        )
    ).scalars().all()
    
    if existing_postings:
        return existing_postings

    posting_group = f"POST-AUD-{audit.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    created_entries: List[StockLedgerEntry] = []

    for line in audit.lines:
        if line.variance == Decimal("0.0000"):
            continue  # Zero variance requires no adjustment entry

        entry_num = generate_ledger_entry_number(db, audit.audit_date)
        entry = StockLedgerEntry(
            entry_number=entry_num,
            posting_group_id=posting_group,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            transaction_date=audit.audit_date,
            movement_type=MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value,
            quantity_delta=line.variance,  # Signed variance
            source_document_type=SourceDocumentType.AUDIT_ADJUSTMENT.value,
            source_document_id=audit.id,
            source_line_id=line.id,
            source_document_number=audit.audit_number,
            reference_number=f"Cutoff System: {line.system_quantity}, Count: {line.physical_quantity}",
            reason=line.reason or f"Physical count variance adjustment for audit {audit.audit_number}",
            posted_by=actor_id,
        )
        db.add(entry)
        created_entries.append(entry)
        db.flush()

    return created_entries


def reverse_stock_ledger_entry(
    db: Session,
    entry_id: int,
    reason: str,
    actor_id: str,
) -> StockLedgerEntry:
    with ledger_write_guard(db):
        return _reverse_stock_ledger_entry(db, entry_id, reason, actor_id)


def _reverse_stock_ledger_entry(
    db: Session,
    entry_id: int,
    reason: str,
    actor_id: str,
) -> StockLedgerEntry:
    """
    Creates a compensating REVERSAL entry with opposite sign.
    Guarantees original entry is never deleted or updated.
    Prevents duplicate reversal of the same entry.
    """
    # Lock the original row so concurrent reversal requests serialise (effective on PostgreSQL only).
    original = db.get(StockLedgerEntry, entry_id, with_for_update=True)
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found.")

    if original.movement_type == MovementType.REVERSAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reverse an entry that is already a reversal.",
        )

    # Check if already reversed
    existing_reversal = db.execute(
        select(StockLedgerEntry).where(StockLedgerEntry.reversal_of_entry_id == original.id)
    ).scalars().first()
    if existing_reversal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entry {original.entry_number} has already been reversed by entry {existing_reversal.entry_number}.",
        )

    # Enforce negative stock check on reversal if reversing an inward receipt
    if not settings.ALLOW_NEGATIVE_STOCK and original.quantity_delta > 0:
        cur_bal, _, _, _ = get_material_stock_balance(db, original.material_item_id)
        if cur_bal < original.quantity_delta:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reverse inward entry: Current stock balance ({cur_bal}) is less than reversal quantity ({original.quantity_delta}). Would cause negative stock.",
            )

    today = date.today()
    entry_num = generate_ledger_entry_number(db, today)
    posting_group = f"REV-{original.entry_number}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    reversal_entry = StockLedgerEntry(
        entry_number=entry_num,
        posting_group_id=posting_group,
        material_item_id=original.material_item_id,
        uom_id=original.uom_id,
        transaction_date=today,
        movement_type=MovementType.REVERSAL.value,
        quantity_delta=-original.quantity_delta,  # Opposite sign
        source_document_type=SourceDocumentType.MANUAL_REVERSAL.value,
        source_document_id=original.id,
        source_line_id=original.id,
        source_document_number=original.entry_number,
        reference_number=original.source_document_number,
        reason=reason,
        posted_by=actor_id,
        reversal_of_entry_id=original.id,
    )
    db.add(reversal_entry)
    db.commit()
    db.refresh(reversal_entry)
    return reversal_entry
