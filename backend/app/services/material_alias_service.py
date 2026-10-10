"""
Material Description Alias Master Service.
Manages mapping from raw heat-log descriptions to controlled MaterialItem records.
Provides review/approval state machine and ensures no duplicate or ambiguous aliases.
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from fastapi import HTTPException, status

from app.models.material_alias import MaterialAlias, MaterialAliasAuditLog, AliasApprovalStatus
from app.models.item import MaterialItem
from app.services.validators import normalize_alias_key


def create_material_alias(
    db: Session,
    alias_text: str,
    material_item_id: int,
    created_by: str,
    status_val: str = AliasApprovalStatus.APPROVED.value,
) -> MaterialAlias:
    """
    Creates a new material alias mapping.
    Prevents duplicate active normalized keys.
    """
    if not alias_text or not alias_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Alias text cannot be empty",
        )
    
    # Verify material item exists and is active
    item = db.execute(
        select(MaterialItem).where(MaterialItem.id == material_item_id)
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material item ID {material_item_id} not found",
        )
    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot map alias to inactive material item '{item.item_code}'",
        )
    
    norm_key = normalize_alias_key(alias_text)
    if not norm_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Normalized alias key cannot be empty",
        )
    
    # Check if normalized key already exists
    existing = db.execute(
        select(MaterialAlias).where(MaterialAlias.normalized_alias_key == norm_key)
    ).scalar_one_or_none()
    if existing:
        if existing.material_item_id == material_item_id:
            # Same mapping already exists
            if not existing.is_active:
                existing.is_active = True
                existing.status = status_val
                db.commit()
                db.refresh(existing)
            return existing
        else:
            # Ambiguous mapping collision
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Alias key '{norm_key}' is already mapped to material item ID "
                    f"{existing.material_item_id}. Ambiguous multi-item aliases are prohibited."
                ),
            )
    
    alias = MaterialAlias(
        alias_text=alias_text.strip(),
        normalized_alias_key=norm_key,
        material_item_id=material_item_id,
        is_active=True,
        status=status_val,
        created_by=created_by,
        reviewer_id=created_by if status_val == AliasApprovalStatus.APPROVED.value else None,
        reviewed_at=datetime.now(timezone.utc) if status_val == AliasApprovalStatus.APPROVED.value else None,
    )
    db.add(alias)
    db.flush()
    
    audit = MaterialAliasAuditLog(
        alias_id=alias.id,
        action="CREATED",
        from_status=None,
        to_status=alias.status,
        actor_id=created_by,
        comments="Alias mapping initialized",
    )
    db.add(audit)
    db.commit()
    db.refresh(alias)
    return alias


def approve_material_alias(
    db: Session,
    alias_id: int,
    reviewer_id: str,
    comments: Optional[str] = None,
) -> MaterialAlias:
    """
    Approves a pending alias mapping.
    """
    alias = db.execute(
        select(MaterialAlias).where(MaterialAlias.id == alias_id)
    ).scalar_one_or_none()
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material alias ID {alias_id} not found",
        )
    if alias.status == AliasApprovalStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alias is already approved",
        )
    
    from_status = alias.status
    alias.status = AliasApprovalStatus.APPROVED.value
    alias.reviewer_id = reviewer_id
    alias.reviewed_at = datetime.now(timezone.utc)
    alias.decision_notes = comments
    
    audit = MaterialAliasAuditLog(
        alias_id=alias.id,
        action="APPROVED",
        from_status=from_status,
        to_status=alias.status,
        actor_id=reviewer_id,
        comments=comments or "Approved by supervisor",
    )
    db.add(audit)
    db.commit()
    db.refresh(alias)
    return alias


def reject_material_alias(
    db: Session,
    alias_id: int,
    reviewer_id: str,
    comments: str,
) -> MaterialAlias:
    """
    Rejects a pending alias mapping. Rejection requires non-empty comments.
    """
    if not comments or not comments.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection justification comments are mandatory",
        )
    alias = db.execute(
        select(MaterialAlias).where(MaterialAlias.id == alias_id)
    ).scalar_one_or_none()
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material alias ID {alias_id} not found",
        )
    
    from_status = alias.status
    alias.status = AliasApprovalStatus.REJECTED.value
    alias.is_active = False
    alias.reviewer_id = reviewer_id
    alias.reviewed_at = datetime.now(timezone.utc)
    alias.decision_notes = comments.strip()
    
    audit = MaterialAliasAuditLog(
        alias_id=alias.id,
        action="REJECTED",
        from_status=from_status,
        to_status=alias.status,
        actor_id=reviewer_id,
        comments=comments.strip(),
    )
    db.add(audit)
    db.commit()
    db.refresh(alias)
    return alias


def deactivate_material_alias(
    db: Session,
    alias_id: int,
    user_id: str,
    comments: Optional[str] = None,
) -> MaterialAlias:
    """
    Deactivates an active alias without deleting historical records.
    """
    alias = db.execute(
        select(MaterialAlias).where(MaterialAlias.id == alias_id)
    ).scalar_one_or_none()
    if not alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material alias ID {alias_id} not found",
        )
    
    alias.is_active = False
    audit = MaterialAliasAuditLog(
        alias_id=alias.id,
        action="DEACTIVATED",
        from_status=alias.status,
        to_status="INACTIVE",
        actor_id=user_id,
        comments=comments or "Deactivated by user",
    )
    db.add(audit)
    db.commit()
    db.refresh(alias)
    return alias


def resolve_material_by_description(
    db: Session,
    raw_description: str,
) -> Optional[MaterialItem]:
    """
    Resolves raw description string against:
    1. Direct match with MaterialItem name (normalized) or item_code
    2. Approved and active MaterialAlias mapping
    Returns MaterialItem if resolved, None otherwise.
    Never uses silent fuzzy auto-matching.
    """
    if not raw_description or not raw_description.strip():
        return None
    
    cleaned = raw_description.strip()
    norm_key = normalize_alias_key(cleaned)
    if not norm_key:
        return None
    
    # 1. Direct match by item_code (exact upper)
    direct_code = db.execute(
        select(MaterialItem).where(
            func.upper(MaterialItem.item_code) == cleaned.upper(),
            MaterialItem.is_active == True,
        )
    ).scalar_one_or_none()
    if direct_code:
        return direct_code
    
    # 2. Check approved active aliases
    alias = db.execute(
        select(MaterialAlias).where(
            MaterialAlias.normalized_alias_key == norm_key,
            MaterialAlias.is_active == True,
            MaterialAlias.status == AliasApprovalStatus.APPROVED.value,
        )
    ).scalar_one_or_none()
    if alias:
        item = db.execute(
            select(MaterialItem).where(
                MaterialItem.id == alias.material_item_id,
                MaterialItem.is_active == True,
            )
        ).scalar_one_or_none()
        if item:
            return item
    
    # 3. Direct match by MaterialItem name (lowercased without punctuation)
    # Search all active items
    all_items = db.execute(
        select(MaterialItem).where(MaterialItem.is_active == True)
    ).scalars().all()
    for it in all_items:
        if normalize_alias_key(it.name) == norm_key:
            return it
    
    return None


def list_material_aliases(
    db: Session,
    status_filter: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[MaterialAlias], int]:
    """
    Lists material aliases with optional filters and pagination.
    """
    stmt = select(MaterialAlias)
    if status_filter:
        stmt = stmt.where(MaterialAlias.status == status_filter)
    if is_active is not None:
        stmt = stmt.where(MaterialAlias.is_active == is_active)
    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            MaterialAlias.alias_text.ilike(s) | MaterialAlias.normalized_alias_key.ilike(s)
        )
    
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(MaterialAlias.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return items, total
