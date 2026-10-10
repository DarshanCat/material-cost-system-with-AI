"""
Material Description Alias Master API Endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user_role, get_current_user_id
from app.schemas.material_alias import (
    MaterialAliasCreate,
    MaterialAliasRead,
    MaterialAliasReview,
    MaterialAliasReject,
)
from app.services.material_alias_service import (
    create_material_alias,
    approve_material_alias,
    reject_material_alias,
    deactivate_material_alias,
    list_material_aliases,
)

router = APIRouter()


@router.post("", response_model=MaterialAliasRead, status_code=status.HTTP_201_CREATED)
def api_create_alias(
    payload: MaterialAliasCreate,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Creates a new material alias mapping.
    Restricted to Stores, Foundry, Management, Admin.
    """
    if current_role not in ("Stores", "Foundry", "Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to create material aliases",
        )
    return create_material_alias(
        db=db,
        alias_text=payload.alias_text,
        material_item_id=payload.material_item_id,
        created_by=current_user_id,
        status_val=payload.status,
    )


@router.get("", response_model=List[MaterialAliasRead])
def api_list_aliases(
    status_filter: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Lists material aliases with optional filters and pagination."""
    items, _ = list_material_aliases(
        db=db,
        status_filter=status_filter,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return items


@router.post("/{id}/approve", response_model=MaterialAliasRead)
def api_approve_alias(
    id: int,
    payload: MaterialAliasReview,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Approves a pending alias mapping.
    Restricted to Management and Admin roles.
    """
    if current_role not in ("Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to approve material aliases",
        )
    return approve_material_alias(
        db=db,
        alias_id=id,
        reviewer_id=current_user_id,
        comments=payload.decision_notes,
    )


@router.post("/{id}/reject", response_model=MaterialAliasRead)
def api_reject_alias(
    id: int,
    payload: MaterialAliasReject,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Rejects a pending alias mapping. Justification notes required.
    Restricted to Management and Admin roles.
    """
    if current_role not in ("Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to reject material aliases",
        )
    return reject_material_alias(
        db=db,
        alias_id=id,
        reviewer_id=current_user_id,
        comments=payload.decision_notes,
    )


@router.post("/{id}/deactivate", response_model=MaterialAliasRead)
def api_deactivate_alias(
    id: int,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """Deactivates an active alias without deleting historical records."""
    if current_role not in ("Stores", "Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to deactivate material aliases",
        )
    return deactivate_material_alias(
        db=db,
        alias_id=id,
        user_id=current_user_id,
    )
