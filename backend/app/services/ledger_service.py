"""
Authoritative Append-Only Stock Ledger Service.
Handles ledger posting, derived balance calculations, idempotency protection,
and compensating reversals.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, and_, desc
from fastapi import HTTPException, status

from app.services.posting_guard import ledger_write_guard
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.grn import GRNHeader, GRNAuditLog, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, IssueAuditLog, IssueStatus
from app.models.waste import WasteDispositionHeader, WasteAuditLog, WasteStatus, DispositionType
from app.schemas.reversal import DocumentReversalResponse
from app.models.physical_audit import PhysicalAuditHeader, AuditStatus
from app.core.config import settings
from app.services.document_number_service import (
    DocumentType,
    execute_with_document_number_retry,
    generate_document_number,
    generate_posting_group_id,
    generate_reversal_posting_group_id,
)


def generate_ledger_entry_number(db: Session, tx_date: date) -> str:
    """Generates sequential document serial: STK-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.LEDGER, tx_date)


def _lock_material_items_for_update(db: Session, item_ids: List[int]) -> Dict[int, MaterialItem]:
    """
    Acquires transaction-scoped row locks (SELECT ... FOR UPDATE) on MaterialItem rows
    in deterministic ascending ID order. On PostgreSQL, this serializes concurrent
    outward postings and inward-receipt reversals for the same material item so two
    sessions cannot both pass the stock balance check and overdraw inventory.
    """
    unique_ids = sorted({int(i) for i in item_ids if i is not None})
    if not unique_ids:
        return {}
    stmt = (
        select(MaterialItem)
        .where(MaterialItem.id.in_(unique_ids))
        .order_by(MaterialItem.id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    items = db.execute(stmt).scalars().all()
    return {item.id: item for item in items}


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
    stmt = select(
        func.coalesce(func.sum(StockLedgerEntry.quantity_delta), Decimal("0.0000")),
        func.max(StockLedgerEntry.transaction_date),
        func.count(StockLedgerEntry.id),
    ).where(StockLedgerEntry.material_item_id == material_item_id)
    if as_of_date:
        stmt = stmt.where(StockLedgerEntry.transaction_date <= as_of_date)

    row = db.execute(stmt).one()
    total, last_date, movement_count = row
    if movement_count == 0:
        return Decimal("0.0000"), False, None, 0
    return Decimal(str(total)), True, last_date, movement_count


def get_batch_material_stock_balances(
    db: Session,
    material_item_ids: Optional[List[int]] = None,
    as_of_date: Optional[date] = None,
) -> Dict[int, Tuple[Decimal, bool, Optional[date], int]]:
    """
    Computes stock balances for multiple material items in a single grouped SQL aggregation query.
    Eliminates N+1 database queries across large item catalogs.
    Returns: {material_item_id: (balance, is_initialized, last_movement_date, movement_count)}.
    """
    if material_item_ids is not None and len(material_item_ids) == 0:
        return {}

    stmt = select(
        StockLedgerEntry.material_item_id,
        func.sum(StockLedgerEntry.quantity_delta).label("balance"),
        func.max(StockLedgerEntry.transaction_date).label("last_date"),
        func.count(StockLedgerEntry.id).label("movement_count"),
    ).group_by(StockLedgerEntry.material_item_id)

    if as_of_date:
        stmt = stmt.where(StockLedgerEntry.transaction_date <= as_of_date)

    if material_item_ids is not None:
        stmt = stmt.where(StockLedgerEntry.material_item_id.in_(material_item_ids))

    rows = db.execute(stmt).all()
    results: Dict[int, Tuple[Decimal, bool, Optional[date], int]] = {}
    for row in rows:
        item_id, total, last_date, count = row
        results[item_id] = (
            Decimal(str(total)),
            True,
            last_date,
            count,
        )

    # For any requested item_id that has no entries in stock_ledger_entries, default to UNINITIALIZED
    if material_item_ids is not None:
        for item_id in material_item_ids:
            if item_id not in results:
                results[item_id] = (Decimal("0.0000"), False, None, 0)

    return results


def get_stock_summary_by_uom(
    db: Session,
    as_of_date: Optional[date] = None,
    department_id: Optional[int] = None,
    include_zero_items: bool = False,
) -> List[Dict[str, Any]]:
    """
    Computes total inventory stock balances strictly grouped by Unit of Measure (UOM).
    Prevents invalid mathematical summation of heterogeneous units (e.g. KG + LTR + NOS + SET).
    Preserves exact Decimal precision (NUMERIC 15,4).
    """
    query = (
        select(MaterialItem)
        .options(
            joinedload(MaterialItem.department),
            joinedload(MaterialItem.base_uom),
        )
        .where(MaterialItem.is_active == True)
    )
    if department_id:
        query = query.where(MaterialItem.department_id == department_id)

    items = db.execute(query).scalars().all()
    if not items:
        if include_zero_items:
            all_uoms = db.execute(select(UOM).where(UOM.is_active == True).order_by(UOM.code)).scalars().all()
            return [
                {
                    "uom_id": u.id,
                    "uom_code": u.code,
                    "uom_name": u.name,
                    "decimal_precision": u.decimal_precision,
                    "total_quantity": Decimal("0.0000"),
                    "item_count": 0,
                    "in_stock_items_count": 0,
                    "zero_stock_items_count": 0,
                    "negative_stock_items_count": 0,
                    "movement_count": 0,
                }
                for u in all_uoms
            ]
        return []

    item_ids = [item.id for item in items]
    balances_map = get_batch_material_stock_balances(
        db, material_item_ids=item_ids, as_of_date=as_of_date
    )

    uom_map: Dict[str, Dict[str, Any]] = {}
    for item in items:
        bal, is_init, _, move_count = balances_map.get(
            item.id, (Decimal("0.0000"), False, None, 0)
        )
        uom = item.base_uom
        if not uom:
            continue

        if uom.code not in uom_map:
            uom_map[uom.code] = {
                "uom_id": uom.id,
                "uom_code": uom.code,
                "uom_name": uom.name,
                "decimal_precision": uom.decimal_precision,
                "total_quantity": Decimal("0.0000"),
                "item_count": 0,
                "in_stock_items_count": 0,
                "zero_stock_items_count": 0,
                "negative_stock_items_count": 0,
                "movement_count": 0,
            }

        rec = uom_map[uom.code]
        rec["item_count"] += 1
        rec["total_quantity"] += bal
        rec["movement_count"] += move_count
        if bal > Decimal("0.0000"):
            rec["in_stock_items_count"] += 1
        elif is_init and bal == Decimal("0.0000"):
            rec["zero_stock_items_count"] += 1
        elif is_init and bal < Decimal("0.0000"):
            rec["negative_stock_items_count"] += 1

    if include_zero_items:
        all_uoms = db.execute(select(UOM).where(UOM.is_active == True).order_by(UOM.code)).scalars().all()
        for u in all_uoms:
            if u.code not in uom_map:
                uom_map[u.code] = {
                    "uom_id": u.id,
                    "uom_code": u.code,
                    "uom_name": u.name,
                    "decimal_precision": u.decimal_precision,
                    "total_quantity": Decimal("0.0000"),
                    "item_count": 0,
                    "in_stock_items_count": 0,
                    "zero_stock_items_count": 0,
                    "negative_stock_items_count": 0,
                    "movement_count": 0,
                }

    return [uom_map[code] for code in sorted(uom_map.keys())]


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

    posting_group = generate_posting_group_id("GRN", grn.id)
    created_entries: List[StockLedgerEntry] = []
    
    movement_type = (
        MovementType.INWARD_RECEIPT.value
        if grn.source_type == GRNSourceType.EXTERNAL_VENDOR.value
        else MovementType.INTERNAL_INWARD.value
    )

    for line in grn.lines:
        def _create_grn_entry(entry_num: str, _line=line) -> StockLedgerEntry:
            entry = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_line.material_item_id,
                uom_id=_line.uom_id,
                transaction_date=grn.receipt_date,
                movement_type=movement_type,
                quantity_delta=abs(_line.quantity),  # Strictly positive
                source_document_type=SourceDocumentType.GRN.value,
                source_document_id=grn.id,
                source_line_id=_line.id,
                source_document_number=grn.grn_number,
                reference_number=grn.vendor_invoice_no,
                reason=f"Approved GRN receipt ({grn.source_type})",
                posted_by=actor_id,
            )
            db.add(entry)
            return entry

        entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_grn_entry,
            target_date=grn.receipt_date,
        )
        created_entries.append(entry)

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

    # Negative stock policy verification with per-item row locking (PostgreSQL FOR UPDATE)
    if not settings.ALLOW_NEGATIVE_STOCK:
        locked_items = _lock_material_items_for_update(
            db, [line.material_item_id for line in issue.lines]
        )
        available_by_item: Dict[int, Decimal] = {}
        for line in issue.lines:
            item_id = line.material_item_id
            item = locked_items.get(item_id) or db.get(MaterialItem, item_id)
            item_code = item.item_code if item else f"ID {item_id}"
            if item_id not in available_by_item:
                current_bal, is_init, _, _ = get_material_stock_balance(db, item_id)
                if not is_init:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot issue material '{item_code}': Stock baseline has not been initialized. Establish opening balance first.",
                    )
                available_by_item[item_id] = current_bal

            avail = available_by_item[item_id]
            if avail < line.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient inventory for '{item_code}': Required {line.quantity}, available {avail}. Negative stock is disallowed by VSPL governance policy.",
                )
            available_by_item[item_id] = avail - line.quantity

    posting_group = generate_posting_group_id("ISS", issue.id)
    created_entries: List[StockLedgerEntry] = []

    for line in issue.lines:
        def _create_issue_entry(entry_num: str, _line=line) -> StockLedgerEntry:
            entry = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_line.material_item_id,
                uom_id=_line.uom_id,
                transaction_date=issue.issue_date,
                movement_type=MovementType.OUTWARD_ISSUE.value,
                quantity_delta=-abs(_line.quantity),  # Strictly negative
                source_document_type=SourceDocumentType.ISSUE.value,
                source_document_id=issue.id,
                source_line_id=_line.id,
                source_document_number=issue.issue_slip_number,
                reference_number=issue.heat_reference_number,
                reason=f"Approved departmental material issue to {issue.receiving_department.name if issue.receiving_department else 'Dept'}",
                posted_by=actor_id,
            )
            db.add(entry)
            return entry

        entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_issue_entry,
            target_date=issue.issue_date,
        )
        created_entries.append(entry)

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

    # Negative stock policy verification with per-item row locking (PostgreSQL FOR UPDATE)
    if waste.disposition_type == DispositionType.SCRAP_OUTWARD.value and not settings.ALLOW_NEGATIVE_STOCK:
        locked_items = _lock_material_items_for_update(
            db, [line.material_item_id for line in waste.lines]
        )
        available_by_item: Dict[int, Decimal] = {}
        for line in waste.lines:
            item_id = line.material_item_id
            item = locked_items.get(item_id) or db.get(MaterialItem, item_id)
            item_code = item.item_code if item else f"ID {item_id}"
            if item_id not in available_by_item:
                current_bal, is_init, _, _ = get_material_stock_balance(db, item_id)
                if not is_init:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot dispose waste for material '{item_code}': Stock baseline has not been initialized. Establish opening balance first.",
                    )
                available_by_item[item_id] = current_bal

            avail = available_by_item[item_id]
            req_qty = abs(line.quantity)
            if avail < req_qty:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient inventory for '{item_code}': Required {line.quantity}, available {avail}. Negative stock is disallowed by VSPL governance policy.",
                )
            available_by_item[item_id] = avail - req_qty

    posting_group = generate_posting_group_id("WST", waste.id)
    created_entries: List[StockLedgerEntry] = []

    for line in waste.lines:
        if waste.disposition_type == DispositionType.SCRAP_OUTWARD.value:
            m_type = MovementType.SCRAP_OUTWARD.value
            qty_delta = -abs(line.quantity)
        else:
            # INTERNAL_RECOVERY: Tracked retention/remelt transfer
            m_type = MovementType.INTERNAL_RECOVERY.value
            qty_delta = Decimal("0.0000")  # Net-neutral within total pool

        def _create_waste_entry(entry_num: str, _line=line, _m_type=m_type, _qty_delta=qty_delta) -> StockLedgerEntry:
            entry = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_line.material_item_id,
                uom_id=_line.uom_id,
                transaction_date=waste.disposition_date,
                movement_type=_m_type,
                quantity_delta=_qty_delta,
                source_document_type=SourceDocumentType.WASTE.value,
                source_document_id=waste.id,
                source_line_id=_line.id,
                source_document_number=waste.waste_number,
                reference_number=waste.waste_type,
                reason=f"Approved waste disposition: {waste.disposition_type} ({waste.waste_type})",
                posted_by=actor_id,
            )
            db.add(entry)
            return entry

        entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_waste_entry,
            target_date=waste.disposition_date,
        )
        created_entries.append(entry)

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

    # Negative stock policy verification with per-item row locking (PostgreSQL FOR UPDATE)
    variance_lines = [line for line in audit.lines if line.variance != Decimal("0.0000")]
    if variance_lines:
        locked_items = _lock_material_items_for_update(
            db, [line.material_item_id for line in variance_lines]
        )
        if not settings.ALLOW_NEGATIVE_STOCK:
            available_by_item: Dict[int, Decimal] = {}
            for line in audit.lines:
                if line.variance == Decimal("0.0000"):
                    continue
                item_id = line.material_item_id
                item = locked_items.get(item_id) or db.get(MaterialItem, item_id)
                item_code = item.item_code if item else f"ID {item_id}"
                if item_id not in available_by_item:
                    current_bal, is_init, _, _ = get_material_stock_balance(db, item_id)
                    if not is_init:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Cannot adjust stock for uninitialized material '{item_code}': Stock baseline has not been initialized. Establish opening balance first.",
                        )
                    available_by_item[item_id] = current_bal

                avail = available_by_item[item_id]
                if line.variance < Decimal("0.0000") and (avail + line.variance) < Decimal("0.0000"):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Insufficient inventory for audit adjustment on '{item_code}': Adjustment variance {line.variance} exceeds available balance {avail}. Negative stock is disallowed by VSPL governance policy.",
                    )
                available_by_item[item_id] = avail + line.variance

    posting_group = generate_posting_group_id("AUD", audit.id)
    created_entries: List[StockLedgerEntry] = []

    for line in audit.lines:
        if line.variance == Decimal("0.0000"):
            continue  # Zero variance requires no adjustment entry

        def _create_audit_entry(entry_num: str, _line=line) -> StockLedgerEntry:
            entry = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_line.material_item_id,
                uom_id=_line.uom_id,
                transaction_date=audit.audit_date,
                movement_type=MovementType.PHYSICAL_AUDIT_ADJUSTMENT.value,
                quantity_delta=_line.variance,  # Signed variance
                source_document_type=SourceDocumentType.AUDIT_ADJUSTMENT.value,
                source_document_id=audit.id,
                source_line_id=_line.id,
                source_document_number=audit.audit_number,
                reference_number=f"Cutoff System: {_line.system_quantity}, Count: {_line.physical_quantity}",
                reason=_line.reason or f"Physical count variance adjustment for audit {audit.audit_number}",
                posted_by=actor_id,
            )
            db.add(entry)
            return entry

        entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_audit_entry,
            target_date=audit.audit_date,
        )
        created_entries.append(entry)

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
        _lock_material_items_for_update(db, [original.material_item_id])
        cur_bal, _, _, _ = get_material_stock_balance(db, original.material_item_id)
        if cur_bal < original.quantity_delta:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reverse inward entry: Current stock balance ({cur_bal}) is less than reversal quantity ({original.quantity_delta}). Would cause negative stock.",
            )

    today = date.today()
    posting_group = generate_reversal_posting_group_id(original.entry_number)

    def _create_reversal(entry_num: str) -> StockLedgerEntry:
        rev = StockLedgerEntry(
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
        db.add(rev)
        return rev

    reversal_entry = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.LEDGER,
        create_fn=_create_reversal,
        target_date=today,
    )
    db.commit()
    db.refresh(reversal_entry)
    return reversal_entry



