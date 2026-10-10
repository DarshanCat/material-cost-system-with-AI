from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.uom import UOM
from app.schemas.uom import UOMRead
from app.core.security import require_permission, Permission

router = APIRouter()


@router.get("", response_model=List[UOMRead], summary="List Controlled UOMs")
def list_uoms(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.UOM_READ)),
):
    """Lists all active units of measurement with decimal precision settings."""
    try:
        uoms = db.scalars(select(UOM).where(UOM.is_active == True).order_by(UOM.code)).all()
        return uoms
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving UOMs: {str(exc.__class__.__name__)}. Ensure PostgreSQL is online."
        )


@router.get("/{uom_id}", response_model=UOMRead, summary="Get UOM Details")
def get_uom(
    uom_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.UOM_READ)),
):
    """Retrieves single UOM details by ID."""
    try:
        uom = db.get(UOM, uom_id)
        if not uom:
            raise HTTPException(status_code=404, detail="UOM not found.")
        return uom
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving UOM: {str(exc.__class__.__name__)}"
        )
