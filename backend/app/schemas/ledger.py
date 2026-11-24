"""
Pydantic Schemas for Append-Only Stock Ledger & Stock Balances.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.ledger import MovementType, SourceDocumentType


class StockLedgerEntryResponse(BaseModel):
    id: int
    entry_number: str
    posting_group_id: str
    material_item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    uom_id: int
    uom_code: Optional[str] = None
    transaction_date: date
    posted_at: datetime
    movement_type: str
    quantity_delta: Decimal
    source_document_type: str
    source_document_id: int
    source_line_id: int
    source_document_number: str
    reference_number: Optional[str] = None
    reason: Optional[str] = None
    posted_by: str
    reversal_of_entry_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockBalanceResponse(BaseModel):
    material_item_id: int
    item_code: str
    item_name: str
    category: str
    department_name: Optional[str] = None
    base_uom_id: int
    uom_code: str
    current_balance: Decimal
    is_initialized: bool
    status: str  # "UNINITIALIZED", "OUT_OF_STOCK", "IN_STOCK", "NEGATIVE_STOCK"
    last_movement_date: Optional[date] = None
    movement_count: int

    model_config = ConfigDict(from_attributes=True)


class LedgerReversalRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for reversing the ledger entry")


class UOMStockSummaryResponse(BaseModel):
    uom_id: int
    uom_code: str
    uom_name: str
    decimal_precision: int
    total_quantity: Decimal
    item_count: int
    in_stock_items_count: int
    zero_stock_items_count: int
    negative_stock_items_count: int
    movement_count: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedLedgerEntriesResponse(BaseModel):
    items: List[StockLedgerEntryResponse]
    total: int
    page: int
    size: int
