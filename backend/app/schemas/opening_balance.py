"""
Pydantic Schemas for Opening Balance Imports and Posting.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class OpeningBalanceItemRow(BaseModel):
    item_code: str
    quantity: Decimal
    uom_code: str
    baseline_date: date = Field(default_factory=lambda: date(2026, 10, 12))
    notes: Optional[str] = None


class OpeningBalancePreviewRow(BaseModel):
    row_number: int
    item_code: str
    item_name: Optional[str] = None
    uom_code: str
    quantity: Decimal
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class OpeningBalancePreviewSummary(BaseModel):
    total_rows: int
    valid_rows_count: int
    error_rows_count: int
    can_commit: bool
    baseline_date: str
    findings: List[OpeningBalancePreviewRow] = []


class OpeningBalancePostRequest(BaseModel):
    baseline_date: date = Field(default_factory=lambda: date(2026, 10, 12))
    audit_reference: str = Field(..., min_length=3, description="Reference to approved physical inventory audit document")
    rows: List[OpeningBalanceItemRow]
    approver_id: Optional[str] = None  # ignored: overwritten server-side from the verified identity
    approver_comments: Optional[str] = None
