"""
Issue-to-Heat Reconciliation API Endpoints.
Deterministic, explainable 3-pass reconciliation between Stores issues and furnace charges.
STRICT RULE: Reconciliation never creates stock movements or alters ledger balances.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import AuthenticatedUser, Permission, require_permission
from app.schemas.reconciliation import (
    ReconciliationRunRequest,
    ReconciliationRunRead,
    ReconciliationRunDetailRead,
    ReconciliationCandidateMatchRead,
    CandidateMatchAction,
    CandidateMatchReject,
    ReconciliationExceptionRead,
    ExceptionResolutionRequest,
)
from app.services.reconciliation_service import (
    run_reconciliation,
    get_reconciliation_run_detail,
    list_reconciliation_runs,
    confirm_candidate_match,
    reject_candidate_match,
    resolve_exception,
)

router = APIRouter()


@router.post("/run", response_model=ReconciliationRunDetailRead, status_code=status.HTTP_201_CREATED)
def api_run_reconciliation(
    payload: ReconciliationRunRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_RECONCILE)),
):
    """
    Executes a new versioned three-pass reconciliation run.
    Restricted to Foundry, Management, Admin.
    """
    run = run_reconciliation(
        db=db,
        created_by=user.user_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        notes=payload.notes,
    )
    return run


@router.get("/runs", response_model=List[ReconciliationRunRead])
def api_list_reconciliation_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """Lists reconciliation runs with summary statistics."""
    items, _ = list_reconciliation_runs(db=db, limit=limit, offset=offset)
    return items


@router.get("/runs/{id}", response_model=ReconciliationRunDetailRead)
def api_get_reconciliation_run_detail(
    id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_LOG_READ)),
):
    """Retrieves full reconciliation run details with results, candidates, and exceptions."""
    run = get_reconciliation_run_detail(db, id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run ID {id} not found",
        )
    return run


@router.post("/candidates/{id}/confirm", response_model=ReconciliationCandidateMatchRead)
def api_confirm_candidate_match(
    id: int,
    payload: CandidateMatchAction,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_RECONCILE)),
):
    """
    Explicit human confirmation of an advisory fuzzy match candidate.
    Restricted to Foundry, Management, Admin.
    """
    return confirm_candidate_match(
        db=db,
        candidate_id=id,
        reviewer_id=user.user_id,
        comments=payload.comments,
    )


@router.post("/candidates/{id}/reject", response_model=ReconciliationCandidateMatchRead)
def api_reject_candidate_match(
    id: int,
    payload: CandidateMatchReject,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_RECONCILE)),
):
    """
    Rejects an advisory candidate match. Comments mandatory.
    Restricted to Foundry, Management, Admin.
    """
    return reject_candidate_match(
        db=db,
        candidate_id=id,
        reviewer_id=user.user_id,
        comments=payload.comments,
    )


@router.post("/exceptions/{id}/resolve", response_model=ReconciliationExceptionRead)
def api_resolve_exception(
    id: int,
    payload: ExceptionResolutionRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.HEAT_EXCEPTION_RESOLVE)),
):
    """
    Resolves an open reconciliation exception.
    Restricted to Management and Admin roles.
    """
    return resolve_exception(
        db=db,
        exception_id=id,
        resolver_id=user.user_id,
        action=payload.action,
        comments=payload.comments,
    )
