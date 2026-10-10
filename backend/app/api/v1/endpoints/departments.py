from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.department import Department
from app.schemas.department import DepartmentRead
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
