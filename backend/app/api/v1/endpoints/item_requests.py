from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models.item_request import ItemRequest, RequestStatus
from app.schemas.item_request import (
    ItemRequestCreate,
    ItemRequestUpdate,
    ItemRequestDecision,
    ItemRequestRead,
    ItemRequestAuditLogRead,
    PaginatedRequestsResponse,
)
from app.services.item_request_service import ItemRequestService
from app.core.security import require_permission, Permission, DevUserContext

router = APIRouter()


def _serialize_request(req: ItemRequest) -> ItemRequestRead:
    req_read = ItemRequestRead.model_validate(req)
    if req.proposed_department:
        req_read.department_name = req.proposed_department.name
    if req.proposed_uom:
        req_read.uom_code = req.proposed_uom.code
    if req.linked_item:
        req_read.linked_item_code = req.linked_item.item_code
    req_read.audit_logs = [ItemRequestAuditLogRead.model_validate(log) for log in req.audit_logs]
    return req_read


@router.post("", response_model=ItemRequestRead, status_code=status.HTTP_201_CREATED, summary="Create Draft Item Request")
def create_item_request(
    payload: ItemRequestCreate,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_REQUEST_CREATE)),
):
    """Initiates a new item request in DRAFT status."""
    try:
        service = ItemRequestService(db)
        req = service.create_draft(
            requested_name=payload.requested_name,
            proposed_department_id=payload.proposed_department_id,
            proposed_category=payload.proposed_category,
            proposed_subcategory=payload.proposed_subcategory,
            proposed_uom_id=payload.proposed_uom_id,
            justification=payload.justification,
            actor=user,
        )
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while creating request: {str(exc.__class__.__name__)}"
        )


@router.get("", response_model=PaginatedRequestsResponse, summary="List Item Requests")
def list_item_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (DRAFT, SUBMITTED, APPROVED, REJECTED, CANCELLED)"),
    requester_id: Optional[str] = Query(None, description="Filter by requester user ID"),
    q: Optional[str] = Query(None, description="Search query across item name or request number"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(25, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_REQUEST_READ)),
):
    """Lists item requests with optional filtering and pagination."""
    try:
        stmt = select(ItemRequest)

        if status_filter:
            stmt = stmt.where(ItemRequest.status == status_filter.upper())

        if requester_id:
            stmt = stmt.where(ItemRequest.requester_id == requester_id)

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(ItemRequest.request_number).like(term)) |
                (func.lower(ItemRequest.requested_name).like(term))
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Paginate
        offset = (page - 1) * size
        requests = db.scalars(
            stmt.order_by(ItemRequest.created_at.desc()).offset(offset).limit(size)
        ).all()

        return PaginatedRequestsResponse(
            items=[_serialize_request(r) for r in requests],
            total=total,
            page=page,
            size=size,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while querying requests: {str(exc.__class__.__name__)}"
        )


@router.get("/pending", response_model=PaginatedRequestsResponse, summary="Pending Approvals Queue")
def list_pending_requests(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_APPROVE)),
):
    """
    Dedicated pending queue for Management and Admin reviewers.
    Displays SUBMITTED requests awaiting decision.
    """
    try:
        stmt = select(ItemRequest).where(ItemRequest.status == RequestStatus.SUBMITTED.value)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        offset = (page - 1) * size
        requests = db.scalars(
            stmt.order_by(ItemRequest.submitted_at.asc()).offset(offset).limit(size)
        ).all()

        return PaginatedRequestsResponse(
            items=[_serialize_request(r) for r in requests],
            total=total,
            page=page,
            size=size,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while querying pending requests: {str(exc.__class__.__name__)}"
        )


@router.get("/{request_id}", response_model=ItemRequestRead, summary="Get Request Detail with Audit Trail")
def get_item_request(
    request_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.ITEM_REQUEST_READ)),
):
    """Retrieves single request details along with full immutable audit history."""
    try:
        req = db.get(ItemRequest, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Item request not found.")
        return _serialize_request(req)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while retrieving request: {str(exc.__class__.__name__)}"
        )


@router.put("/{request_id}", response_model=ItemRequestRead, summary="Update Draft Item Request")
def update_item_request(
    request_id: int,
    payload: ItemRequestUpdate,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_REQUEST_CREATE)),
):
    """Updates draft details before submission."""
    try:
        service = ItemRequestService(db)
        req = service.update_draft(
            request_id=request_id,
            requested_name=payload.requested_name,
            proposed_department_id=payload.proposed_department_id,
            proposed_category=payload.proposed_category,
            proposed_subcategory=payload.proposed_subcategory,
            proposed_uom_id=payload.proposed_uom_id,
            justification=payload.justification,
            actor=user,
        )
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while updating draft: {str(exc.__class__.__name__)}"
        )


@router.post("/{request_id}/submit", response_model=ItemRequestRead, summary="Submit Request for Review")
def submit_item_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_REQUEST_SUBMIT)),
):
    """Submits a draft request for management review."""
    try:
        service = ItemRequestService(db)
        req = service.submit_request(request_id=request_id, actor=user)
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while submitting request: {str(exc.__class__.__name__)}"
        )


@router.post("/{request_id}/cancel", response_model=ItemRequestRead, summary="Cancel Request")
def cancel_item_request(
    request_id: int,
    payload: Optional[ItemRequestDecision] = None,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_REQUEST_CANCEL)),
):
    """Cancels a draft or submitted request."""
    try:
        service = ItemRequestService(db)
        comments = payload.comments if payload else None
        req = service.cancel_request(request_id=request_id, actor=user, comments=comments)
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while cancelling request: {str(exc.__class__.__name__)}"
        )


@router.post("/{request_id}/approve", response_model=ItemRequestRead, summary="Approve Request & Create Item")
def approve_item_request(
    request_id: int,
    payload: Optional[ItemRequestDecision] = None,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_APPROVE)),
):
    """
    Approves request and creates new MaterialItem in an atomic transaction.
    Enforces separation of duties (no self-approval).
    """
    try:
        service = ItemRequestService(db)
        comments = payload.comments if payload else None
        req = service.approve_request(request_id=request_id, actor=user, comments=comments)
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while approving request: {str(exc.__class__.__name__)}"
        )


@router.post("/{request_id}/reject", response_model=ItemRequestRead, summary="Reject Request")
def reject_item_request(
    request_id: int,
    payload: ItemRequestDecision,
    db: Session = Depends(get_db),
    user: DevUserContext = Depends(require_permission(Permission.ITEM_REJECT)),
):
    """
    Rejects request with mandatory explanation reason.
    Enforces separation of duties (no self-rejection).
    """
    if not payload or not payload.comments:
        raise HTTPException(status_code=400, detail="Rejection requires an explicit explanation in decision comments.")

    try:
        service = ItemRequestService(db)
        req = service.reject_request(request_id=request_id, actor=user, comments=payload.comments)
        return _serialize_request(req)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error while rejecting request: {str(exc.__class__.__name__)}"
        )
