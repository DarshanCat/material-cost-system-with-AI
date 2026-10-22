"""
Material Description Alias Master API Endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import AuthenticatedUser, Permission, require_permission
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
    user: AuthenticatedUser = Depends(require_permission(Permission.ALIAS_CREATE)),
):
    """
    Creates a new material alias mapping.
    Restricted to Stores, Foundry, Management, Admin.
    """
    return create_material_alias(
        db=db,
        alias_text=payload.alias_text,
        material_item_id=payload.material_item_id,
        created_by=user.user_id,
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
    _user: AuthenticatedUser = Depends(require_permission(Permission.ITEM_READ)),
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
    user: AuthenticatedUser = Depends(require_permission(Permission.ALIAS_APPROVE)),
):
    """
    Approves a pending alias mapping.
    Restricted to Management and Admin roles.
    """
    return approve_material_alias(
        db=db,
        alias_id=id,
        reviewer_id=user.user_id,
        comments=payload.decision_notes,
    )


@router.post("/{id}/reject", response_model=MaterialAliasRead)
def api_reject_alias(
    id: int,
    payload: MaterialAliasReject,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.ALIAS_APPROVE)),
):
    """
    Rejects a pending alias mapping. Justification notes required.
    Restricted to Management and Admin roles.
    """
    return reject_material_alias(
        db=db,
        alias_id=id,
        reviewer_id=user.user_id,
        comments=payload.decision_notes,
    )


@router.post("/{id}/deactivate", response_model=MaterialAliasRead)
def api_deactivate_alias(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.ALIAS_DEACTIVATE)),
):
    """Deactivates an active alias without deleting historical records."""
    return deactivate_material_alias(
        db=db,
        alias_id=id,
        user_id=user.user_id,
    )
