"""
Pydantic Schemas for Excel Import Validation and Atomic Execution.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class RowValidationFinding(BaseModel):
    row_number: int
    status: str  # "VALID", "WARNING", "ERROR"
    errors: List[str] = []
    warnings: List[str] = []
    raw_data: Dict[str, Any] = {}


class ExcelImportValidationSummary(BaseModel):
    total_rows: int
    valid_rows_count: int
    warning_rows_count: int
    error_rows_count: int
    can_commit: bool  # True ONLY if error_rows_count == 0
    message: str
    findings: List[RowValidationFinding] = []


class ExcelImportCommitRequest(BaseModel):
    import_type: str  # "GRN", "ISSUE", "WASTE"
    rows: List[Dict[str, Any]]
    created_by: str = "System Import"
