"""
Pydantic schemas for Issue-to-Heat Reconciliation runs, results, candidate matches, and exceptions.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ReconciliationRunRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    notes: Optional[str] = None


class MaterialItemSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    name: str
    category: str
    subcategory: Optional[str] = None


class HeatSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    heat_number: str
    heat_date: date


class ReconciliationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    material_item_id: Optional[int] = None
    heat_id: Optional[int] = None
    match_method: str
    issued_quantity: Decimal
    charged_quantity: Decimal
    variance_quantity: Decimal
    variance_percentage: Optional[Decimal] = None
    applied_tolerance: Decimal
    tolerance_basis: str
    variance_class: str
    contributing_issue_ids: Optional[str] = None
    contributing_issue_line_ids: Optional[str] = None
    contributing_heat_ids: Optional[str] = None
    contributing_charge_line_ids: Optional[str] = None
    notes: Optional[str] = None
    status: str
    material_item: Optional[MaterialItemSummaryRead] = None
    heat: Optional[HeatSummaryRead] = None


class ReconciliationCandidateMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    issue_line_id: int
    heat_charge_line_id: int
    confidence_score: Decimal
    suggestion_reason: str
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comments: Optional[str] = None


class CandidateMatchAction(BaseModel):
    comments: Optional[str] = None


class CandidateMatchReject(BaseModel):
    comments: str = Field(..., min_length=1)


class ReconciliationExceptionAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exception_id: int
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_id: str
    comments: Optional[str] = None
    timestamp: datetime


class ReconciliationExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    exception_type: str
    source_reference: str
    description: str
    assigned_role: str
    priority: str
    status: str
    resolution_comments: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    audit_logs: List[ReconciliationExceptionAuditLogRead] = []


class ExceptionResolutionRequest(BaseModel):
    action: str = Field(..., pattern="^(RESOLVE|ACCEPT_LOSS)$")
    comments: str = Field(..., min_length=1)


class ReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_number: str
    algorithm_version: str
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: str
    total_evaluated_count: int
    exact_matches_count: int
    batch_matches_count: int
    fuzzy_candidates_count: int
    discrepancies_count: int
    segregated_consumables_count: int = 0
    segregated_consumables_quantity: Decimal = Decimal("0.0000")
    notes: Optional[str] = None
    created_by: str
    created_at: datetime


class ReconciliationRunDetailRead(ReconciliationRunRead):
    results: List[ReconciliationResultRead] = []
    candidate_matches: List[ReconciliationCandidateMatchRead] = []
    exceptions: List[ReconciliationExceptionRead] = []
