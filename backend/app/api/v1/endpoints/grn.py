"""
Goods Receipt Note (GRN) API Endpoints.
"""

from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, desc

from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import get_db
from app.schemas.grn import (
    GRNCreate,
    GRNResponse,
    GRNLineItemResponse,
    GRNAuditLogResponse,
    GRNStatusAction,
    GRNPaymentAction,
    GRNQualityAction,
)
from app.core.config import settings
from app.models.grn import GRNAttachment, GRNAuditLog, GRNHeader, GRNLineItem, GRNStatus
from app.services.attachment_store import (
    AttachmentRejected,
    AttachmentStore,
    check_upload,
    get_attachment_store,
    new_storage_key,
)
from app.schemas.reversal import DocumentReversalRequest, DocumentReversalResponse
from app.services.grn_service import (
    approve_grn,
    cancel_grn,
    create_grn,
    grn_payable_total,
    record_payment,
    record_quality_inspection,
    reject_grn,
    reverse_grn,
    submit_grn,
)

router = APIRouter()


def _serialize_grn(header: GRNHeader, warnings: Optional[List[str]] = None) -> GRNResponse:
    lines = []
    for l in header.lines:
        lines.append(
            GRNLineItemResponse(
                id=l.id,
                grn_id=l.grn_id,
                line_number=l.line_number,
                material_item_id=l.material_item_id,
                uom_id=l.uom_id,
                quantity=l.quantity,
                rate_ex_gst=l.rate_ex_gst,
                gst_percent=l.gst_percent,
                remarks=l.remarks,
                item_code=l.material_item.item_code if l.material_item else None,
                item_name=l.material_item.name if l.material_item else None,
                uom_code=l.uom.code if l.uom else None,
            )
        )
    audits = [
        GRNAuditLogResponse(
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

    return GRNResponse(
        id=header.id,
        grn_number=header.grn_number,
        receipt_date=header.receipt_date,
        source_type=header.source_type,
        vendor_id=header.vendor_id,
        vendor_name=header.vendor.name if header.vendor else None,
        vendor_invoice_no=header.vendor_invoice_no,
        invoice_date=header.invoice_date,
        reference_document=header.reference_document,
        notes=header.notes,
        status=header.status,
        created_by=header.created_by,
        created_at=header.created_at,
        updated_at=header.updated_at,
        lines=lines,
        audit_logs=audits,
        validation_warnings=warnings or [],
        quality_document_number=header.quality_document_number,
        quality_inspection_status=header.quality_inspection_status,
        quality_inspection_notes=header.quality_inspection_notes,
        quality_inspected_by=header.quality_inspected_by,
        quality_inspected_at=header.quality_inspected_at,
        payment_status=header.payment_status or ("UNPAID" if header.status == "APPROVED" else None),
        amount_paid=header.amount_paid,
        payment_reference=header.payment_reference,
        payment_date=header.payment_date,
        payment_mode=header.payment_mode,
        payment_notes=header.payment_notes,
        paid_by=header.paid_by,
        payable_total=grn_payable_total(header) if header.status == "APPROVED" else None,
    )


@router.post("/", response_model=GRNResponse, status_code=status.HTTP_201_CREATED)
def create_new_grn(
    payload: GRNCreate,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    header, warnings = create_grn(db, payload, user.user_id)
    return _serialize_grn(header, warnings)


@router.get("/", response_model=List[GRNResponse])
def list_grns(
    status: Optional[str] = Query(None, description="Filter by GRN status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    from_date: Optional[date] = Query(None, description="Filter receipt date from"),
    to_date: Optional[date] = Query(None, description="Filter receipt date to"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    query = (
        select(GRNHeader)
        .options(
            joinedload(GRNHeader.vendor),
            selectinload(GRNHeader.lines).joinedload(GRNLineItem.material_item),
            selectinload(GRNHeader.lines).joinedload(GRNLineItem.uom),
            selectinload(GRNHeader.audit_logs),
        )
        .order_by(desc(GRNHeader.created_at))
    )
    if status:
        query = query.where(GRNHeader.status == status.upper())
    if source_type:
        query = query.where(GRNHeader.source_type == source_type.upper())
    if from_date:
        query = query.where(GRNHeader.receipt_date >= from_date)
    if to_date:
        query = query.where(GRNHeader.receipt_date <= to_date)

    query = query.offset(skip).limit(limit)
    headers = db.execute(query).scalars().unique().all()
    return [_serialize_grn(h) for h in headers]


@router.get("/{grn_id}", response_model=GRNResponse)
def get_grn_by_id(
    grn_id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    query = (
        select(GRNHeader)
        .options(
            joinedload(GRNHeader.vendor),
            selectinload(GRNHeader.lines).joinedload(GRNLineItem.material_item),
            selectinload(GRNHeader.lines).joinedload(GRNLineItem.uom),
            selectinload(GRNHeader.audit_logs),
        )
        .where(GRNHeader.id == grn_id)
    )
    grn = db.execute(query).scalars().unique().first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    return _serialize_grn(grn)


@router.post("/{grn_id}/submit", response_model=GRNResponse)
def submit_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    grn = submit_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)


@router.post("/{grn_id}/approve", response_model=GRNResponse)
def approve_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    grn = approve_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)


@router.post("/{grn_id}/cancel", response_model=GRNResponse)
def cancel_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
    db: Session = Depends(get_db),
):
    grn = cancel_grn(db, grn_id, user.user_id, action.comments)
    return _serialize_grn(grn)


@router.post("/{grn_id}/reverse", response_model=DocumentReversalResponse)
def reverse_grn_action(
    grn_id: int,
    payload: DocumentReversalRequest,
    user: AuthenticatedUser = Depends(require_permission(Permission.LEDGER_REVERSE)),
    db: Session = Depends(get_db),
):
    return reverse_grn(db, grn_id, user.user_id, payload.get_reason())


@router.post("/{grn_id}/reject", response_model=GRNResponse)
def reject_grn_action(
    grn_id: int,
    action: GRNStatusAction,
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_APPROVE)),
    db: Session = Depends(get_db),
):
    return _serialize_grn(reject_grn(db, grn_id, user.user_id, action.comments))


@router.post("/{grn_id}/quality", response_model=GRNResponse)
def record_grn_quality(
    grn_id: int,
    payload: GRNQualityAction,
    # Quality role only: even Admin cannot sign off quality.
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_QUALITY, admin_bypass=False)),
    db: Session = Depends(get_db),
):
    grn = record_quality_inspection(
        db, grn_id, user.user_id, payload.quality_inspection_status,
        payload.quality_document_number, payload.quality_inspection_notes,
    )
    return _serialize_grn(grn)


