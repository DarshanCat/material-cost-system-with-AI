"""
Excel Import API Endpoints.
Provides template download, sheet upload validation preview, and atomic execution.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.excel_import import (
    ExcelImportValidationSummary,
    ExcelImportCommitRequest,
)
from app.services.excel_import_service import (
    parse_and_validate_excel,
    commit_excel_import,
    generate_template_excel,
)

router = APIRouter()


@router.get("/template/{import_type}")
def download_excel_template(
    import_type: str,
    _user: AuthenticatedUser = Depends(require_permission(Permission.EXCEL_IMPORT)),
):
    """Downloads blank Excel template with headers and column formatting."""
    clean_type = import_type.upper()
    if clean_type not in ["GRN", "ISSUE", "WASTE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid import type '{import_type}'. Must be GRN, ISSUE, or WASTE.",
        )
    file_bytes = generate_template_excel(clean_type)
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="VSPL_{clean_type}_Import_Template.xlsx"'
        },
    )


@router.post("/validate", response_model=ExcelImportValidationSummary)
async def validate_excel_upload(
    import_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.EXCEL_IMPORT)),
):
    """
    Validates uploaded Excel file without committing changes.
    Returns preview summary, errors, and warnings row-by-row.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only modern Excel (.xlsx, .xlsm) files are accepted.",
        )

    content = await file.read()
    summary = parse_and_validate_excel(content, import_type, db)
    return summary


@router.post("/commit")
def commit_validated_batch(
    payload: ExcelImportCommitRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.EXCEL_IMPORT)),
):
    """
    Commits validated rows atomically within a single transaction.
    """
    # Acting user comes from the verified identity; any client-supplied created_by is overwritten.
    payload.created_by = user.user_id
    try:
        result = commit_excel_import(payload, db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Atomic import failed and was rolled back: {str(e)}",
        )
