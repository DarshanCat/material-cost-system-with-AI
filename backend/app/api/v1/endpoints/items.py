from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.item import MaterialItem
from app.schemas.item import MaterialItemRead, PaginatedItemsResponse
from app.core.security import require_permission, Permission

router = APIRouter()


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
