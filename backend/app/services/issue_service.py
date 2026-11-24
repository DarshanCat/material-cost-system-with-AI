"""
Service for Material Issue operations, department validation, and lifecycle transitions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.services.maker_checker import enforce_maker_checker, ISSUE
from app.services.posting_guard import ledger_write_guard
from app.models.issue import (
    MaterialIssueHeader,
    MaterialIssueLineItem,
    IssueAuditLog,
    IssueStatus,
)
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.issue import MaterialIssueCreate
from app.services.decimal_validator import validate_and_flag_quantity
from app.services.duplicate_detector import check_issue_slip_duplicate, check_duplicate_line_items
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)


def generate_issue_slip_number(db: Session, issue_date: date) -> str:
    """Generates sequential document number: ISS-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.ISSUE, issue_date)


def create_material_issue(
    db: Session,
    data: MaterialIssueCreate,
    created_by: str,
    auto_commit: bool = True,
    direct_issue: bool = False,
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

    # 2. Pre-validate line items before entering transaction retry block
    item_labels: dict[int, str] = {}
    validated_lines = []
    for idx, line in enumerate(data.lines, start=1):
        item = db.get(MaterialItem, line.material_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: Material Item ID {line.material_item_id} not found.",
            )
        item_labels[item.id] = item.item_code or item.name
        uom = db.get(UOM, line.uom_id)
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: UOM ID {line.uom_id} not found.",
            )

        qty_result = validate_and_flag_quantity(line.quantity, uom, item.category, item.name)
        if not qty_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Line {idx}: {'; '.join(qty_result.errors)}",
            )
        for w in qty_result.warnings:
            warnings.append(f"Line {idx} ({item.item_code}): {w}")

        validated_lines.append(line)

    # 2b. Check intra-document duplicate line items (non-blocking advisory warnings)
    warnings.extend(check_duplicate_line_items(data.lines, item_labels))

    # 3. Create document using bounded savepoint retry for collision safety
    initial_status = IssueStatus.APPROVED.value if direct_issue else IssueStatus.DRAFT.value

    def _create(slip_number: str) -> MaterialIssueHeader:
        header = MaterialIssueHeader(
            issue_slip_number=slip_number,
            issue_date=data.issue_date,
            issuing_department_id=data.issuing_department_id,
            receiving_department_id=data.receiving_department_id,
            heat_reference_number=data.heat_reference_number,
            notes=data.notes,
            status=initial_status,
            created_by=created_by,
        )
        db.add(header)
        db.flush()

        for idx, line in enumerate(validated_lines, start=1):
            line_rec = MaterialIssueLineItem(
                issue_id=header.id,
                line_number=idx,
                material_item_id=line.material_item_id,
                uom_id=line.uom_id,
                quantity=line.quantity,
                remarks=line.remarks,
            )
            db.add(line_rec)

        audit = IssueAuditLog(
            issue_id=header.id,
            action="APPROVED" if direct_issue else "CREATED",
            from_status=None,
            to_status=initial_status,
            actor_id=created_by,
            comments=(
                "Direct material issue by Stores. Posted outward entries to stock ledger."
                if direct_issue
                else "Material issue slip created in draft status."
            ),
        )
        db.add(audit)
        return header

    header = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.ISSUE,
        create_fn=_create,
        target_date=data.issue_date,
    )

    if direct_issue:
        from app.services.ledger_service import post_issue_to_ledger
        with ledger_write_guard(db):
            post_issue_to_ledger(db, header, created_by)

    if auto_commit:
        db.commit()
        db.refresh(header)
    else:
        db.flush()
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
    with ledger_write_guard(db):
        return _approve_material_issue(db, issue_id, actor_id, comments)


def _approve_material_issue(db: Session, issue_id: int, actor_id: str, comments: Optional[str] = None) -> MaterialIssueHeader:
    issue = db.get(MaterialIssueHeader, issue_id, with_for_update=True)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue slip not found.")
    enforce_maker_checker(ISSUE, issue.created_by, actor_id, f"issue slip {issue.issue_slip_number}")
    if issue.status not in (IssueStatus.SUBMITTED.value, IssueStatus.DRAFT.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve issue slip in status '{issue.status}'. Must be DRAFT or SUBMITTED.",
        )

    prev_status = issue.status
    issue.status = IssueStatus.APPROVED.value
    audit = IssueAuditLog(
        issue_id=issue.id,
        action="APPROVED",
        from_status=prev_status,
        to_status=issue.status,
        actor_id=actor_id,
        comments=comments or "Issue slip approved. Posted outward entries to stock ledger.",
    )
    db.add(audit)
    db.flush()

    # Atomically post to append-only stock ledger
    from app.services.ledger_service import post_issue_to_ledger
    post_issue_to_ledger(db, issue, actor_id)

    db.commit()
    db.refresh(issue)
    return issue


def direct_issue_slip(db: Session, issue_id: int, actor_id: str, comments: Optional[str] = None) -> MaterialIssueHeader:
    """Stores direct issue: issues draft or submitted slip directly to stock ledger without approval blocker."""
    with ledger_write_guard(db):
        issue = db.get(MaterialIssueHeader, issue_id, with_for_update=True)
        if not issue:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue slip not found.")
        if issue.status == IssueStatus.APPROVED.value:
            return issue
        if issue.status not in (IssueStatus.DRAFT.value, IssueStatus.SUBMITTED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot issue slip in status '{issue.status}'. Must be DRAFT or SUBMITTED.",
            )

        prev_status = issue.status
        issue.status = IssueStatus.APPROVED.value
        audit = IssueAuditLog(
            issue_id=issue.id,
            action="APPROVED",
            from_status=prev_status,
            to_status=issue.status,
            actor_id=actor_id,
            comments=comments or "Direct material issue by Stores. Posted outward entries to stock ledger.",
        )
        db.add(audit)
        db.flush()

        from app.services.ledger_service import post_issue_to_ledger
        post_issue_to_ledger(db, issue, actor_id)

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


# Re-export whole-document reversal service
from app.services.document_reversal_service import reverse_material_issue  # noqa: E402
