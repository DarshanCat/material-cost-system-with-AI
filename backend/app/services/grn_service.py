"""
Service for Goods Receipt Note (GRN) operations and lifecycle transitions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.services.maker_checker import enforce_maker_checker, GRN
from app.services.posting_guard import ledger_write_guard
from app.models.grn import GRNHeader, GRNLineItem, GRNAuditLog, GRNStatus, GRNSourceType
from app.models.vendor import Vendor
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.grn import GRNCreate, GRNUpdate
from app.services.decimal_validator import validate_and_flag_quantity, validate_rate_and_gst
from app.services.duplicate_detector import check_grn_invoice_duplicate
from app.services.document_number_service import (
    DocumentType,
    generate_document_number,
    execute_with_document_number_retry,
)


def generate_grn_number(db: Session, receipt_date: date) -> str:
    """Generates sequential document number: GRN-YYYYMMDD-XXXX."""
    return generate_document_number(db, DocumentType.GRN, receipt_date)


def create_grn(db: Session, data: GRNCreate, created_by: str) -> Tuple[GRNHeader, List[str]]:
    warnings: List[str] = []

    # 1. Vendor validation
    if data.source_type == GRNSourceType.EXTERNAL_VENDOR:
        if not data.vendor_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vendor selection is mandatory for external vendor receipts.",
            )
        vendor = db.get(Vendor, data.vendor_id)
        if not vendor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with ID {data.vendor_id} does not exist.",
            )
        
        # Duplicate invoice warning check
        if data.vendor_invoice_no:
            dup_check = check_grn_invoice_duplicate(
                db, data.vendor_id, data.vendor_invoice_no, data.invoice_date
            )
            if dup_check.has_conflict:
                warnings.append(dup_check.message)

    # 2. Pre-validate line items before entering transaction retry block
    validated_lines = []
    for idx, line in enumerate(data.lines, start=1):
        item = db.get(MaterialItem, line.material_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: Material Item with ID {line.material_item_id} does not exist.",
            )
        uom = db.get(UOM, line.uom_id)
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: UOM with ID {line.uom_id} does not exist.",
            )

        # Quantity precision & suspect heuristics
        qty_result = validate_and_flag_quantity(line.quantity, uom, item.category, item.name)
        if not qty_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Line {idx}: {'; '.join(qty_result.errors)}",
            )
        for w in qty_result.warnings:
            warnings.append(f"Line {idx} ({item.item_code}): {w}")

        # Rate and GST validation
        rate_result = validate_rate_and_gst(
            data.source_type.value, item.category, line.rate_ex_gst, line.gst_percent
        )
        if not rate_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Line {idx}: {'; '.join(rate_result.errors)}",
            )
        for w in rate_result.warnings:
            warnings.append(f"Line {idx} ({item.item_code}): {w}")

        validated_lines.append(line)

    # 3. Create document using bounded savepoint retry for collision safety
    def _create(grn_num: str) -> GRNHeader:
        header = GRNHeader(
            grn_number=grn_num,
            receipt_date=data.receipt_date,
            source_type=data.source_type.value,
            vendor_id=data.vendor_id,
            vendor_invoice_no=data.vendor_invoice_no.strip() if data.vendor_invoice_no else None,
            invoice_date=data.invoice_date,
            reference_document=data.reference_document,
            notes=data.notes,
            status=GRNStatus.DRAFT.value,
            created_by=created_by,
        )
        db.add(header)
        db.flush()

        for idx, line in enumerate(validated_lines, start=1):
            line_record = GRNLineItem(
                grn_id=header.id,
                line_number=idx,
                material_item_id=line.material_item_id,
                uom_id=line.uom_id,
                quantity=line.quantity,
                rate_ex_gst=line.rate_ex_gst,
                gst_percent=line.gst_percent,
                remarks=line.remarks,
            )
            db.add(line_record)

        audit = GRNAuditLog(
            grn_id=header.id,
            action="CREATED",
            from_status=None,
            to_status=GRNStatus.DRAFT.value,
            actor_id=created_by,
            comments="GRN created in draft status.",
        )
        db.add(audit)
        return header

    header = execute_with_document_number_retry(
        db=db,
        doc_type=DocumentType.GRN,
        create_fn=_create,
        target_date=data.receipt_date,
    )
    db.commit()
    db.refresh(header)
    return header, warnings


def submit_grn(db: Session, grn_id: int, actor_id: str, comments: Optional[str] = None) -> GRNHeader:
    grn = db.get(GRNHeader, grn_id)
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")
    if grn.status != GRNStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit GRN in status '{grn.status}'. Only DRAFT can be submitted.",
        )
    if not grn.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot submit GRN without line items.",
        )

    prev_status = grn.status
    grn.status = GRNStatus.SUBMITTED.value
    audit = GRNAuditLog(
        grn_id=grn.id,
        action="SUBMITTED",
        from_status=prev_status,
        to_status=grn.status,
        actor_id=actor_id,
        comments=comments or "GRN submitted for verification.",
    )
    db.add(audit)
    db.commit()
    db.refresh(grn)
    return grn


def approve_grn(db: Session, grn_id: int, actor_id: str, comments: Optional[str] = None) -> GRNHeader:
    with ledger_write_guard(db):
        return _approve_grn(db, grn_id, actor_id, comments)


def _approve_grn(db: Session, grn_id: int, actor_id: str, comments: Optional[str] = None) -> GRNHeader:
    grn = db.get(GRNHeader, grn_id, with_for_update=True)
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")
    enforce_maker_checker(GRN, grn.created_by, actor_id, f"GRN {grn.grn_number}")
    if grn.status != GRNStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve GRN in status '{grn.status}'. Must be SUBMITTED first.",
        )

    prev_status = grn.status
    grn.status = GRNStatus.APPROVED.value
    audit = GRNAuditLog(
        grn_id=grn.id,
        action="APPROVED",
        from_status=prev_status,
        to_status=grn.status,
        actor_id=actor_id,
        comments=comments or "GRN verified and approved. Posted inward entries to stock ledger.",
    )
    db.add(audit)
    db.flush()

    # Atomically post to append-only stock ledger
    from app.services.ledger_service import post_grn_to_ledger
    post_grn_to_ledger(db, grn, actor_id)

    db.commit()
    db.refresh(grn)
    return grn


def cancel_grn(db: Session, grn_id: int, actor_id: str, comments: Optional[str] = None) -> GRNHeader:
    grn = db.get(GRNHeader, grn_id)
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")
    if grn.status == GRNStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved GRNs cannot be cancelled directly. Requires reversal authorization.",
        )

    prev_status = grn.status
    grn.status = GRNStatus.CANCELLED.value
    audit = GRNAuditLog(
        grn_id=grn.id,
        action="CANCELLED",
        from_status=prev_status,
        to_status=grn.status,
        actor_id=actor_id,
        comments=comments or "GRN cancelled.",
    )
    db.add(audit)
    db.commit()
    db.refresh(grn)
    return grn
