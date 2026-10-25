from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.session import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorRead, PaginatedVendorsResponse
from app.services.validators import normalize_vendor_name
from app.core.security import require_permission, Permission

router = APIRouter()


@router.get("", response_model=PaginatedVendorsResponse, summary="List and Search Vendors")
def list_vendors(
    q: Optional[str] = Query(None, description="Search query across vendor name, contact person, or GSTIN"),
    is_active: Optional[bool] = Query(True, description="Filter active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(25, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.VENDOR_READ)),
):
    """
    Search and list vendor master records.
    Filters by normalized name, contact details, or GSTIN.
    """
    try:
        stmt = select(Vendor)

        if is_active is not None:
            stmt = stmt.where(Vendor.is_active == is_active)

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(Vendor.name).like(term)) |
                (func.lower(Vendor.normalized_name).like(term)) |
                (func.lower(Vendor.gstin).like(term)) |
                (func.lower(Vendor.contact_person).like(term))
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Paginate
        offset = (page - 1) * size
        vendors = db.scalars(stmt.order_by(Vendor.name).offset(offset).limit(size)).all()

        return PaginatedVendorsResponse(
            items=[VendorRead.model_validate(v) for v in vendors],
            total=total,
            page=page,
            size=size,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while querying vendors: {str(exc.__class__.__name__)}. Ensure PostgreSQL is online."
        )


@router.get("/{vendor_id}", response_model=VendorRead, summary="Get Vendor Details")
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.VENDOR_READ)),
):
    """Retrieves single vendor master details."""
    try:
        v = db.get(Vendor, vendor_id)
        if not v:
            raise HTTPException(status_code=404, detail="Vendor not found.")
        return VendorRead.model_validate(v)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving vendor: {str(exc.__class__.__name__)}"
        )


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED, summary="Create New Vendor")
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.VENDOR_MANAGE)),
):
    """
    Creates a new vendor record.
    Enforces normalized name deduplication and GSTIN format syntax validation.
    Preserves original name for official display and invoice auditing.
    """
    normalized = normalize_vendor_name(payload.name)
    if not normalized:
        raise HTTPException(status_code=400, detail="Vendor name cannot be empty or solely punctuation.")

    try:
        # Check duplicate normalized name
        existing = db.scalar(select(Vendor).where(Vendor.normalized_name == normalized))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate vendor conflict: Vendor '{existing.name}' already exists with normalized key '{normalized}'."
            )

        vendor = Vendor(
            name=payload.name.strip(),
            normalized_name=normalized,
            gstin=payload.gstin,
            address=payload.address,
            contact_person=payload.contact_person,
            phone=payload.phone,
            email=payload.email,
            is_active=True,
        )
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return VendorRead.model_validate(vendor)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor with identical normalized name already exists."
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while creating vendor: {str(exc.__class__.__name__)}"
        )


@router.put("/{vendor_id}", response_model=VendorRead, summary="Update Vendor Details")
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.VENDOR_MANAGE)),
):
    """
    Updates an existing vendor record.
    Re-validates normalized name uniqueness if name is changed.
    """
    v = db.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    try:
        if payload.name is not None and payload.name.strip():
            new_name = payload.name.strip()
            normalized = normalize_vendor_name(new_name)
            if not normalized:
                raise HTTPException(status_code=400, detail="Vendor name cannot be empty or solely punctuation.")

            # Check duplicate normalized key against OTHER vendors
            existing = db.scalar(
                select(Vendor).where(
                    Vendor.normalized_name == normalized,
                    Vendor.id != vendor_id,
                )
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate vendor conflict: Vendor '{existing.name}' already exists with normalized key '{normalized}'."
                )
            v.name = new_name
            v.normalized_name = normalized

        if payload.gstin is not None:
            v.gstin = payload.gstin

        if payload.address is not None:
            v.address = payload.address.strip() if payload.address.strip() else None

        if payload.contact_person is not None:
            v.contact_person = payload.contact_person.strip() if payload.contact_person.strip() else None

        if payload.phone is not None:
            v.phone = payload.phone.strip() if payload.phone.strip() else None

        if payload.email is not None:
            v.email = payload.email.strip() if payload.email.strip() else None

        if payload.is_active is not None:
            v.is_active = payload.is_active

        db.commit()
        db.refresh(v)
        return VendorRead.model_validate(v)
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor with identical normalized name already exists."
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while updating vendor: {str(exc.__class__.__name__)}"
        )
