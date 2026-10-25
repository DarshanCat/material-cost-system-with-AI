from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.item import MaterialItem
from app.schemas.item import (
    MaterialItemRead,
    PaginatedItemsResponse,
    ItemCategoryRead,
    MaterialItemUpdate,
)
from app.services.validators import get_material_categories_list
from app.core.security import require_permission, Permission

router = APIRouter()


@router.get("/categories", response_model=List[ItemCategoryRead], summary="List Supported Material Categories")
def list_material_categories(
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """Retrieves standard categorized domain groupings for the foundry item master."""
    return get_material_categories_list()


@router.get("", response_model=PaginatedItemsResponse, summary="Search and Filter Material Master Items")
def list_items(
    q: Optional[str] = Query(None, description="Search query by item code or name"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(True, description="Filter active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(25, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """
    Search and filter material master items.
    Supports search across 741 items without fabricating artificial balances.
    """
    try:
        stmt = select(MaterialItem)

        if is_active is not None:
            stmt = stmt.where(MaterialItem.is_active == is_active)

        if department_id:
            stmt = stmt.where(MaterialItem.department_id == department_id)

        if category:
            stmt = stmt.where(MaterialItem.category == category.upper())

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(MaterialItem.item_code).like(term)) | (func.lower(MaterialItem.name).like(term))
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Paginate
        offset = (page - 1) * size
        items = db.scalars(stmt.order_by(MaterialItem.item_code).offset(offset).limit(size)).all()

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
            size=size,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while querying items: {str(exc.__class__.__name__)}. Ensure PostgreSQL is online."
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
    _user=Depends(require_permission(Permission.ITEM_UPDATE)),
):
    """
    Updates non-key master item metadata (name, subcategory, description, active status).
    Preserves immutable item code, department reference, and base UOM.
    """
    try:
        it = db.get(MaterialItem, item_id)
        if not it:
            raise HTTPException(status_code=404, detail="Material item not found.")

        if payload.name is not None and payload.name.strip():
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
            it.name = new_name

        if payload.subcategory is not None:
            it.subcategory = payload.subcategory.strip().upper() if payload.subcategory.strip() else None

        if payload.description is not None:
            it.description = payload.description.strip() if payload.description.strip() else None

        if payload.is_active is not None:
            it.is_active = payload.is_active

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
