"""
Service for Material Issue transactions and state lifecycle.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueAuditLog, IssueStatus
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.issue import MaterialIssueCreate
from app.services.decimal_validator import validate_and_flag_quantity
from app.services.duplicate_detector import check_issue_slip_duplicate


def generate_issue_slip_number(db: Session, issue_date: date) -> str:
    """Generates sequential document number: ISS-YYYYMMDD-XXXX."""
    date_str = issue_date.strftime("%Y%m%d")
    prefix = f"ISS-{date_str}-"
    
    count_today = db.execute(
        select(func.count(MaterialIssueHeader.id)).where(MaterialIssueHeader.issue_slip_number.like(f"{prefix}%"))
    ).scalar_one()
    
    return f"{prefix}{count_today + 1:04d}"


def create_material_issue(
    db: Session, data: MaterialIssueCreate, created_by: str
) -> Tuple[MaterialIssueHeader, List[str]]:
    warnings: List[str] = []

    # 1. Department validations
    issuing_dept = db.get(Department, data.issuing_department_id)
    if not issuing_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuing Department ID {data.issuing_department_id} not found.",
        )
    receiving_dept = db.get(Department, data.receiving_department_id)
    if not receiving_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receiving Department ID {data.receiving_department_id} not found.",
        )

    # 2. Sequential Slip Number
    slip_number = generate_issue_slip_number(db, data.issue_date)

    header = MaterialIssueHeader(
        issue_slip_number=slip_number,
        issue_date=data.issue_date,
        issuing_department_id=data.issuing_department_id,
        receiving_department_id=data.receiving_department_id,
        heat_reference_number=data.heat_reference_number,
        notes=data.notes,
        status=IssueStatus.DRAFT.value,
        created_by=created_by,
    )
    db.add(header)
    db.flush()

    # 3. Process line items
    for idx, line in enumerate(data.lines, start=1):
        item = db.get(MaterialItem, line.material_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: Material Item ID {line.material_item_id} not found.",
            )
        uom = db.get(UOM, line.uom_id)
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: UOM ID {line.uom_id} not found.",
            )

        qty_result = validate_and_flag_quantity(line.quantity, uom, item.category, item.name)
        if not qty_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Line {idx}: {'; '.join(qty_result.errors)}",
            )
        for w in qty_result.warnings:
            warnings.append(f"Line {idx} ({item.item_code}): {w}")

        line_rec = MaterialIssueLineItem(
            issue_id=header.id,
            line_number=idx,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            quantity=line.quantity,
            remarks=line.remarks,
        )
        db.add(line_rec)

    # Initial audit
    audit = IssueAuditLog(
        issue_id=header.id,
        action="CREATED",
        from_status=None,
        to_status=IssueStatus.DRAFT.value,
        actor_id=created_by,
        comments="Material issue slip created in draft status.",
    )
    db.add(audit)
    db.commit()
    db.refresh(header)
    return header, warnings


def submit_material_issue(db: Session, issue_id: int, actor_id: str, comments: Optional[str] = None) -> MaterialIssueHeader:
    issue = db.get(MaterialIssueHeader, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue slip not found.")
    if issue.status != IssueStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit issue slip in status '{issue.status}'. Only DRAFT can be submitted.",
        )

    prev_status = issue.status
    issue.status = IssueStatus.SUBMITTED.value
    audit = IssueAuditLog(
        issue_id=issue.id,
        action="SUBMITTED",
        from_status=prev_status,
        to_status=issue.status,
        actor_id=actor_id,
        comments=comments or "Issue slip submitted for department sign-off.",
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)
    return issue


def approve_material_issue(db: Session, issue_id: int, actor_id: str, comments: Optional[str] = None) -> MaterialIssueHeader:
    issue = db.get(MaterialIssueHeader, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue slip not found.")
    if issue.status != IssueStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve issue slip in status '{issue.status}'. Must be SUBMITTED first.",
        )

    prev_status = issue.status
    issue.status = IssueStatus.APPROVED.value
    audit = IssueAuditLog(
        issue_id=issue.id,
        action="APPROVED",
        from_status=prev_status,
        to_status=issue.status,
        actor_id=actor_id,
        comments=comments or "Issue slip approved. (Note: Ledger deduction scheduled for Phase 4)",
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)
    return issue


def cancel_material_issue(db: Session, issue_id: int, actor_id: str, comments: Optional[str] = None) -> MaterialIssueHeader:
    issue = db.get(MaterialIssueHeader, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue slip not found.")
    if issue.status == IssueStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved issue slips cannot be cancelled directly.",
        )

    prev_status = issue.status
    issue.status = IssueStatus.CANCELLED.value
    audit = IssueAuditLog(
        issue_id=issue.id,
        action="CANCELLED",
        from_status=prev_status,
        to_status=issue.status,
        actor_id=actor_id,
        comments=comments or "Issue slip cancelled.",
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)
    return issue
