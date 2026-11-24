"""
Return to Store (RTS) API Endpoints.
Handles material returns from shop-floor departments back to Stores.
"""

from typing import List, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission, UserRole, get_current_user_context
from app.db.session import get_db, engine
from app.db.base import Base
from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.material_return import (
    MaterialReturnHeader,
    MaterialReturnLineItem,
    MaterialReturnAuditLog,
    ReturnCondition,
    ReturnStatus,
)
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.schemas.material_return import (
    MaterialReturnCreate,
    MaterialReturnResponse,
    MaterialReturnLineResponse,
    MaterialReturnAuditResponse,
    MaterialReturnRejectRequest,
)
from app.services.document_number_service import (
    execute_with_document_number_retry,
    DocumentType,
)
from app.services.ledger_service import generate_posting_group_id, ledger_write_guard

router = APIRouter()

# Ensure table creation if not already present
# create_all removed in the Cloud deployment: the schema is created only by Alembic migrations.


def _serialize_return(header: MaterialReturnHeader) -> MaterialReturnResponse:
    lines = []
    for l in header.lines:
        lines.append(
            MaterialReturnLineResponse(
                id=l.id,
                return_id=l.return_id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                uom_id=l.uom_id,
                quantity=l.quantity,
                condition=l.condition,
                remarks=l.remarks,
                item_code=l.material_item.item_code if l.material_item else None,
                item_name=l.material_item.name if l.material_item else None,
                uom_code=l.uom.code if l.uom else None,
            )
        )
    audits = [
        MaterialReturnAuditResponse(
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

    return MaterialReturnResponse(
        id=header.id,
        return_number=header.return_number,
        return_date=header.return_date,
        returning_department_id=header.returning_department_id,
        returning_department_name=header.returning_department.name if header.returning_department else None,
        receiving_department_id=header.receiving_department_id,
        receiving_department_name=header.receiving_department.name if header.receiving_department else None,
        reference_issue_id=header.reference_issue_id,
        heat_reference_number=header.heat_reference_number,
        condition=header.condition,
        status=header.status,
        notes=header.notes,
        rejection_reason=header.rejection_reason,
        created_by=header.created_by,
        accepted_by=header.accepted_by,
        accepted_at=header.accepted_at,
        created_at=header.created_at,
        updated_at=header.updated_at,
        lines=lines,
        audit_logs=audits,
    )


@router.post("/", response_model=MaterialReturnResponse, status_code=status.HTTP_201_CREATED)
def create_material_return(
    payload: MaterialReturnCreate,
    user: AuthenticatedUser = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """
    Creates a new Return to Store (RTS) voucher.
    Submitted by shop-floor departments (Foundry, Machine Shop, etc.).
    """
    ret_dept = db.get(Department, payload.returning_department_id)
    if not ret_dept:
        raise HTTPException(status_code=404, detail="Returning department not found")

    # Receiving department defaults to Stores (GNS or ID 4)
    recv_dept_id = payload.receiving_department_id
    if not recv_dept_id:
        gns_dept = db.execute(select(Department).where(Department.code == "GNS")).scalar_one_or_none()
        recv_dept_id = gns_dept.id if gns_dept else payload.returning_department_id

    today = payload.return_date or date.today()

    # Generate document sequence
    count_today = db.query(MaterialReturnHeader).count() + 1
    return_num = f"RTS-{today.strftime('%Y%m')}-{count_today:04d}"

    header = MaterialReturnHeader(
        return_number=return_num,
        return_date=today,
        returning_department_id=payload.returning_department_id,
        receiving_department_id=recv_dept_id,
        reference_issue_id=payload.reference_issue_id,
        heat_reference_number=payload.heat_reference_number.strip() if payload.heat_reference_number else None,
        condition=payload.condition,
        status=ReturnStatus.SUBMITTED.value,
        notes=payload.notes,
        created_by=user.user_id,
    )
    db.add(header)
    db.flush()

    for idx, l in enumerate(payload.lines, start=1):
        item = db.get(MaterialItem, l.material_item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Material item ID {l.material_item_id} not found")
        uom_id = l.uom_id or item.base_uom_id
        line_item = MaterialReturnLineItem(
            return_id=header.id,
            line_number=idx,
            material_item_id=l.material_item_id,
            uom_id=uom_id,
            quantity=l.quantity,
            condition=l.condition or payload.condition,
            remarks=l.remarks,
        )
        db.add(line_item)

    audit = MaterialReturnAuditLog(
        return_id=header.id,
        action="SUBMITTED",
        from_status=None,
        to_status=ReturnStatus.SUBMITTED.value,
        actor_id=user.user_id,
        comments=f"Material return voucher submitted by {ret_dept.name} [{payload.condition}].",
    )
    db.add(audit)
    db.commit()
    db.refresh(header)

    return _serialize_return(header)


@router.get("/", response_model=List[MaterialReturnResponse])
def list_material_returns(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    condition_filter: Optional[str] = Query(None, description="Filter by condition"),
    department_id: Optional[int] = Query(None, description="Filter by returning department"),
    heat_number: Optional[str] = Query(None, description="Filter by heat number"),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(get_current_user_context),
):
    """Lists Material Return vouchers with eager loading of relations."""
    stmt = (
        select(MaterialReturnHeader)
        .options(
            joinedload(MaterialReturnHeader.returning_department),
            joinedload(MaterialReturnHeader.receiving_department),
            selectinload(MaterialReturnHeader.lines).joinedload(MaterialReturnLineItem.material_item),
            selectinload(MaterialReturnHeader.lines).joinedload(MaterialReturnLineItem.uom),
            selectinload(MaterialReturnHeader.audit_logs),
        )
        .order_by(desc(MaterialReturnHeader.return_date), desc(MaterialReturnHeader.id))
    )

    if status_filter and status_filter != "ALL":
        stmt = stmt.where(MaterialReturnHeader.status == status_filter)
    if condition_filter and condition_filter != "ALL":
        stmt = stmt.where(MaterialReturnHeader.condition == condition_filter)
    if department_id:
        stmt = stmt.where(MaterialReturnHeader.returning_department_id == department_id)
    if heat_number:
        stmt = stmt.where(MaterialReturnHeader.heat_reference_number.ilike(f"%{heat_number.strip()}%"))

    items = db.execute(stmt).scalars().all()
    return [_serialize_return(h) for h in items]


@router.get("/{id}", response_model=MaterialReturnResponse)
def get_material_return(
    id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(get_current_user_context),
):
    """Retrieves full details of a specific RTS voucher."""
    header = (
        db.query(MaterialReturnHeader)
        .options(
            joinedload(MaterialReturnHeader.returning_department),
            joinedload(MaterialReturnHeader.receiving_department),
            selectinload(MaterialReturnHeader.lines).joinedload(MaterialReturnLineItem.material_item),
            selectinload(MaterialReturnHeader.lines).joinedload(MaterialReturnLineItem.uom),
            selectinload(MaterialReturnHeader.audit_logs),
        )
        .filter(MaterialReturnHeader.id == id)
        .first()
    )
    if not header:
        raise HTTPException(status_code=404, detail="Material return voucher not found")
    return _serialize_return(header)


@router.post("/{id}/accept", response_model=MaterialReturnResponse)
def accept_material_return(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user_context),
):
    """
    Stores Acceptance action.
    Physically verifies returned material and takes it back into store inventory.
    Creates positive stock movements in stock_ledger_entries.
    """
    header = db.get(MaterialReturnHeader, id)
    if not header:
        raise HTTPException(status_code=404, detail="Material return voucher not found")
    if header.status != ReturnStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept return in status '{header.status}'. Must be in SUBMITTED status.",
        )

    # Post to stock ledger with write guard
    with ledger_write_guard(db):
        posting_group = generate_posting_group_id("RTS", header.id)

        for line in header.lines:
            def _create_return_entry(entry_num: str, _line=line) -> StockLedgerEntry:
                entry = StockLedgerEntry(
                    entry_number=entry_num,
                    posting_group_id=posting_group,
                    material_item_id=_line.material_item_id,
                    uom_id=_line.uom_id,
                    transaction_date=header.return_date,
                    movement_type=MovementType.INTERNAL_INWARD.value,
                    quantity_delta=abs(_line.quantity),  # Positive inward into inventory
                    source_document_type="RETURN_TO_STORE",
                    source_document_id=header.id,
                    source_line_id=_line.id,
                    source_document_number=header.return_number,
                    reference_number=header.heat_reference_number,
                    reason=f"Material returned from {header.returning_department.name if header.returning_department else 'Dept'} [{header.condition}]",
                    posted_by=user.user_id,
                )
                db.add(entry)
                return entry

            execute_with_document_number_retry(
                db=db,
                doc_type=DocumentType.LEDGER,
                create_fn=_create_return_entry,
                target_date=header.return_date,
            )

        header.status = ReturnStatus.ACCEPTED.value
        header.accepted_by = user.user_id
        header.accepted_at = datetime.now(timezone.utc)

        audit = MaterialReturnAuditLog(
            return_id=header.id,
            action="ACCEPTED",
            from_status=ReturnStatus.SUBMITTED.value,
            to_status=ReturnStatus.ACCEPTED.value,
            actor_id=user.user_id,
            comments=f"Physical stock verified and inwarded to Stores by {user.user_id}.",
        )
        db.add(audit)
        db.commit()
        db.refresh(header)

    return _serialize_return(header)


@router.post("/{id}/reject", response_model=MaterialReturnResponse)
def reject_material_return(
    id: int,
    payload: MaterialReturnRejectRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user_context),
):
    """Rejects a material return voucher with mandatory operational comments."""
    header = db.get(MaterialReturnHeader, id)
    if not header:
        raise HTTPException(status_code=404, detail="Material return voucher not found")
    if header.status != ReturnStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject return in status '{header.status}'. Must be in SUBMITTED status.",
        )

    header.status = ReturnStatus.REJECTED.value
    header.rejection_reason = payload.comments

    audit = MaterialReturnAuditLog(
        return_id=header.id,
        action="REJECTED",
        from_status=ReturnStatus.SUBMITTED.value,
        to_status=ReturnStatus.REJECTED.value,
        actor_id=user.user_id,
        comments=payload.comments,
    )
    db.add(audit)
    db.commit()
    db.refresh(header)

    return _serialize_return(header)
