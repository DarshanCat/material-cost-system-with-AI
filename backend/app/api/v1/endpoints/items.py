from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.item import MaterialItem
from app.models.item_code import ItemCodeRegistry, ItemMasterAction, ItemMasterAuditLog
from app.schemas.item import (
    MaterialItemRead,
    PaginatedItemsResponse,
    ItemCategoryRead,
    MaterialItemUpdate,
    ItemHistoryResponse,
    ItemCodeRegistryRead,
    ItemHistoryEventRead,
)
from app.services import item_nomenclature as std
from app.services.item_code_service import ItemCodeService
from app.core.security import require_permission, Permission, DevUserContext

router = APIRouter()

MIN_CHANGE_REASON_LENGTH = 5


@router.get("/categories", response_model=List[ItemCategoryRead], summary="List Supported Material Categories")
def list_material_categories(
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """Categories of the Item Nomenclature Standard v1.0 (Section 4), with owning department and cost head."""
    return [
        ItemCategoryRead(
            category=rule.name,
            code=rule.code,
            name=rule.name,
            description=f"{std.DEPARTMENTS[rule.department_code]} · {rule.cost_head}",
            department_code=rule.department_code,
            cost_head=rule.cost_head,
        )
        for rule in std.CATEGORIES.values()
    ]


@router.get("", response_model=PaginatedItemsResponse, summary="Search and Filter Material Master Items")
def list_items(
    q: Optional[str] = Query(None, description="Search query by item code or name"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(True, description="Filter active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(25, ge=1, le=1000, description="Page size"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Alias for page size"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """
    Search and filter material master items.
    Supports search across 741 items without fabricating artificial balances.
    """
    effective_size = limit if limit is not None else size
    try:
        filters = []
        if is_active is not None:
            filters.append(MaterialItem.is_active == is_active)

        if department_id:
            filters.append(MaterialItem.department_id == department_id)

        if category:
            # Stored category text is kept exactly as approved (e.g. 'Bolts & Nuts'); match case-insensitively.
            filters.append(func.lower(MaterialItem.category) == category.lower())

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                (func.lower(MaterialItem.item_code).like(term)) | (func.lower(MaterialItem.name).like(term))
            )

        # Count total
        count_stmt = select(func.count(MaterialItem.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = db.scalar(count_stmt) or 0

        # Paginate
        offset = (page - 1) * effective_size
        stmt = (
            select(MaterialItem)
            .options(
                joinedload(MaterialItem.department),
                joinedload(MaterialItem.base_uom),
            )
        )
        if filters:
            stmt = stmt.where(*filters)
        items = db.scalars(stmt.order_by(MaterialItem.item_code).offset(offset).limit(effective_size)).unique().all()

        results = []
        for it in items:
            it_read = MaterialItemRead.model_validate(it)
            if it.department:
                it_read.department_name = it.department.name
            if it.base_uom:
                it_read.uom_code = it.base_uom.code
            results.append(it_read)

        return PaginatedItemsResponse(
            items=results,
            total=total,
            page=page,
            size=effective_size,
        )
    except SQLAlchemyError as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while querying items: {str(exc)}. Ensure PostgreSQL is online."
        )


@router.get("/{item_id}", response_model=MaterialItemRead, summary="Get Item Details")
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """Retrieves single material master item details."""
    try:
        it = db.get(MaterialItem, item_id)
        if not it:
            raise HTTPException(status_code=404, detail="Material item not found.")

        it_read = MaterialItemRead.model_validate(it)
        if it.department:
            it_read.department_name = it.department.name
        if it.base_uom:
            it_read.uom_code = it.base_uom.code
        return it_read
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving item: {str(exc.__class__.__name__)}"
        )


@router.put("/{item_id}", response_model=MaterialItemRead, summary="Update Master Item Metadata")
def update_item(
    item_id: int,
    payload: MaterialItemUpdate,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_UPDATE)),
):
    """
    Updates non-key master item metadata (name, subcategory, description, active status).
    Preserves immutable item code, department reference, and base UOM.

    Every change is recorded in the append-only item history. Renaming (a description correction) and
    retiring / reactivating require `change_reason`; ITEM_UPDATE is held by the approving roles only
    (Management, Admin). Retiring never frees the code: codes are permanent and never reused.
    Legacy (non-v1.0) items are editable here without being forced through new-item validation.
    """
    try:
        it = db.get(MaterialItem, item_id)
        if not it:
            raise HTTPException(status_code=404, detail="Material item not found.")

        codes = ItemCodeService(db)
        codes.require_registry()
        reason = payload.change_reason.strip() if payload.change_reason and payload.change_reason.strip() else None
        changes: list[tuple[str, str, Optional[str], Optional[str]]] = []  # (action, field, old, new)

        if payload.name is not None and payload.name.strip() and payload.name.strip() != it.name:
            new_name = payload.name.strip()
            conflict = db.scalar(
                select(MaterialItem).where(
                    MaterialItem.department_id == it.department_id,
                    func.lower(MaterialItem.name) == func.lower(new_name),
                    MaterialItem.id != item_id,
                    MaterialItem.is_active == True,
                )
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict detected: Item '{conflict.name}' already exists in this department with code '{conflict.item_code}'."
                )
            # One material, one code: a correction must not make this item a duplicate of any other item.
            other = next(
                (m for m in codes.find_duplicates(new_name) if m.source in ("ITEM", "ALIAS") and m.item_id != item_id),
                None,
            )
            if other:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict detected: '{new_name}' matches existing item {other.item_code} ('{other.name}').",
                )
            changes.append((ItemMasterAction.RENAMED, "name", it.name, new_name))
            it.name = new_name

        if payload.subcategory is not None:
            new_sub = payload.subcategory.strip().upper() if payload.subcategory.strip() else None
            if new_sub != it.subcategory:
                changes.append((ItemMasterAction.METADATA_UPDATED, "subcategory", it.subcategory, new_sub))
                it.subcategory = new_sub

        if payload.description is not None:
            new_desc = payload.description.strip() if payload.description.strip() else None
            if new_desc != it.description:
                changes.append((ItemMasterAction.METADATA_UPDATED, "description", it.description, new_desc))
                it.description = new_desc

        if payload.reconciliation_category is not None:
            new_recon = payload.reconciliation_category.strip().upper() if payload.reconciliation_category.strip() else None
            if new_recon and new_recon not in std.RECONCILIATION_CATEGORIES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid reconciliation_category '{new_recon}'. Allowed: {sorted(std.RECONCILIATION_CATEGORIES)}"
                )
            curr_recon = getattr(it, "reconciliation_category", None)
            if new_recon != curr_recon:
                changes.append((ItemMasterAction.METADATA_UPDATED, "reconciliation_category", curr_recon, new_recon))
                it.reconciliation_category = new_recon

        if payload.is_active is not None and payload.is_active != it.is_active:
            action = ItemMasterAction.REACTIVATED if payload.is_active else ItemMasterAction.RETIRED
            changes.append((action, "is_active", str(it.is_active), str(payload.is_active)))
            it.is_active = payload.is_active

        needs_reason = [
            c for c in changes 
            if c[0] in (ItemMasterAction.RENAMED, ItemMasterAction.RETIRED, ItemMasterAction.REACTIVATED) 
            or c[1] == "reconciliation_category"
        ]
        if needs_reason and (reason is None or len(reason) < MIN_CHANGE_REASON_LENGTH):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"change_reason (at least {MIN_CHANGE_REASON_LENGTH} characters) is required to "
                    + " / ".join(sorted({(c[1] if c[1] == "reconciliation_category" else c[0]).lower() for c in needs_reason}))
                    + " an item. The change is recorded in the item history."
                ),
            )

        for action, field_name, old, new in changes:
            db.add(
                ItemMasterAuditLog(
                    material_item_id=it.id,
                    item_code=it.item_code,
                    action=action,
                    field_name=field_name,
                    old_value=old,
                    new_value=new,
                    reason=reason,
                    actor_id=user.user_id,
                    actor_role=user.role.value,
                )
            )

        db.commit()
        db.refresh(it)

        it_read = MaterialItemRead.model_validate(it)
        if it.department:
            it_read.department_name = it.department.name
        if it.base_uom:
            it_read.uom_code = it.base_uom.code
        return it_read
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while updating item: {str(exc.__class__.__name__)}"
        )


@router.get("/{item_id}/history", response_model=ItemHistoryResponse, summary="Item Code Registry Entry and Item History")
def get_item_history(
    item_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """Permanent registry entry (for generator-issued codes) and the append-only change history of the item."""
    try:
        it = db.get(MaterialItem, item_id)
        if not it:
            raise HTTPException(status_code=404, detail="Material item not found.")

        if not ItemCodeService(db).registry_installed():
            return ItemHistoryResponse(item_id=it.id, item_code=it.item_code, registry_installed=False)

        registry = db.scalar(select(ItemCodeRegistry).where(ItemCodeRegistry.material_item_id == it.id))
        events = db.scalars(
            select(ItemMasterAuditLog)
            .where(ItemMasterAuditLog.material_item_id == it.id)
            .order_by(ItemMasterAuditLog.timestamp, ItemMasterAuditLog.id)
        ).all()
        return ItemHistoryResponse(
            item_id=it.id,
            item_code=it.item_code,
            registry_installed=True,
            registry=ItemCodeRegistryRead.model_validate(registry) if registry else None,
            events=[ItemHistoryEventRead.model_validate(e) for e in events],
        )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving item history: {str(exc.__class__.__name__)}"
        )