def reverse_grn(
    db: Session,
    grn_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    """
    Atomically reverses an approved Goods Receipt Note.
    Creates compensating REVERSAL entries with negative quantity deltas.
    Pessimistically verifies that stock will not drop below zero before reversing.
    """
    with ledger_write_guard(db):
        return _reverse_grn(db, grn_id, actor_id, reason)


def _reverse_grn(
    db: Session,
    grn_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    grn = db.get(GRNHeader, grn_id, with_for_update=True)
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")

    if grn.status == GRNStatus.REVERSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"GRN '{grn.grn_number}' has already been reversed.",
        )

    if grn.status != GRNStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reverse GRN in status '{grn.status}'. Only APPROVED GRNs can be reversed.",
        )

    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reversal reason is mandatory and cannot be empty.",
        )

    # 1. Fetch original ledger entries
    orig_entries = db.execute(
        select(StockLedgerEntry)
        .where(
            StockLedgerEntry.source_document_type == SourceDocumentType.GRN.value,
            StockLedgerEntry.source_document_id == grn.id,
        )
        .order_by(StockLedgerEntry.id.asc())
    ).scalars().all()

    # 2. Prevent duplicate reversals if individual lines were already reversed
    if orig_entries:
        orig_ids = [e.id for e in orig_entries]
        existing_reversals = db.execute(
            select(StockLedgerEntry).where(StockLedgerEntry.reversal_of_entry_id.in_(orig_ids))
        ).scalars().all()
        if existing_reversals:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"One or more ledger entries for GRN '{grn.grn_number}' have already been reversed.",
            )

    # 3. Negative stock policy check with pessimistic item locks
    item_ids = [e.material_item_id for e in orig_entries if e.quantity_delta > Decimal("0.0000")]
    if item_ids:
        locked_items = _lock_material_items_for_update(db, item_ids)
        if not settings.ALLOW_NEGATIVE_STOCK:
            required_deductions: Dict[int, Decimal] = {}
            for e in orig_entries:
                if e.quantity_delta > Decimal("0.0000"):
                    required_deductions[e.material_item_id] = (
                        required_deductions.get(e.material_item_id, Decimal("0.0000")) + e.quantity_delta
                    )

            for item_id, req_qty in required_deductions.items():
                cur_bal, _, _, _ = get_material_stock_balance(db, item_id)
                if cur_bal < req_qty:
                    item = locked_items.get(item_id) or db.get(MaterialItem, item_id)
                    item_code = item.item_code if item else f"ID {item_id}"
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cannot reverse GRN '{grn.grn_number}': Reversing receipt of {req_qty} "
                            f"exceeds available stock {cur_bal} for material '{item_code}'. "
                            f"Negative stock is disallowed by VSPL governance policy."
                        ),
                    )

    # 4. Generate compensating reversal entries
    today = date.today()
    posting_group = generate_reversal_posting_group_id(grn.grn_number)
    created_reversals: List[StockLedgerEntry] = []

    for orig in orig_entries:
        def _create_reversal_entry(entry_num: str, _orig=orig) -> StockLedgerEntry:
            rev = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_orig.material_item_id,
                uom_id=_orig.uom_id,
                transaction_date=today,
                movement_type=MovementType.REVERSAL.value,
                quantity_delta=-_orig.quantity_delta,  # Compensating opposite sign
                source_document_type=SourceDocumentType.MANUAL_REVERSAL.value,
                source_document_id=_orig.id,
                source_line_id=_orig.id,
                source_document_number=_orig.source_document_number,
                reference_number=f"REVERSAL-OF-{_orig.entry_number}",
                reason=clean_reason,
                posted_by=actor_id,
                reversal_of_entry_id=_orig.id,
            )
            db.add(rev)
            return rev

        rev_entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_reversal_entry,
            target_date=today,
        )
        created_reversals.append(rev_entry)

    # 5. Transition document status & log audit record
    prev_status = grn.status
    grn.status = GRNStatus.REVERSED.value
    audit = GRNAuditLog(
        grn_id=grn.id,
        action="REVERSED",
        from_status=prev_status,
        to_status=grn.status,
        actor_id=actor_id,
        comments=clean_reason,
    )
    db.add(audit)
    db.commit()
    db.refresh(grn)

    now_utc = datetime.now(timezone.utc)
    return DocumentReversalResponse(
        document_type="GRN",
        document_id=grn.id,
        document_number=grn.grn_number,
        status=grn.status,
        reversed_by=actor_id,
        reversed_at=now_utc,
        reason=clean_reason,
        reversal_posting_group_id=posting_group,
        original_ledger_entry_ids=[e.id for e in orig_entries],
        reversal_ledger_entry_ids=[e.id for e in created_reversals],
        reversal_entry_numbers=[e.entry_number for e in created_reversals],
    )


