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
from app.core.security import get_current_user_role, get_current_user_id
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
    current_role: str = Depends(get_current_user_role),
):
    """
    Dry-run preview validation of heat log data.
    Restricted to Foundry, Management, Admin.
    """
    if current_role not in ("Foundry", "Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to preview heat imports",
        )
    return preview_heat_log_import(db, payload.rows)


@router.post("/commit", status_code=status.HTTP_201_CREATED)
def api_commit_heat_import(
    payload: HeatImportCommitRequest,
    db: Session = Depends(get_db),
    current_role: str = Depends(get_current_user_role),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Atomically commits validated heat log batch.
    Rejects entire batch if any blocking errors exist.
    Restricted to Foundry, Management, Admin.
    """
    if current_role not in ("Foundry", "Management", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_role}' is not authorized to commit heat imports",
        )
    return commit_heat_log_import(
        db=db,
        rows=payload.rows,
        created_by=current_user_id,
        source_filename=payload.source_filename,
    )
