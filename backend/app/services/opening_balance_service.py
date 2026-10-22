"""
Opening Balance Import and Posting Service.
Manages baseline inventory preview, master data validation, and atomic posting
for the 12 October 2026 baseline.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.services.posting_guard import ledger_write_guard
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.opening_balance import (
    OpeningBalancePostRequest,
    OpeningBalancePreviewSummary,
    OpeningBalancePreviewRow,
    OpeningBalanceItemRow,
)
from app.services.decimal_validator import validate_and_flag_quantity
from app.services.ledger_service import generate_ledger_entry_number


def preview_opening_balances(
    db: Session,
    rows: List[OpeningBalanceItemRow],
    baseline_date: date,
) -> OpeningBalancePreviewSummary:
    """
    Validates opening balance rows against master data without writing to ledger.
    """
    items_by_code = {item.item_code.upper(): item for item in db.execute(select(MaterialItem)).scalars().all()}
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}

    findings: List[OpeningBalancePreviewRow] = []
    valid_count = 0
    error_count = 0

    for idx, row in enumerate(rows, start=1):
        row_errors: List[str] = []
        row_warnings: List[str] = []

        item = items_by_code.get(row.item_code.strip().upper())
        if not item:
            row_errors.append(f"Material item code '{row.item_code}' not found in Item Master.")

        uom = uoms_by_code.get(row.uom_code.strip().upper())
        if not uom:
            row_errors.append(f"UOM '{row.uom_code}' not found in UOM Master.")

        # Check precision
        if uom and item:
            qty_res = validate_and_flag_quantity(row.quantity, uom, item.category, item.name)
            if not qty_res.is_valid:
                row_errors.extend(qty_res.errors)
            row_warnings.extend(qty_res.warnings)

        # Check if item already has posted opening balance
        if item:
            existing_ob = db.execute(
                select(StockLedgerEntry).where(
                    StockLedgerEntry.material_item_id == item.id,
                    StockLedgerEntry.movement_type == MovementType.OPENING_BALANCE.value,
                )
            ).scalars().first()
            if existing_ob:
                row_errors.append(
                    f"Item '{item.item_code}' already has an established opening balance ({existing_ob.quantity_delta} on {existing_ob.transaction_date})."
                )

        if row_errors:
            error_count += 1
            is_valid = False
        else:
            valid_count += 1
            is_valid = True

        findings.append(
            OpeningBalancePreviewRow(
                row_number=idx,
                item_code=row.item_code,
                item_name=item.name if item else None,
                uom_code=row.uom_code,
                quantity=row.quantity,
                is_valid=is_valid,
                errors=row_errors,
                warnings=row_warnings,
            )
        )

    can_commit = (error_count == 0 and len(findings) > 0)

    return OpeningBalancePreviewSummary(
        total_rows=len(findings),
        valid_rows_count=valid_count,
        error_rows_count=error_count,
        can_commit=can_commit,
        baseline_date=str(baseline_date),
        findings=findings,
    )


def post_approved_opening_balances(
    db: Session,
    request: OpeningBalancePostRequest,
) -> Dict[str, Any]:
    with ledger_write_guard(db):
        return _post_approved_opening_balances(db, request)


def _post_approved_opening_balances(
    db: Session,
    request: OpeningBalancePostRequest,
) -> Dict[str, Any]:
    """
    Atomically posts approved opening balance rows inside a single database transaction.
    """
    # Preview first to assure 100% validity
    preview = preview_opening_balances(db, request.rows, request.baseline_date)
    if not preview.can_commit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot post opening balances: Batch contains {preview.error_rows_count} blocking errors. Run preview first.",
        )

    items_by_code = {item.item_code.upper(): item for item in db.execute(select(MaterialItem)).scalars().all()}
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}

    posting_group = f"OPENING-BAL-{request.baseline_date.strftime('%Y%m%d')}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    created_entries = []

    for idx, row in enumerate(request.rows, start=1):
        item = items_by_code[row.item_code.strip().upper()]
        uom = uoms_by_code[row.uom_code.strip().upper()]
        
        entry_num = generate_ledger_entry_number(db, request.baseline_date)
        entry = StockLedgerEntry(
            entry_number=entry_num,
            posting_group_id=posting_group,
            material_item_id=item.id,
            uom_id=uom.id,
            transaction_date=request.baseline_date,
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=row.quantity,
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=0,
            source_line_id=item.id,  # Unique per material item
            source_document_number=f"OB-{request.baseline_date.strftime('%Y%m%d')}",
            reference_number=request.audit_reference,
            reason=f"Approved opening stock baseline as of {request.baseline_date}. Ref: {request.audit_reference}",
            posted_by=request.approver_id,
        )
        db.add(entry)
        created_entries.append(entry.entry_number)
        db.flush()

    db.commit()
    return {
        "success": True,
        "posted_count": len(created_entries),
        "posting_group_id": posting_group,
        "message": f"Successfully established {len(created_entries)} opening stock balance records.",
        "entry_numbers": created_entries,
    }