def reverse_material_issue(
    db: Session,
    issue_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    """
    Atomically reverses an approved Material Issue slip.
    Creates compensating REVERSAL entries with positive quantity deltas,
    restoring inventory back into available stock.
    """
    with ledger_write_guard(db):
        return _reverse_material_issue(db, issue_id, actor_id, reason)


def _reverse_material_issue(
    db: Session,
    issue_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    issue = db.get(MaterialIssueHeader, issue_id, with_for_update=True)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material issue slip not found.")

    if issue.status == IssueStatus.REVERSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issue slip '{issue.issue_slip_number}' has already been reversed.",
        )

    if issue.status != IssueStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reverse issue slip in status '{issue.status}'. Only APPROVED issue slips can be reversed.",
        )

    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reversal reason is mandatory and cannot be empty.",
        )

    # 1. Fetch original ledger entries
    orig_entries = db.execute(
        select(StockLedgerEntry)
        .where(
            StockLedgerEntry.source_document_type == SourceDocumentType.ISSUE.value,
            StockLedgerEntry.source_document_id == issue.id,
        )
        .order_by(StockLedgerEntry.id.asc())
    ).scalars().all()

    # 2. Prevent duplicate reversals if individual lines were already reversed
    if orig_entries:
        orig_ids = [e.id for e in orig_entries]
        existing_reversals = db.execute(
            select(StockLedgerEntry).where(StockLedgerEntry.reversal_of_entry_id.in_(orig_ids))
        ).scalars().all()
        if existing_reversals:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"One or more ledger entries for issue slip '{issue.issue_slip_number}' have already been reversed.",
            )

    # 3. Lock affected items in ascending ID order for deterministic serialization
    item_ids = [e.material_item_id for e in orig_entries]
    if item_ids:
        _lock_material_items_for_update(db, item_ids)

    # 4. Generate compensating reversal entries (opposite sign restores inventory)
    today = date.today()
    posting_group = generate_reversal_posting_group_id(issue.issue_slip_number)
    created_reversals: List[StockLedgerEntry] = []

    for orig in orig_entries:
        def _create_reversal_entry(entry_num: str, _orig=orig) -> StockLedgerEntry:
            rev = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_orig.material_item_id,
                uom_id=_orig.uom_id,
                transaction_date=today,
                movement_type=MovementType.REVERSAL.value,
                quantity_delta=-_orig.quantity_delta,  # -(-quantity) = +quantity
                source_document_type=SourceDocumentType.MANUAL_REVERSAL.value,
                source_document_id=_orig.id,
                source_line_id=_orig.id,
                source_document_number=_orig.source_document_number,
                reference_number=f"REVERSAL-OF-{_orig.entry_number}",
                reason=clean_reason,
                posted_by=actor_id,
                reversal_of_entry_id=_orig.id,
            )
            db.add(rev)
            return rev

        rev_entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_reversal_entry,
            target_date=today,
        )
        created_reversals.append(rev_entry)

    # 5. Transition document status & log audit record
    prev_status = issue.status
    issue.status = IssueStatus.REVERSED.value
    audit = IssueAuditLog(
        issue_id=issue.id,
        action="REVERSED",
        from_status=prev_status,
        to_status=issue.status,
        actor_id=actor_id,
        comments=clean_reason,
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)

    now_utc = datetime.now(timezone.utc)
    return DocumentReversalResponse(
        document_type="ISSUE",
        document_id=issue.id,
        document_number=issue.issue_slip_number,
        status=issue.status,
        reversed_by=actor_id,
        reversed_at=now_utc,
        reason=clean_reason,
        reversal_posting_group_id=posting_group,
        original_ledger_entry_ids=[e.id for e in orig_entries],
        reversal_ledger_entry_ids=[e.id for e in created_reversals],
        reversal_entry_numbers=[e.entry_number for e in created_reversals],
    )


