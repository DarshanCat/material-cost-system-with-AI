"""
Stock Ledger & Stock Balance API Endpoints.
"""

from typing import List, Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.models.ledger import StockLedgerEntry
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.ledger import (
    StockLedgerEntryResponse,
    StockBalanceResponse,
    UOMStockSummaryResponse,
    LedgerReversalRequest,
    PaginatedLedgerEntriesResponse,
)
from app.services.ledger_service import (
    get_material_stock_balance,
    get_batch_material_stock_balances,
    get_stock_summary_by_uom,
    reverse_stock_ledger_entry,
)

router = APIRouter()


def _serialize_ledger_entry(entry: StockLedgerEntry) -> StockLedgerEntryResponse:
    return StockLedgerEntryResponse(
        id=entry.id,
        entry_number=entry.entry_number,
        posting_group_id=entry.posting_group_id,
        material_item_id=entry.material_item_id,
        item_code=entry.material_item.item_code if entry.material_item else None,
        item_name=entry.material_item.name if entry.material_item else None,
        uom_id=entry.uom_id,
        uom_code=entry.uom.code if entry.uom else None,
        transaction_date=entry.transaction_date,
        posted_at=entry.posted_at,
        movement_type=entry.movement_type,
        quantity_delta=entry.quantity_delta,
        source_document_type=entry.source_document_type,
        source_document_id=entry.source_document_id,
        source_line_id=entry.source_line_id,
        source_document_number=entry.source_document_number,
        reference_number=entry.reference_number,
        reason=entry.reason,
        posted_by=entry.posted_by,
        reversal_of_entry_id=entry.reversal_of_entry_id,
        created_at=entry.created_at,
    )


@router.get("/balances", response_model=List[StockBalanceResponse])
def get_all_stock_balances(
    as_of_date: Optional[date] = Query(None, description="Point-in-time date for stock calculation"),
    department_id: Optional[int] = Query(None, description="Filter items by department"),
    q: Optional[str] = Query(None, description="Search item code or name"),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_READ)),
):
    """
    Computes stock balances for all material items strictly derived from append-only ledger entries.
    Executes in O(1) query complexity using grouped SQL aggregation and relationship eager loading.
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
    if q:
        query = query.where(
            (MaterialItem.item_code.ilike(f"%{q}%")) | (MaterialItem.name.ilike(f"%{q}%"))
        )

    items = db.execute(query).scalars().all()
    if not items:
        return []

    item_ids = [item.id for item in items]
    balances_map = get_batch_material_stock_balances(
        db, material_item_ids=item_ids, as_of_date=as_of_date
    )

    results: List[StockBalanceResponse] = []
    for item in items:
        bal, is_init, last_date, move_count = balances_map.get(
            item.id, (Decimal("0.0000"), False, None, 0)
        )
        
        if not is_init:
            status_str = "UNINITIALIZED"
        elif bal < Decimal("0.0000"):
            status_str = "NEGATIVE_STOCK"
        elif bal == Decimal("0.0000"):
            status_str = "OUT_OF_STOCK"
        else:
            status_str = "IN_STOCK"

        results.append(
            StockBalanceResponse(
                material_item_id=item.id,
                item_code=item.item_code,
                item_name=item.name,
                category=item.category,
                department_name=item.department.name if item.department else None,
                base_uom_id=item.base_uom_id,
                uom_code=item.base_uom.code if item.base_uom else "UOM",
                current_balance=bal,
                is_initialized=is_init,
                status=status_str,
                last_movement_date=last_date,
                movement_count=move_count,
            )
        )

    return results


@router.get("/balances/{item_id}", response_model=StockBalanceResponse)
def get_single_item_stock_balance(
    item_id: int,
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_READ)),
):
    query = (
        select(MaterialItem)
        .options(
            joinedload(MaterialItem.department),
            joinedload(MaterialItem.base_uom),
        )
        .where(MaterialItem.id == item_id)
    )
    item = db.execute(query).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Material item not found.")

    bal, is_init, last_date, move_count = get_material_stock_balance(db, item.id, as_of_date)
    if not is_init:
        status_str = "UNINITIALIZED"
    elif bal < Decimal("0.0000"):
        status_str = "NEGATIVE_STOCK"
    elif bal == Decimal("0.0000"):
        status_str = "OUT_OF_STOCK"
    else:
        status_str = "IN_STOCK"

    return StockBalanceResponse(
        material_item_id=item.id,
        item_code=item.item_code,
        item_name=item.name,
        category=item.category,
        department_name=item.department.name if item.department else None,
        base_uom_id=item.base_uom_id,
        uom_code=item.base_uom.code if item.base_uom else "UOM",
        current_balance=bal,
        is_initialized=is_init,
        status=status_str,
        last_movement_date=last_date,
        movement_count=move_count,
    )


@router.get("/summary-by-uom", response_model=List[UOMStockSummaryResponse])
def get_inventory_summary_by_uom(
    as_of_date: Optional[date] = Query(None, description="Point-in-time date for stock calculation"),
    department_id: Optional[int] = Query(None, description="Filter items by department"),
    include_zero_items: bool = Query(False, description="Include active UOMs with zero assigned items"),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_READ)),
):
    """
    Computes total inventory stock balances strictly grouped by Unit of Measure (UOM).
    Never combines heterogeneous units (KG, LTR, NOS, SET) into a single mass.
    """
    return get_stock_summary_by_uom(
        db, as_of_date=as_of_date, department_id=department_id, include_zero_items=include_zero_items
    )


@router.get("/entries", response_model=PaginatedLedgerEntriesResponse)
def list_stock_ledger_entries(
    material_item_id: Optional[int] = Query(None),
    movement_type: Optional[str] = Query(None),
    source_document_type: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_READ)),
):
    """
    Paginated access to immutable movement history journal.
    """
    query = (
        select(StockLedgerEntry)
        .options(
            joinedload(StockLedgerEntry.material_item),
            joinedload(StockLedgerEntry.uom),
        )
        .order_by(desc(StockLedgerEntry.transaction_date), desc(StockLedgerEntry.id))
    )
    
    if material_item_id:
        query = query.where(StockLedgerEntry.material_item_id == material_item_id)
    if movement_type:
        query = query.where(StockLedgerEntry.movement_type == movement_type.upper())
    if source_document_type:
        query = query.where(StockLedgerEntry.source_document_type == source_document_type.upper())
    if from_date:
        query = query.where(StockLedgerEntry.transaction_date >= from_date)
    if to_date:
        query = query.where(StockLedgerEntry.transaction_date <= to_date)

    from sqlalchemy import func
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    
    entries = db.execute(query.offset((page - 1) * size).limit(size)).scalars().unique().all()
    return PaginatedLedgerEntriesResponse(
        items=[_serialize_ledger_entry(e) for e in entries],
        total=total,
        page=page,
        size=size,
    )


@router.get("/entries/{entry_id}", response_model=StockLedgerEntryResponse)
def get_ledger_entry_by_id(entry_id: int, db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_READ)),
):
    entry = db.get(StockLedgerEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Stock ledger entry not found.")
    return _serialize_ledger_entry(entry)


@router.post("/entries/{entry_id}/reverse", response_model=StockLedgerEntryResponse)
def reverse_ledger_entry_action(
    entry_id: int,
    payload: LedgerReversalRequest,
    user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_REVERSE)),
    db: Session = Depends(get_db),
):
    """
    Creates a compensating REVERSAL journal entry without altering or deleting the original record.
    """
    rev = reverse_stock_ledger_entry(db, entry_id, payload.reason, user.user_id)
    return _serialize_ledger_entry(rev)
