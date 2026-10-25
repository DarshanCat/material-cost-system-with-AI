"""
Pydantic Schemas for Whole-Document Reversals (SW-07).
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentReversalRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Mandatory audit justification for whole-document reversal")
    comments: Optional[str] = Field(None, description="Optional alias for reason")

    def get_reason(self) -> str:
        return (self.reason or self.comments or "").strip()


class DocumentReversalResponse(BaseModel):
    document_type: str
    document_id: int
    document_number: str
    status: str
    reversed_by: str
    reversed_at: datetime
    reason: str
    reversal_posting_group_id: str
    original_ledger_entry_ids: List[int]
    reversal_ledger_entry_ids: List[int]
    reversal_entry_numbers: List[str]

    model_config = ConfigDict(from_attributes=True)
