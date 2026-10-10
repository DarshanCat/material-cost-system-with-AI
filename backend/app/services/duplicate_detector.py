"""
Duplicate detection service for GRN and Material Issue transactions.
Enforces hard database uniqueness and soft audit warnings for potential double entry.
"""

from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.grn import GRNHeader
from app.models.issue import MaterialIssueHeader


class DuplicateCheckResult:
    def __init__(self, has_conflict: bool, is_blocking: bool, message: str, existing_doc_number: Optional[str] = None):
        self.has_conflict = has_conflict
        self.is_blocking = is_blocking
        self.message = message
        self.existing_doc_number = existing_doc_number

    def to_dict(self):
        return {
            "has_conflict": self.has_conflict,
            "is_blocking": self.is_blocking,
            "message": self.message,
            "existing_doc_number": self.existing_doc_number,
        }


def check_grn_invoice_duplicate(
    db: Session,
    vendor_id: Optional[int],
    invoice_number: Optional[str],
    invoice_date: Optional[date],
    exclude_grn_id: Optional[int] = None,
) -> DuplicateCheckResult:
    """
    Checks if a vendor invoice has already been processed under an existing GRN.
    Flags warning / audit concern if (vendor_id, invoice_number, invoice_date) exists.
    """
    if not vendor_id or not invoice_number:
        return DuplicateCheckResult(False, False, "No vendor invoice details provided for duplicate check.")

    norm_inv = invoice_number.strip().upper()
    query = select(GRNHeader).where(
        GRNHeader.vendor_id == vendor_id,
        GRNHeader.vendor_invoice_no.ilike(norm_inv),
    )
    if invoice_date:
        query = query.where(GRNHeader.invoice_date == invoice_date)
    if exclude_grn_id:
        query = query.where(GRNHeader.id != exclude_grn_id)

    existing = db.execute(query).scalars().first()
    if existing:
        return DuplicateCheckResult(
            has_conflict=True,
            is_blocking=False,  # Soft warning with explicit traceability flag
            message=f"Possible duplicate invoice: Invoice '{invoice_number}' for this vendor was already received on GRN {existing.grn_number} dated {existing.receipt_date}.",
            existing_doc_number=existing.grn_number,
        )

    return DuplicateCheckResult(False, False, "No duplicate vendor invoice found.")


def check_issue_slip_duplicate(
    db: Session,
    issue_slip_number: str,
    issue_date: date,
    receiving_department_id: int,
    exclude_issue_id: Optional[int] = None,
) -> DuplicateCheckResult:
    """
    Checks if an issue slip number has already been entered.
    Document number uniqueness is a hard blocking rule.
    """
    norm_slip = issue_slip_number.strip().upper()
    query = select(MaterialIssueHeader).where(
        MaterialIssueHeader.issue_slip_number.ilike(norm_slip)
    )
    if exclude_issue_id:
        query = query.where(MaterialIssueHeader.id != exclude_issue_id)

    existing = db.execute(query).scalars().first()
    if existing:
        return DuplicateCheckResult(
            has_conflict=True,
            is_blocking=True,
            message=f"Duplicate issue slip: Slip number '{norm_slip}' already exists with ID {existing.id} on date {existing.issue_date}.",
            existing_doc_number=existing.issue_slip_number,
        )

    return DuplicateCheckResult(False, False, "No duplicate issue slip found.")
