"""
Opening Stock Valuation Versioning and Maker-Checker Service (SW-06).

Manages proposal, independent approval, rejection, and lifecycle versioning
for material item opening commercial valuation rates.
Ensures maker-checker separation of duties, immutable revision history,
and transactional safety.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.costing import (
    ItemOpeningValuation,
    ItemOpeningValuationAuditLog,
    OpeningValuationStatus,
)
from app.models.item import MaterialItem
from app.schemas.costing import ItemOpeningValuationCreate
from app.services.maker_checker import enforce_maker_checker, OPENING_VALUATION
def _same_person(a: str, b: str) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()



def propose_opening_valuation(
    db: Session,
    payload: ItemOpeningValuationCreate,
    actor_id: str,
) -> ItemOpeningValuation:
    """
    Proposes a new opening valuation rate version for a material item.
    Enforces master item validation, baseline date boundaries, and prevents
    duplicate pending proposals.
    """
    item = db.get(MaterialItem, payload.material_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {payload.material_item_id} not found",
        )

    if payload.baseline_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Baseline valuation date cannot be in the future",
        )

    if payload.opening_rate_ex_gst <= Decimal("0.0000"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opening rate excluding GST must be greater than zero",
        )

    # Check for existing pending proposal for this item
    pending = db.execute(
        select(ItemOpeningValuation).where(
            ItemOpeningValuation.material_item_id == payload.material_item_id,
            ItemOpeningValuation.status.in_([
                OpeningValuationStatus.PROPOSED.value,
                OpeningValuationStatus.PENDING_APPROVAL.value,
            ]),
        )
    ).scalars().first()
    if pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An opening valuation proposal (version {pending.version}) is already "
                f"pending approval for item {item.item_code}. Approve or reject it before submitting a new proposal."
            ),
        )

    # Version sequence determination
    max_version = db.execute(
        select(func.coalesce(func.max(ItemOpeningValuation.version), 0)).where(
            ItemOpeningValuation.material_item_id == payload.material_item_id
        )
    ).scalar_one()
    new_version = max_version + 1

    now_utc = datetime.now(timezone.utc)
    record = ItemOpeningValuation(
        material_item_id=payload.material_item_id,
        version=new_version,
        baseline_date=payload.baseline_date,
        opening_rate_ex_gst=payload.opening_rate_ex_gst,
        status=OpeningValuationStatus.PROPOSED.value,
        created_by=actor_id,
        notes=payload.notes,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(record)
    db.flush()

    audit = ItemOpeningValuationAuditLog(
        valuation_id=record.id,
        action="PROPOSED",
        from_status=None,
        to_status=OpeningValuationStatus.PROPOSED.value,
        actor_id=actor_id,
        comments=payload.notes or f"Proposed opening valuation version {new_version}",
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()
    db.refresh(record)
    return record


def approve_opening_valuation(
    db: Session,
    valuation_id: int,
    actor_id: str,
    comments: Optional[str] = None,
) -> ItemOpeningValuation:
    """
    Approves a proposed opening valuation under pessimistic row locks.
    Enforces maker-checker (creator cannot self-approve).
    Atomically transitions any previous APPROVED version for the item to SUPERSEDED.
    """
    valuation = db.execute(
        select(ItemOpeningValuation)
        .where(ItemOpeningValuation.id == valuation_id)
        .with_for_update()
    ).scalars().first()

    if not valuation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item opening valuation ID {valuation_id} not found",
        )

    # 1. Maker-checker enforcement (SW-06 mandatory rule)
    if _same_person(valuation.created_by, actor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maker-checker violation: the creator of opening valuation v{valuation.version} cannot approve it. A different authorized approver is required.",
        )

    # 2. Status validations
    if valuation.status == OpeningValuationStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Opening valuation v{valuation.version} is already approved",
        )
    if valuation.status == OpeningValuationStatus.SUPERSEDED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve superseded opening valuation v{valuation.version}",
        )
    if valuation.status == OpeningValuationStatus.REJECTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve rejected opening valuation v{valuation.version}",
        )
    if valuation.status not in (
        OpeningValuationStatus.PROPOSED.value,
        OpeningValuationStatus.PENDING_APPROVAL.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve opening valuation in {valuation.status} status",
        )

    now_utc = datetime.now(timezone.utc)

    # 3. Atomically supersede any existing APPROVED version for this material item
    currently_approved = db.execute(
        select(ItemOpeningValuation)
        .where(
            ItemOpeningValuation.material_item_id == valuation.material_item_id,
            ItemOpeningValuation.status == OpeningValuationStatus.APPROVED.value,
            ItemOpeningValuation.id != valuation.id,
        )
        .with_for_update()
    ).scalars().all()

    for prior in currently_approved:
        prior.status = OpeningValuationStatus.SUPERSEDED.value
        prior.superseded_by_id = valuation.id
        prior.superseded_at = now_utc
        prior.updated_at = now_utc

        prior_log = ItemOpeningValuationAuditLog(
            valuation_id=prior.id,
            action="SUPERSEDED",
            from_status=OpeningValuationStatus.APPROVED.value,
            to_status=OpeningValuationStatus.SUPERSEDED.value,
            actor_id=actor_id,
            comments=f"Superseded by approved opening valuation v{valuation.version} (id={valuation.id})",
            timestamp=now_utc,
        )
        db.add(prior_log)

    # 4. Mark proposed valuation as APPROVED
    old_status = valuation.status
    valuation.status = OpeningValuationStatus.APPROVED.value
    valuation.approved_by = actor_id
    valuation.approved_at = now_utc
    valuation.updated_at = now_utc

    approval_log = ItemOpeningValuationAuditLog(
        valuation_id=valuation.id,
        action="APPROVED",
        from_status=old_status,
        to_status=OpeningValuationStatus.APPROVED.value,
        actor_id=actor_id,
        comments=comments or f"Approved opening valuation v{valuation.version}",
        timestamp=now_utc,
    )
    db.add(approval_log)
    db.commit()
    db.refresh(valuation)
    return valuation


def reject_opening_valuation(
    db: Session,
    valuation_id: int,
    actor_id: str,
    reason: str,
) -> ItemOpeningValuation:
    """
    Rejects a proposed opening valuation with mandatory justification.
    Enforces maker-checker separation of duties.
    """
    valuation = db.execute(
        select(ItemOpeningValuation)
        .where(ItemOpeningValuation.id == valuation_id)
        .with_for_update()
    ).scalars().first()

    if not valuation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item opening valuation ID {valuation_id} not found",
        )

    if not reason or not reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is mandatory and cannot be empty",
        )

    # Enforce maker-checker on rejection (SW-06 mandatory rule)
    if _same_person(valuation.created_by, actor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maker-checker violation: the creator of opening valuation v{valuation.version} cannot reject it. A different authorized approver is required.",
        )

    if valuation.status not in (
        OpeningValuationStatus.PROPOSED.value,
        OpeningValuationStatus.PENDING_APPROVAL.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject opening valuation in {valuation.status} status",
        )

    now_utc = datetime.now(timezone.utc)
    old_status = valuation.status
    valuation.status = OpeningValuationStatus.REJECTED.value
    valuation.rejection_reason = reason.strip()
    valuation.updated_at = now_utc

    audit = ItemOpeningValuationAuditLog(
        valuation_id=valuation.id,
        action="REJECTED",
        from_status=old_status,
        to_status=OpeningValuationStatus.REJECTED.value,
        actor_id=actor_id,
        comments=reason.strip(),
        timestamp=now_utc,
    )
    db.add(audit)
    db.commit()
    db.refresh(valuation)
    return valuation


def get_effective_opening_valuation(
    db: Session,
    material_item_id: int,
    as_of_date: Optional[date] = None,
) -> Optional[ItemOpeningValuation]:
    """
    Returns the currently active approved opening valuation version for an item.
    """
    query = select(ItemOpeningValuation).where(
        ItemOpeningValuation.material_item_id == material_item_id,
        ItemOpeningValuation.status == OpeningValuationStatus.APPROVED.value,
    )
    if as_of_date:
        query = query.where(ItemOpeningValuation.baseline_date <= as_of_date)
    query = query.order_by(ItemOpeningValuation.version.desc())
    return db.execute(query).scalars().first()


def list_opening_valuations(
    db: Session,
    material_item_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[ItemOpeningValuation]:
    """
    Lists opening valuation records with optional filters.
    """
    query = select(ItemOpeningValuation)
    if material_item_id is not None:
        query = query.where(ItemOpeningValuation.material_item_id == material_item_id)
    if status is not None:
        query = query.where(ItemOpeningValuation.status == status.strip().upper())
    query = query.order_by(ItemOpeningValuation.material_item_id, ItemOpeningValuation.version.desc())
    return list(db.execute(query).scalars().all())


def get_opening_valuation_by_id(db: Session, valuation_id: int) -> ItemOpeningValuation:
    """
    Retrieves a single opening valuation by ID.
    """
    record = db.get(ItemOpeningValuation, valuation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item opening valuation ID {valuation_id} not found",
        )
    return record
