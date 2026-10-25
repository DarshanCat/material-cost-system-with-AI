"""
Induction Furnace Heat Log Master Service.
Manages Heat Headers, Furnace Charge Details, and Parts Produced.
STRICT INVENTORY RULE: Heat Log charge records NEVER create stock movements.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    ProductionStatus,
    HeatChargeValidationStatus,
    CastingClassification,
)
from app.models.item import MaterialItem
from app.models.uom import UOM
from app.services.validators import normalize_heat_number
from app.services.material_alias_service import resolve_material_by_description


def create_heat(
    db: Session,
    heat_number: str,
    heat_date: date,
    created_by: str,
    furnace_id: Optional[str] = None,
    shift: Optional[str] = None,
    metal_tapped_weight: Optional[Decimal] = None,
    metal_tapped_uom_id: Optional[int] = None,
    production_status: str = ProductionStatus.COMPLETED.value,
    source_document_reference: Optional[str] = None,
    notes: Optional[str] = None,
    charge_lines_data: Optional[List[Dict[str, Any]]] = None,
    parts_produced_data: Optional[List[Dict[str, Any]]] = None,
) -> HeatHeader:
    """
    Creates a new induction furnace heat log record.
    Preserves original heat number and computes normalized reference (e.g. H-102603-3721).
    Validates charge line materials against alias master.
    """
    if not heat_number or not heat_number.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Heat number cannot be empty",
        )
    
    raw_heat = heat_number.strip()
    try:
        norm_heat = normalize_heat_number(raw_heat)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    
    # Check for existing heat with either raw or normalized number
    existing = db.execute(
        select(HeatHeader).where(
            (HeatHeader.heat_number == raw_heat) | 
            (HeatHeader.normalized_heat_number == norm_heat)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Heat '{raw_heat}' (normalized '{norm_heat}') already exists with ID {existing.id}",
        )
    
    # Metal tapped UOM check if weight provided
    if metal_tapped_weight is not None and metal_tapped_uom_id is not None:
        uom = db.execute(select(UOM).where(UOM.id == metal_tapped_uom_id)).scalar_one_or_none()
        if not uom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metal tapped UOM ID {metal_tapped_uom_id} not found",
            )
    
    heat = HeatHeader(
        heat_number=raw_heat,
        original_heat_number=raw_heat,
        normalized_heat_number=norm_heat,
        heat_date=heat_date,
        furnace_id=furnace_id.strip() if furnace_id else None,
        shift=shift.strip() if shift else None,
        metal_tapped_weight=metal_tapped_weight,
        metal_tapped_uom_id=metal_tapped_uom_id,
        production_status=production_status,
        source_document_reference=source_document_reference,
        notes=notes,
        created_by=created_by,
    )
    db.add(heat)
    db.flush()
    
    # Process charge lines
    if charge_lines_data:
        for idx, line_data in enumerate(charge_lines_data, start=1):
            raw_desc = line_data.get("original_material_description", "").strip()
            if not raw_desc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Charge line {idx} missing material description",
                )
            
            qty = Decimal(str(line_data.get("charged_quantity", "0")))
            if qty <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Charge line {idx} quantity must be strictly positive",
                )
            
            uom_id = line_data.get("uom_id")
            if not uom_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Charge line {idx} requires a valid UOM ID",
                )
            
            # Resolve material item via alias master or direct code/name
            resolved_item = None
            explicit_item_id = line_data.get("material_item_id")
            if explicit_item_id:
                resolved_item = db.execute(
                    select(MaterialItem).where(MaterialItem.id == explicit_item_id)
                ).scalar_one_or_none()
            if not resolved_item:
                resolved_item = resolve_material_by_description(db, raw_desc)
            
            val_status = (
                HeatChargeValidationStatus.VALID.value
                if resolved_item
                else HeatChargeValidationStatus.UNMAPPED_ALIAS.value
            )
            
            charge_line = HeatChargeLine(
                heat_id=heat.id,
                line_number=idx,
                material_item_id=resolved_item.id if resolved_item else None,
                original_material_description=raw_desc,
                charged_quantity=qty,
                uom_id=uom_id,
                source_row_reference=line_data.get("source_row_reference"),
                validation_status=val_status,
                remarks=line_data.get("remarks"),
            )
            db.add(charge_line)
    
    # Process parts produced
    if parts_produced_data:
        for idx, part_data in enumerate(parts_produced_data, start=1):
            raw_part = part_data.get("original_part_description", "").strip()
            if not raw_part:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Parts produced line {idx} missing part description",
                )
            
            qty_prod = Decimal(str(part_data.get("quantity_produced", "0")))
            if qty_prod <= Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Parts produced line {idx} quantity must be strictly positive",
                )
            
            unit_weight = None
            if part_data.get("unit_cast_weight") is not None:
                unit_weight = Decimal(str(part_data.get("unit_cast_weight")))
            
            part_line = HeatPartsProduced(
                heat_id=heat.id,
                line_number=idx,
                part_item_id=part_data.get("part_item_id"),
                original_part_description=raw_part,
                quantity_produced=qty_prod,
                unit_cast_weight=unit_weight,
                weight_uom_id=part_data.get("weight_uom_id"),
                classification=part_data.get("classification", CastingClassification.GOOD.value),
                source_row_reference=part_data.get("source_row_reference"),
                remarks=part_data.get("remarks"),
            )
            db.add(part_line)
    
    db.commit()
    db.refresh(heat)
    return heat


def get_heat_by_id(db: Session, heat_id: int) -> Optional[HeatHeader]:
    """Retrieves heat by ID with charges and parts loaded."""
    return db.execute(
        select(HeatHeader)
        .options(
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.material_item),
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.uom),
            selectinload(HeatHeader.parts_produced).selectinload(HeatPartsProduced.weight_uom),
            selectinload(HeatHeader.metal_tapped_uom),
        )
        .where(HeatHeader.id == heat_id)
    ).scalar_one_or_none()


def get_heat_by_number(db: Session, heat_number: str) -> Optional[HeatHeader]:
    """Retrieves heat by exact raw or normalized heat number."""
    cleaned = heat_number.strip()
    try:
        norm = normalize_heat_number(cleaned)
    except Exception:
        norm = cleaned
    
    return db.execute(
        select(HeatHeader)
        .options(
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.material_item),
            selectinload(HeatHeader.charge_lines).selectinload(HeatChargeLine.uom),
            selectinload(HeatHeader.parts_produced),
        )
        .where(
            (HeatHeader.heat_number == cleaned) | 
            (HeatHeader.normalized_heat_number == norm)
        )
    ).scalar_one_or_none()


def list_heats(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    furnace_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[HeatHeader], int]:
    """Lists heats with optional date range, furnace, and search filters."""
    stmt = select(HeatHeader).options(
        selectinload(HeatHeader.charge_lines),
        selectinload(HeatHeader.parts_produced),
        selectinload(HeatHeader.metal_tapped_uom),
    )
    if date_from:
        stmt = stmt.where(HeatHeader.heat_date >= date_from)
    if date_to:
        stmt = stmt.where(HeatHeader.heat_date <= date_to)
    if furnace_id:
        stmt = stmt.where(HeatHeader.furnace_id == furnace_id.strip())
    if status_filter:
        stmt = stmt.where(HeatHeader.production_status == status_filter)
    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            HeatHeader.heat_number.ilike(s) |
            HeatHeader.normalized_heat_number.ilike(s) |
            HeatHeader.furnace_id.ilike(s)
        )
    
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(HeatHeader.heat_date.desc(), HeatHeader.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return items, total
