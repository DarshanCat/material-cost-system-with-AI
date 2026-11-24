from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.session import get_db
from app.models.department import Department
from app.schemas.department import DepartmentRead, DepartmentCreate
from app.core.security import require_permission, Permission

router = APIRouter()


@router.get("", response_model=List[DepartmentRead], summary="List Plant Departments")
def list_departments(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.DEPARTMENT_READ)),
):
    """Lists all active plant operational departments."""
    try:
        departments = db.scalars(select(Department).where(Department.is_active == True).order_by(Department.name)).all()
        return departments
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving departments: {str(exc.__class__.__name__)}. Ensure PostgreSQL is online."
        )


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED, summary="Create Plant Department")
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.DEPARTMENT_MANAGE)),
):
    """
    Creates a new plant operational department.
    Enforces uppercase code standard and uniqueness of code and name.
    Restricted to Management and Admin roles.
    """
    clean_code = payload.code.strip().upper()
    clean_name = payload.name.strip()
    if not clean_code or not clean_name:
        raise HTTPException(status_code=400, detail="Department code and name cannot be empty.")

    try:
        existing = db.scalar(
            select(Department).where(
                (func.upper(Department.code) == clean_code) |
                (func.lower(Department.name) == clean_name.lower())
            )
        )
        if existing:
            if existing.code.upper() == clean_code:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department with code '{clean_code}' already exists ({existing.name})."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department with name '{clean_name}' already exists with code '{existing.code}'."
                )

        dept = Department(
            code=clean_code,
            name=clean_name,
            is_active=True
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
        return dept
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department conflict: code '{clean_code}' or name '{clean_name}' already exists."
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while creating department: {str(exc.__class__.__name__)}"
        )


@router.get("/{department_id}", response_model=DepartmentRead, summary="Get Department Details")
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.DEPARTMENT_READ)),
):
    """Retrieves single department details by ID."""
    try:
        dept = db.get(Department, department_id)
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found.")
        return dept
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving department: {str(exc.__class__.__name__)}"
        )
