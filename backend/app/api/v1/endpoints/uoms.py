from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.session import get_db
from app.models.uom import UOM
from app.schemas.uom import UOMRead, UOMCreate
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


@router.post("", response_model=UOMRead, status_code=status.HTTP_201_CREATED, summary="Create Controlled UOM")
def create_uom(
    payload: UOMCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.UOM_MANAGE)),
):
    """
    Creates a new controlled Unit of Measurement with decimal precision.
    Enforces uppercase code standard and uniqueness of code.
    Restricted to Management and Admin roles.
    """
    clean_code = payload.code.strip().upper()
    clean_name = payload.name.strip()
    if not clean_code or not clean_name:
        raise HTTPException(status_code=400, detail="UOM code and name cannot be empty.")

    try:
        existing = db.scalar(
            select(UOM).where(func.upper(UOM.code) == clean_code)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"UOM with code '{clean_code}' already exists ({existing.name})."
            )

        uom = UOM(
            code=clean_code,
            name=clean_name,
            decimal_precision=payload.decimal_precision,
            is_active=True
        )
        db.add(uom)
        db.commit()
        db.refresh(uom)
        return uom
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"UOM conflict: code '{clean_code}' already exists."
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while creating UOM: {str(exc.__class__.__name__)}"
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