@router.post("/{grn_id}/payment", response_model=GRNResponse)
def record_grn_payment(
    grn_id: int,
    payload: GRNPaymentAction,
    # Accounts role only: even Admin cannot record payments.
    user: AuthenticatedUser = Depends(require_permission(Permission.PAYMENT_RECORD, admin_bypass=False)),
    db: Session = Depends(get_db),
):
    grn = record_payment(
        db, grn_id, user.user_id, payload.amount_paid, payload.payment_reference,
        payload.payment_date or date.today(), payload.payment_mode, payload.payment_notes,
    )
    return _serialize_grn(grn)


# ----------------------------------------------------------------------------------------------
# Supporting documents (vendor invoice, delivery challan, test certificate, photos)
# ----------------------------------------------------------------------------------------------

class AttachmentOut(BaseModel):
    id: int
    grn_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    description: Optional[str]
    uploaded_by: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


def _grn_or_404(db: Session, grn_id: int) -> GRNHeader:
    grn = db.get(GRNHeader, grn_id)
    if grn is None:
        raise HTTPException(status_code=404, detail="GRN not found")
    return grn


def _attachment_or_404(db: Session, grn_id: int, attachment_id: int) -> GRNAttachment:
    row = db.get(GRNAttachment, attachment_id)
    if row is None or row.grn_id != grn_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return row