def reverse_waste_disposition(
    db: Session,
    waste_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    """
    Atomically reverses an approved Waste Disposition record.
    - SCRAP_OUTWARD: Compensating entry restores inventory (+delta).
    - INTERNAL_RECOVERY: Net-neutral compensating entry (quantity delta = 0.0000).
    - INSPECTION_HOLD: No ledger entries existed; transitions status only with no phantom movements.
    """
    with ledger_write_guard(db):
        return _reverse_waste_disposition(db, waste_id, actor_id, reason)


def _reverse_waste_disposition(
    db: Session,
    waste_id: int,
    actor_id: str,
    reason: str,
) -> DocumentReversalResponse:
    waste = db.get(WasteDispositionHeader, waste_id, with_for_update=True)
    if not waste:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waste disposition record not found.")

    if waste.status == WasteStatus.REVERSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Waste disposition '{waste.waste_number}' has already been reversed.",
        )

    if waste.status != WasteStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reverse waste disposition in status '{waste.status}'. Only APPROVED waste records can be reversed.",
        )

    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reversal reason is mandatory and cannot be empty.",
        )

    # 1. Fetch original ledger entries (INSPECTION_HOLD has no ledger entries)
    orig_entries = db.execute(
        select(StockLedgerEntry)
        .where(
            StockLedgerEntry.source_document_type == SourceDocumentType.WASTE.value,
            StockLedgerEntry.source_document_id == waste.id,
        )
        .order_by(StockLedgerEntry.id.asc())
    ).scalars().all()

    # 2. Prevent duplicate reversals if individual lines were already reversed
    if orig_entries:
        orig_ids = [e.id for e in orig_entries]
        existing_reversals = db.execute(
            select(StockLedgerEntry).where(StockLedgerEntry.reversal_of_entry_id.in_(orig_ids))
        ).scalars().all()
        if existing_reversals:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"One or more ledger entries for waste disposition '{waste.waste_number}' have already been reversed.",
            )

    # 3. Lock affected items in ascending order if ledger entries are being reversed
    if orig_entries:
        item_ids = [e.material_item_id for e in orig_entries]
        _lock_material_items_for_update(db, item_ids)

    # 4. Generate compensating reversal entries based on disposition type
    today = date.today()
    posting_group = generate_reversal_posting_group_id(waste.waste_number)
    created_reversals: List[StockLedgerEntry] = []

    # INSPECTION_HOLD produced no ledger entries, so created_reversals remains empty
    for orig in orig_entries:
        def _create_reversal_entry(entry_num: str, _orig=orig) -> StockLedgerEntry:
            rev = StockLedgerEntry(
                entry_number=entry_num,
                posting_group_id=posting_group,
                material_item_id=_orig.material_item_id,
                uom_id=_orig.uom_id,
                transaction_date=today,
                movement_type=MovementType.REVERSAL.value,
                quantity_delta=-_orig.quantity_delta,  # Opposite sign
                source_document_type=SourceDocumentType.MANUAL_REVERSAL.value,
                source_document_id=_orig.id,
                source_line_id=_orig.id,
                source_document_number=_orig.source_document_number,
                reference_number=f"REVERSAL-OF-{_orig.entry_number}",
                reason=clean_reason,
                posted_by=actor_id,
                reversal_of_entry_id=_orig.id,
            )
            db.add(rev)
            return rev

        rev_entry = execute_with_document_number_retry(
            db=db,
            doc_type=DocumentType.LEDGER,
            create_fn=_create_reversal_entry,
            target_date=today,
        )
        created_reversals.append(rev_entry)

    # 5. Transition document status & log audit record
    prev_status = waste.status
    waste.status = WasteStatus.REVERSED.value
    audit = WasteAuditLog(
        waste_id=waste.id,
        action="REVERSED",
        from_status=prev_status,
        to_status=waste.status,
        actor_id=actor_id,
        comments=clean_reason,
    )
    db.add(audit)
    db.commit()
    db.refresh(waste)

    now_utc = datetime.now(timezone.utc)
    return DocumentReversalResponse(
        document_type="WASTE",
        document_id=waste.id,
        document_number=waste.waste_number,
        status=waste.status,
        reversed_by=actor_id,
        reversed_at=now_utc,
        reason=clean_reason,
        reversal_posting_group_id=posting_group,
        original_ledger_entry_ids=[e.id for e in orig_entries],
        reversal_ledger_entry_ids=[e.id for e in created_reversals],
        reversal_entry_numbers=[e.entry_number for e in created_reversals],
    )
