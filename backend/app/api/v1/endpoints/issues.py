"""
Material Issue API Endpoints.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission, UserRole
from app.db.session import get_db
from app.schemas.issue import (
    MaterialIssueCreate,
    MaterialIssueResponse,
    MaterialIssueLineItemResponse,
    IssueAuditLogResponse,
    IssueStatusAction,
)
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem
from app.services.issue_service import (
    create_material_issue,
    submit_material_issue,
    approve_material_issue,
    direct_issue_slip,
    cancel_material_issue,
    reverse_material_issue,
)

from app.schemas.reversal import DocumentReversalRequest, DocumentReversalResponse

router = APIRouter()


def _serialize_issue(header: MaterialIssueHeader, warnings: Optional[List[str]] = None) -> MaterialIssueResponse:
    lines = []
    for l in header.lines:
        lines.append(
            MaterialIssueLineItemResponse(
                id=l.id,
                issue_id=l.issue_id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                uom_id=l.uom_id,
                quantity=l.quantity,
                remarks=l.remarks,
                item_code=l.material_item.item_code if l.material_item else None,
                item_name=l.material_item.name if l.material_item else None,
                uom_code=l.uom.code if l.uom else None,
            )
        )
    audits = [
        IssueAuditLogResponse(
            id=a.id,
            action=a.action,
            from_status=a.from_status,
            to_status=a.to_status,
            actor_id=a.actor_id,
            comments=a.comments,
            timestamp=a.timestamp,
        )
        for a in header.audit_logs
    ]

    return MaterialIssueResponse(
        id=header.id,
        issue_slip_number=header.issue_slip_number,
        issue_date=header.issue_date,
        issuing_department_id=header.issuing_department_id,
        issuing_department_name=header.issuing_department.name if header.issuing_department else None,
        receiving_department_id=header.receiving_department_id,
        receiving_department_name=header.receiving_department.name if header.receiving_department else None,
        heat_reference_number=header.heat_reference_number,
        notes=header.notes,
        status=header.status,
        created_by=header.created_by,
        created_at=header.created_at,
        updated_at=header.updated_at,
        lines=lines,
        audit_logs=audits,
        validation_warnings=warnings or [],
    )


@router.post("/", response_model=MaterialIssueResponse, status_code=status.HTTP_201_CREATED)
def create_new_issue(
    payload: MaterialIssueCreate,
    direct_issue: bool = Query(False, description="When true, directly issues materials and posts to stock ledger"),
    user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_CREATE)),
    db: Session = Depends(get_db),
):
    header, warnings = create_material_issue(db, payload, user.user_id, direct_issue=direct_issue)
    return _serialize_issue(header, warnings)


@router.post("/{issue_id}/direct-issue", response_model=MaterialIssueResponse)
def direct_issue_action(
    issue_id: int,
    action: Optional[IssueStatusAction] = None,
    user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_CREATE)),
    db: Session = Depends(get_db),
):
    comments = action.comments if action else None
    issue = direct_issue_slip(db, issue_id, user.user_id, comments)
    return _serialize_issue(issue)


@router.get("/", response_model=List[MaterialIssueResponse])
def list_issues(
    status: Optional[str] = Query(None, description="Filter by status"),
    heat_reference_number: Optional[str] = Query(None, description="Filter by heat number"),
    department_id: Optional[int] = Query(None, description="Filter by receiving department"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_READ)),
):
    query = (
        select(MaterialIssueHeader)
        .options(
            joinedload(MaterialIssueHeader.issuing_department),
            joinedload(MaterialIssueHeader.receiving_department),
            selectinload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.material_item),
            selectinload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.uom),
            selectinload(MaterialIssueHeader.audit_logs),
        )
        .order_by(desc(MaterialIssueHeader.created_at))
    )
    if status:
        query = query.where(MaterialIssueHeader.status == status.upper())
    if heat_reference_number:
        query = query.where(MaterialIssueHeader.heat_reference_number.ilike(f"%{heat_reference_number}%"))
    if department_id:
        query = query.where(MaterialIssueHeader.receiving_department_id == department_id)
    if from_date:
        query = query.where(MaterialIssueHeader.issue_date >= from_date)
    if to_date:
        query = query.where(MaterialIssueHeader.issue_date <= to_date)

    query = query.offset(skip).limit(limit)
    headers = db.execute(query).scalars().unique().all()
    return [_serialize_issue(h) for h in headers]


@router.get("/{issue_id}", response_model=MaterialIssueResponse)
def get_issue_by_id(
    issue_id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_READ)),
):
    query = (
        select(MaterialIssueHeader)
        .options(
            joinedload(MaterialIssueHeader.issuing_department),
            joinedload(MaterialIssueHeader.receiving_department),
            selectinload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.material_item),
            selectinload(MaterialIssueHeader.lines).joinedload(MaterialIssueLineItem.uom),
            selectinload(MaterialIssueHeader.audit_logs),
        )
        .where(MaterialIssueHeader.id == issue_id)
    )
    issue = db.execute(query).scalars().unique().first()
    if not issue:
        raise HTTPException(status_code=404, detail="Material issue slip not found")
    return _serialize_issue(issue)


@router.post("/{issue_id}/submit", response_model=MaterialIssueResponse)
def submit_issue_action(
    issue_id: int,
    action: IssueStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_CREATE)),
    db: Session = Depends(get_db),
):
    issue = submit_material_issue(db, issue_id, user.user_id, action.comments)
    return _serialize_issue(issue)


@router.post("/{issue_id}/approve", response_model=MaterialIssueResponse)
def approve_issue_action(
    issue_id: int,
    action: IssueStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_APPROVE)),
    db: Session = Depends(get_db),
):
    issue = approve_material_issue(db, issue_id, user.user_id, action.comments)
    return _serialize_issue(issue)


@router.post("/{issue_id}/cancel", response_model=MaterialIssueResponse)
def cancel_issue_action(
    issue_id: int,
    action: IssueStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.ISSUE_CREATE)),
    db: Session = Depends(get_db),
):
    issue = cancel_material_issue(db, issue_id, user.user_id, action.comments)
    return _serialize_issue(issue)


@router.post("/{issue_id}/reverse", response_model=DocumentReversalResponse)
def reverse_issue_action(
    issue_id: int,
    payload: DocumentReversalRequest,
    user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_REVERSE)),
    db: Session = Depends(get_db),
):
    return reverse_material_issue(db, issue_id, user.user_id, payload.get_reason())
