"""
Heat Log Excel Import API Endpoints.
Provides template download, sheet upload validation preview, and atomic execution.
STRICT RULE: Heat log imports NEVER create stock movements.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import AuthenticatedUser, Permission, require_permission
from app.services.heat_import_service import (
    preview_heat_log_import,
    commit_heat_log_import,
    parse_excel_heat_log,
    generate_heat_log_template_excel,
)

router = APIRouter()


class HeatImportPreviewRequest(BaseModel):
    rows: List[Dict[str, Any]]


class HeatImportCommitRequest(BaseModel):
    rows: List[Dict[str, Any]]
    source_filename: Optional[str] = None


@router.get("/template")
def api_download_heat_import_template(
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """
    Downloads styled blank Excel (.xlsx) template for heat log imports.
    Restricted to Foundry, Management, Admin.
    """
    file_bytes = generate_heat_log_template_excel()
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="VSPL_Heat_Log_Import_Template.xlsx"'
        },
    )


@router.post("/upload", status_code=status.HTTP_200_OK)
async def api_upload_heat_import_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_CREATE)),
):
    """
    Direct Excel (.xlsx, .xlsm) upload for heat log imports.
    Parses workbook, validates row-by-row and in-batch header consistency, and returns dry-run preview.
    Zero database mutations or stock ledger entries created.
    Restricted to Foundry, Management, Admin.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only modern Excel (.xlsx, .xlsm) files are accepted.",
        )

    content = await file.read()
    rows = parse_excel_heat_log(content)
    preview = preview_heat_log_import(db, rows)
    preview["source_filename"] = file.filename
    return preview


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
