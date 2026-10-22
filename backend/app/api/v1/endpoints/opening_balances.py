"""
Opening Balance API Endpoints.
Provides template download, preview validation, and atomic posting of approved baselines.
"""

from typing import List, Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status, HTTPException, Response
from sqlalchemy.orm import Session
import openpyxl
import io

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.opening_balance import (
    OpeningBalanceItemRow,
    OpeningBalancePreviewSummary,
    OpeningBalancePostRequest,
)
from app.services.opening_balance_service import (
    preview_opening_balances,
    post_approved_opening_balances,
)

router = APIRouter()


@router.get("/template")
def download_opening_balance_template(
    _user: AuthenticatedUser = Depends(require_permission(Permission.OPENING_BALANCE_POST)),
):
    """Generates blank Excel template for opening balance data collection."""
    headers = ["Item Code", "Quantity", "UOM", "Baseline Date", "Notes"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Opening_Balances"

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 20

    # Example row
    ws.append(["FDY-RM-001", "12500.00", "KG", "2026-10-12", "Foundry Pig Iron physical yard count"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="VSPL_Opening_Balance_Template_20261012.xlsx"'
        },
    )


@router.post("/preview", response_model=OpeningBalancePreviewSummary)
def preview_opening_balance_import(
    rows: List[OpeningBalanceItemRow],
    baseline_date: Optional[date] = Query(date(2026, 10, 12), description="Baseline date (strictly 2026-10-12)"),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.OPENING_BALANCE_POST)),
):
    """
    Validates proposed opening balances without writing to ledger.
    """
    summary = preview_opening_balances(db, rows, baseline_date)
    return summary


@router.post("/post")
def post_opening_balance_batch(
    payload: OpeningBalancePostRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.OPENING_BALANCE_POST)),
):
    """
    Atomically posts approved opening balances to the append-only stock ledger.
    """
    # Acting user comes from the verified identity; any client-supplied approver_id is overwritten.
    payload.approver_id = user.user_id
    result = post_approved_opening_balances(db, payload)
    return result
