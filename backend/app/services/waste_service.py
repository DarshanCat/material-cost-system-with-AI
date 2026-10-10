"""
Service for Waste Disposition transactions and approval states.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.waste import (
    WasteDispositionHeader,
    WasteDispositionLineItem,
    WasteAuditLog,
    WasteStatus,
    WasteType,
    DispositionType,
)
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.schemas.waste import WasteDispositionCreate
from app.services.decimal_validator import validate_and_flag_quantity


def generate_waste_number(db: Session, disposition_date: date) -> str:
    """Generates sequential document number: WST-YYYYMMDD-XXXX."""
    date_str = disposition_date.strftime("%Y%m%d")
    prefix = f"WST-{date_str}-"
    
    count_today = db.execute(
        select(func.count(WasteDispositionHeader.id)).where(WasteDispositionHeader.waste_number.like(f"{prefix}%"))
    ).scalar_one()
    
    return f"{prefix}{count_today + 1:04d}"


def create_waste_disposition(
    db: Session, data: WasteDispositionCreate, created_by: str
) -> Tuple[WasteDispositionHeader, List[str]]:
    warnings: List[str] = []

    # 1. Department validation
    source_dept = db.get(Department, data.source_department_id)
    if not source_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source Department ID {data.source_department_id} not found.",
        )

    # 2. Sequential Waste Number
    waste_num = generate_waste_number(db, data.disposition_date)

    header = WasteDispositionHeader(
        waste_number=waste_num,
        disposition_date=data.disposition_date,
        waste_type=data.waste_type.value,
        disposition_type=data.disposition_type.value,
        source_department_id=data.source_department_id,
        destination_notes=data.destination_notes,
        notes=data.notes,
        status=WasteStatus.DRAFT.value,
        created_by=created_by,
    )
    db.add(header)
    db.flush()

    # 3. Process line items
    for idx, line in enumerate(data.lines, start=1):
        item = db.get(MaterialItem, line.material_item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: Material Item ID {line.material_item_id} not found.",
            )
        uom = db.get(UOM, line.uom_id)
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {idx}: UOM ID {line.uom_id} not found.",
            )

        qty_result = validate_and_flag_quantity(line.quantity, uom, item.category, item.name)
        if not qty_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Line {idx}: {'; '.join(qty_result.errors)}",
            )
        for w in qty_result.warnings:
            warnings.append(f"Line {idx} ({item.item_code}): {w}")

        line_rec = WasteDispositionLineItem(
            waste_id=header.id,
            line_number=idx,
            material_item_id=line.material_item_id,
            uom_id=line.uom_id,
            quantity=line.quantity,
            reason=line.reason,
            remarks=line.remarks,
        )
        db.add(line_rec)

    # Initial audit
    audit = WasteAuditLog(
        waste_id=header.id,
        action="CREATED",
        from_status=None,
        to_status=WasteStatus.DRAFT.value,
        actor_id=created_by,
        comments="Waste disposition record created in draft status.",
    )
    db.add(audit)
    db.commit()
    db.refresh(header)
    return header, warnings


def submit_waste_disposition(db: Session, waste_id: int, actor_id: str, comments: Optional[str] = None) -> WasteDispositionHeader:
    waste = db.get(WasteDispositionHeader, waste_id)
    if not waste:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waste record not found.")
    if waste.status != WasteStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit waste record in status '{waste.status}'. Only DRAFT can be submitted.",
        )

    prev_status = waste.status
    waste.status = WasteStatus.SUBMITTED.value
    audit = WasteAuditLog(
        waste_id=waste.id,
        action="SUBMITTED",
        from_status=prev_status,
        to_status=waste.status,
        actor_id=actor_id,
        comments=comments or "Waste disposition submitted for supervisor review.",
    )
    db.add(audit)
    db.commit()
    db.refresh(waste)
    return waste


def approve_waste_disposition(db: Session, waste_id: int, actor_id: str, comments: Optional[str] = None) -> WasteDispositionHeader:
    waste = db.get(WasteDispositionHeader, waste_id)
    if not waste:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waste record not found.")
    if waste.status != WasteStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve waste record in status '{waste.status}'. Must be SUBMITTED first.",
        )

    prev_status = waste.status
    waste.status = WasteStatus.APPROVED.value
    audit = WasteAuditLog(
        waste_id=waste.id,
        action="APPROVED",
        from_status=prev_status,
        to_status=waste.status,
        actor_id=actor_id,
        comments=comments or "Waste disposition approved. (Note: Scrap / recovery ledger movements scheduled for Phase 4)",
    )
    db.add(audit)
    db.commit()
    db.refresh(waste)
    return waste
