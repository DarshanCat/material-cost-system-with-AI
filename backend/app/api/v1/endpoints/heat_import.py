"""
Heat Log Excel Import API Endpoints.
Provides preview validation and atomic batch commit for heat log workbooks.
STRICT RULE: Heat log imports NEVER create stock movements.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import AuthenticatedUser, Permission, require_permission
from app.services.heat_import_service import (
    preview_heat_log_import,
    commit_heat_log_import,
)

router = APIRouter()


class HeatImportPreviewRequest(BaseModel):
    rows: List[Dict[str, Any]]


class HeatImportCommitRequest(BaseModel):
    rows: List[Dict[str, Any]]
    source_filename: Optional[str] = None


@router.post("/preview", status_code=status.HTTP_200_OK)
def api_preview_heat_import(
    payload: HeatImportPreviewRequest,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_CREATE)),
):
    """
    Dry-run preview validation of heat log data.
    Restricted to Foundry, Management, Admin.
    """
    return preview_heat_log_import(db, payload.rows)


@router.post("/commit", status_code=status.HTTP_201_CREATED)
def api_commit_heat_import(
    payload: HeatImportCommitRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_CREATE)),
):
    """
    Atomically commits validated heat log batch.
    Rejects entire batch if any blocking errors exist.
    Restricted to Foundry, Management, Admin.
    """
    return commit_heat_log_import(
        db=db,
        rows=payload.rows,
        created_by=user.user_id,
        source_filename=payload.source_filename,
    )
