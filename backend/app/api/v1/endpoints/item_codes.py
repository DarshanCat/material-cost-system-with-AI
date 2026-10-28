from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.services.item_code_service import ItemCodeService
from app.core.security import require_permission, Permission

router = APIRouter()


class ItemCodePreviewRequest(BaseModel):
    """All fields optional so the guided form can preview while it is still incomplete."""

    department_id: Optional[int] = None
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    uom_id: Optional[int] = None
    exclude_request_id: Optional[int] = Field(None, description="Request being edited or reviewed (excluded from duplicate search)")


@router.get("/rules", summary="Item Nomenclature Standard v1.0 rules")
def get_item_code_rules(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_REQUEST_READ)),
):
    """Departments, categories (owner and cost head), UOMs, abbreviations and description patterns, with database IDs."""
    try:
        return ItemCodeService(db).rules()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while loading item code rules: {str(exc.__class__.__name__)}"
        )


@router.post("/preview", summary="Validate a proposed item and preview its code (non-reserving)")
def preview_item_code(
    payload: ItemCodePreviewRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_REQUEST_READ)),
):
    """
    Validates the proposal against v1.0, searches for duplicates and shows the provisional next code.
    Nothing is written and no serial is reserved: the final code is allocated only at approval.
    """
    try:
        return ItemCodeService(db).preview(
            department_id=payload.department_id,
            category=payload.category,
            description=payload.description,
            uom_id=payload.uom_id,
            exclude_request_id=payload.exclude_request_id,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while previewing item code: {str(exc.__class__.__name__)}"
        )


@router.get("/compliance", summary="Report existing (grandfathered) item codes that do not follow v1.0")
def item_code_compliance(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_READ)),
):
    """Read-only. Legacy records are reported, never rejected, renamed, deactivated or migrated."""
    try:
        return ItemCodeService(db).compliance_report()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while checking item code compliance: {str(exc.__class__.__name__)}"
        )