def _audit(db: Session, grn: GRNHeader, action: str, actor: str, comment: str) -> None:
    db.add(GRNAuditLog(grn_id=grn.id, action=action, from_status=grn.status, to_status=grn.status, actor_id=actor, comments=comment[:500]))


@router.get("/{grn_id}/attachments", response_model=List[AttachmentOut])
def list_grn_attachments(
    grn_id: int,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    _grn_or_404(db, grn_id)
    rows = db.execute(select(GRNAttachment).where(GRNAttachment.grn_id == grn_id).order_by(GRNAttachment.id)).scalars().all()
    return [AttachmentOut.model_validate(r) for r in rows]


@router.post("/{grn_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
def upload_grn_attachment(
    grn_id: int,
    file: UploadFile = File(...),
    description: Optional[str] = Form(default=None, max_length=300),
    db: Session = Depends(get_db),
    store: AttachmentStore = Depends(get_attachment_store),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
):
    grn = _grn_or_404(db, grn_id)
    if grn.status not in (GRNStatus.DRAFT.value, GRNStatus.SUBMITTED.value):
        raise HTTPException(status_code=409, detail="Documents can only be added while the GRN is Draft or Submitted.")
    existing = db.execute(select(GRNAttachment.id).where(GRNAttachment.grn_id == grn_id)).all()
    if len(existing) >= settings.ATTACHMENT_MAX_PER_DOCUMENT:
        raise HTTPException(status_code=409, detail=f"A GRN can have at most {settings.ATTACHMENT_MAX_PER_DOCUMENT} documents.")
    limit = settings.ATTACHMENT_MAX_MB * 1024 * 1024
    data = file.file.read(limit + 1)  # never read more than the limit into memory
    try:
        checked = check_upload(file.filename, data)
    except AttachmentRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    key = new_storage_key(f"grn/{grn_id}", checked.display_name)
    store.save(key, data, checked.content_type)
    row = GRNAttachment(
        grn_id=grn_id, original_filename=checked.display_name, content_type=checked.content_type, size_bytes=checked.size_bytes,
        sha256=checked.sha256, storage_key=key, description=(description or "").strip() or None, uploaded_by=user.user_id,
    )
    db.add(row)
    _audit(db, grn, "ATTACHMENT_ADDED", user.user_id, f"{checked.display_name} ({checked.size_bytes} bytes, sha256 {checked.sha256[:12]})")
    try:
        db.commit()
    except Exception:
        db.rollback()
        store.delete(key)  # do not leave an orphan file behind a failed record
        raise HTTPException(status_code=500, detail="Could not save the document.")
    db.refresh(row)
    return AttachmentOut.model_validate(row)


@router.get("/{grn_id}/attachments/{attachment_id}/download")
def download_grn_attachment(
    grn_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    store: AttachmentStore = Depends(get_attachment_store),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_READ)),
):
    _grn_or_404(db, grn_id)
    row = _attachment_or_404(db, grn_id, attachment_id)
    try:
        data = store.read(row.storage_key)
    except Exception:
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    safe_name = row.original_filename.replace('"', "'")
    return Response(
        content=data,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{grn_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grn_attachment(
    grn_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    store: AttachmentStore = Depends(get_attachment_store),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECEIPT_CREATE)),
):
    grn = _grn_or_404(db, grn_id)
    row = _attachment_or_404(db, grn_id, attachment_id)
    if grn.status != GRNStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Documents can only be removed while the GRN is Draft.")
    key, name = row.storage_key, row.original_filename
    db.delete(row)
    _audit(db, grn, "ATTACHMENT_REMOVED", user.user_id, name)
    db.commit()
    store.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
