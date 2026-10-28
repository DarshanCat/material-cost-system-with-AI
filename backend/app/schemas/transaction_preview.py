"""
Pydantic Schemas for Transaction Import Preview and Dry-Run Source Validation.
Strictly read-only data structures for validating 12-15 October daily material entry workbooks.
"""

from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class PreviewRowStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    HELD_FOR_APPROVAL = "HELD_FOR_APPROVAL"
    DUPLICATE = "DUPLICATE"
    CONFLICTING = "CONFLICTING"
    REJECTED = "REJECTED"


class PreviewTransactionType(str, Enum):
    RECEIPT_GRN = "RECEIPT_GRN"
    GENERAL_ISSUE = "GENERAL_ISSUE"
    FURNACE_CHARGE = "FURNACE_CHARGE"
    WASTE_DISPOSITION = "WASTE_DISPOSITION"


class RowPreviewFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_file: str
    worksheet: str
    row_number: int
    activity_date: Optional[str] = None
    transaction_type: PreviewTransactionType
    item_code: Optional[str] = None
    item_description: Optional[str] = None
    quantity: Optional[Decimal] = None
    uom: Optional[str] = None
    document_ref: Optional[str] = None
    vendor_name: Optional[str] = None
    consuming_section: Optional[str] = None
    status: PreviewRowStatus
    reason: str
    is_furnace_charge: bool = False
    details: Dict[str, Any] = {}


class SourceFileVerification(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    sheet_names: List[str]
    receipt_grn_rows: int
    issue_rows: int
    waste_disposition_rows: int
    activity_dates: List[str]


class TransactionImportPreviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_read_only: bool = True
    total_files_scanned: int
    total_rows_scanned: int

    # Status Breakdown
    eligible_count: int
    held_for_approval_count: int
    duplicate_count: int
    conflicting_count: int
    rejected_count: int

    # Transaction Type Breakdown
    receipt_grn_count: int
    general_issue_count: int
    furnace_charge_count: int
    waste_disposition_count: int

    # Root Cause Breakdown
    unapproved_ledger_only_codes: int
    not_found_codes: int
    uom_mismatches: int
    blank_issue_slips: int
    zero_or_negative_quantities: int
    duplicate_waste_entries: int
    missing_mandatory_fields: int

    # File verifications & Row findings
    file_verifications: List[SourceFileVerification] = []
    findings: List[RowPreviewFinding] = []
    message: str
