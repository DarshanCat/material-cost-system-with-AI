"""
Service for Goods Receipt Note (GRN) operations and lifecycle transitions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.grn import GRNHeader, GRNLineItem, GRNAuditLog, GRNStatus, GRNSourceType
from app.models.vendor import Vendor
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.grn import GRNCreate, GRNUpdate
from app.services.decimal_validator import validate_and_flag_quantity, validate_rate_and_gst
from app.services.duplicate_detector import check_grn_invoice_duplicate


def generate_grn_number(db: Session, receipt_date: date) -> str:
    """Generates sequential document number: GRN-YYYYMMDD-XXXX."""
    date_str = receipt_date.strftime("%Y%m%d")
    prefix = f"GRN-{date_str}-"
    
    count_today = db.execute(
        select(func.count(GRNHeader.id)).where(GRNHeader.grn_number.like(f"{prefix}%"))
    ).scalar_one()
    
    return f"{prefix}{count_today + 1:04d}"


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

    # 2. Generate document number
    grn_number = generate_grn_number(db, data.receipt_date)

    header = GRNHeader(
        grn_number=grn_number,
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

    # 3. Process line items with strict decimal validation
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

    # Initial audit log
    audit = GRNAuditLog(
        grn_id=header.id,
        action="CREATED",
        from_status=None,
        to_status=GRNStatus.DRAFT.value,
        actor_id=created_by,
        comments="GRN created in draft status.",
    )
    db.add(audit)
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
    grn = db.get(GRNHeader, grn_id)
    if not grn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRN not found.")
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
        comments=comments or "GRN verified and approved. (Note: Ledger integration scheduled for Phase 4)",
    )
    db.add(audit)
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
