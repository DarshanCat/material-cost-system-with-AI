"""
Induction Furnace Heat Log Master Service.
Manages Heat Headers, Furnace Charge Details, and Parts Produced.
STRICT INVENTORY RULE: Heat Log charge records NEVER create stock movements.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.heat import (
    HeatHeader,
    HeatChargeLine,
    HeatPartsProduced,
    ProductionStatus,
    HeatChargeValidationStatus,
    CastingClassification,
    HeelMeasurementMethod,
    HeelVerificationStatus,
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
    opening_liquid_heel_kg: Optional[Decimal] = None,
    closing_liquid_heel_kg: Optional[Decimal] = None,
    heel_measurement_method: Optional[str] = None,
    is_cold_start: bool = False,
    is_furnace_empty: bool = False,
    opening_heel_source_heat_id: Optional[int] = None,
    charge_lines_data: Optional[List[Dict[str, Any]]] = None,
    parts_produced_data: Optional[List[Dict[str, Any]]] = None,
) -> HeatHeader:
    """
    Creates a new induction furnace heat log record.
    Preserves original heat number and computes normalized reference (e.g. H-102603-3721).
    Validates charge line materials against alias master.
    Validates liquid heel measurements, cold-start, furnace-empty, and carry-forward rules.
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
    
    # Heel quantity validations: non-negative
    if opening_liquid_heel_kg is not None and opening_liquid_heel_kg < Decimal("0.0000"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Opening liquid heel ({opening_liquid_heel_kg} kg) cannot be negative.",
        )
    if closing_liquid_heel_kg is not None and closing_liquid_heel_kg < Decimal("0.0000"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Closing liquid heel ({closing_liquid_heel_kg} kg) cannot be negative.",
        )

    # Cold start logic: opening heel must be zero
    if is_cold_start:
        if opening_liquid_heel_kg is not None and opening_liquid_heel_kg > Decimal("0.0000"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Cold start heat cannot have a positive opening heel ({opening_liquid_heel_kg} kg). Must be 0.",
            )
        opening_liquid_heel_kg = Decimal("0.0000")
        opening_heel_source_heat_id = None
        if not heel_measurement_method:
            heel_measurement_method = HeelMeasurementMethod.COLD_START.value

    # Furnace empty logic: closing heel must be zero
    if is_furnace_empty:
        if closing_liquid_heel_kg is not None and closing_liquid_heel_kg > Decimal("0.0000"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Furnace-empty heat cannot have a positive closing heel ({closing_liquid_heel_kg} kg). Must be 0.",
            )
        closing_liquid_heel_kg = Decimal("0.0000")
        if not heel_measurement_method:
            heel_measurement_method = HeelMeasurementMethod.FURNACE_EMPTIED.value

    # Carry-forward source heat validation
    if opening_heel_source_heat_id is not None:
        source_heat = db.execute(
            select(HeatHeader).where(HeatHeader.id == opening_heel_source_heat_id)
        ).scalar_one_or_none()
        if not source_heat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Opening heel source heat ID {opening_heel_source_heat_id} not found.",
            )
        if furnace_id and source_heat.furnace_id and furnace_id.strip() != source_heat.furnace_id.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Cannot carry forward heel across different furnaces ('{source_heat.furnace_id}' to '{furnace_id}').",
            )
        if source_heat.closing_liquid_heel_kg is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Source heat '{source_heat.heat_number}' has no closing liquid heel recorded.",
            )
        if source_heat.heel_verification_status != HeelVerificationStatus.VERIFIED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Source heat '{source_heat.heat_number}' closing heel is unverified (status: {source_heat.heel_verification_status}). Automatic carry-forward blocked.",
            )
        # Prevent concurrent multiple consumption
        existing_consumer = db.execute(
            select(HeatHeader).where(HeatHeader.opening_heel_source_heat_id == source_heat.id)
        ).scalar_one_or_none()
        if existing_consumer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Source heat '{source_heat.heat_number}' closing heel was already consumed by heat '{existing_consumer.heat_number}'.",
            )
        if opening_liquid_heel_kg is None:
            opening_liquid_heel_kg = source_heat.closing_liquid_heel_kg

    # Verification status determination
    has_heel_entry = (opening_liquid_heel_kg is not None) or (closing_liquid_heel_kg is not None)
    heel_verif_status = HeelVerificationStatus.PENDING_VERIFICATION.value if has_heel_entry else HeelVerificationStatus.UNRECORDED.value
    heel_recorder = created_by if has_heel_entry else None

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
        opening_liquid_heel_kg=opening_liquid_heel_kg,
        closing_liquid_heel_kg=closing_liquid_heel_kg,
        heel_measurement_method=heel_measurement_method,
        heel_recorded_by=heel_recorder,
        heel_verification_status=heel_verif_status,
        is_cold_start=is_cold_start,
        is_furnace_empty=is_furnace_empty,
        opening_heel_source_heat_id=opening_heel_source_heat_id,
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
        selectinload(HeatHeader.charge_lines).joinedload(HeatChargeLine.material_item),
        selectinload(HeatHeader.charge_lines).joinedload(HeatChargeLine.uom),
        selectinload(HeatHeader.parts_produced).joinedload(HeatPartsProduced.part_item),
        selectinload(HeatHeader.parts_produced).joinedload(HeatPartsProduced.weight_uom),
        joinedload(HeatHeader.metal_tapped_uom),
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
    
    count_stmt = select(func.count(HeatHeader.id))
    if stmt.whereclause is not None:
        count_stmt = count_stmt.where(stmt.whereclause)
    total = db.scalar(count_stmt) or 0
    items = db.execute(
        stmt.order_by(HeatHeader.heat_date.desc(), HeatHeader.id.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return items, total


def propose_heat_carry_forward(
    db: Session,
    furnace_id: str,
) -> Dict[str, Any]:
    """
    Finds the latest heat for the given furnace and proposes the opening heel.
    Enforces that:
    1. A cold start defaults opening heel = 0.
    2. An unverified closing heel BLOCKS automatic carry-forward.
    3. Missing closing heel BLOCKS automatic carry-forward.
    4. An already consumed closing heel BLOCKS duplicate consumption.
    """
    clean_furnace = furnace_id.strip() if furnace_id else ""
    if not clean_furnace:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Furnace ID must be provided to propose carry-forward.",
        )

    # Latest heat by heat_date desc, id desc on this furnace
    latest_heat = db.execute(
        select(HeatHeader)
        .where(HeatHeader.furnace_id == clean_furnace)
        .order_by(HeatHeader.heat_date.desc(), HeatHeader.id.desc())
    ).scalars().first()

    if not latest_heat:
        return {
            "can_carry_forward": False,
            "furnace_id": clean_furnace,
            "source_heat_id": None,
            "source_heat_number": None,
            "proposed_opening_heel_kg": Decimal("0.0000"),
            "is_cold_start": True,
            "verification_status": None,
            "message": f"No previous heat found for furnace {clean_furnace}. Cold start required (opening heel = 0).",
        }

    # If furnace was recorded empty in previous heat
    if latest_heat.is_furnace_empty:
        if latest_heat.heel_verification_status == HeelVerificationStatus.VERIFIED.value:
            return {
                "can_carry_forward": True,
                "furnace_id": clean_furnace,
                "source_heat_id": latest_heat.id,
                "source_heat_number": latest_heat.heat_number,
                "proposed_opening_heel_kg": Decimal("0.0000"),
                "is_cold_start": True,
                "verification_status": latest_heat.heel_verification_status,
                "message": f"Previous heat {latest_heat.heat_number} recorded furnace empty. Cold start opening heel of 0 proposed.",
            }
        else:
            return {
                "can_carry_forward": False,
                "furnace_id": clean_furnace,
                "source_heat_id": latest_heat.id,
                "source_heat_number": latest_heat.heat_number,
                "proposed_opening_heel_kg": None,
                "is_cold_start": False,
                "verification_status": latest_heat.heel_verification_status,
                "message": f"Previous heat {latest_heat.heat_number} furnace-empty status is unverified ({latest_heat.heel_verification_status}). Automatic carry-forward blocked.",
            }

    # Check if closing heel exists
    if latest_heat.closing_liquid_heel_kg is None:
        return {
            "can_carry_forward": False,
            "furnace_id": clean_furnace,
            "source_heat_id": latest_heat.id,
            "source_heat_number": latest_heat.heat_number,
            "proposed_opening_heel_kg": None,
            "is_cold_start": False,
            "verification_status": latest_heat.heel_verification_status,
            "message": f"Previous heat {latest_heat.heat_number} has no closing liquid heel recorded. Automatic carry-forward blocked.",
        }

    # Check verification status
    if latest_heat.heel_verification_status != HeelVerificationStatus.VERIFIED.value:
        return {
            "can_carry_forward": False,
            "furnace_id": clean_furnace,
            "source_heat_id": latest_heat.id,
            "source_heat_number": latest_heat.heat_number,
            "proposed_opening_heel_kg": None,
            "is_cold_start": False,
            "verification_status": latest_heat.heel_verification_status,
            "message": f"Previous heat {latest_heat.heat_number} closing heel is unverified (status: {latest_heat.heel_verification_status}). Automatic carry-forward blocked.",
        }

    # Check concurrency / prior consumption
    existing_consumer = db.execute(
        select(HeatHeader).where(HeatHeader.opening_heel_source_heat_id == latest_heat.id)
    ).scalar_one_or_none()
    if existing_consumer:
        return {
            "can_carry_forward": False,
            "furnace_id": clean_furnace,
            "source_heat_id": latest_heat.id,
            "source_heat_number": latest_heat.heat_number,
            "proposed_opening_heel_kg": None,
            "is_cold_start": False,
            "verification_status": latest_heat.heel_verification_status,
            "message": f"Closing heel of heat {latest_heat.heat_number} has already been consumed by heat {existing_consumer.heat_number}.",
        }

    return {
        "can_carry_forward": True,
        "furnace_id": clean_furnace,
        "source_heat_id": latest_heat.id,
        "source_heat_number": latest_heat.heat_number,
        "proposed_opening_heel_kg": latest_heat.closing_liquid_heel_kg,
        "is_cold_start": False,
        "verification_status": latest_heat.heel_verification_status,
        "message": f"Verified closing heel from heat {latest_heat.heat_number} proposed for carry-forward.",
    }


def verify_heat_heel(
    db: Session,
    heat_id: int,
    decision: str,
    verified_by: str,
    comments: Optional[str] = None,
) -> HeatHeader:
    """
    Verifies or rejects liquid heel measurement on a heat record.
    Enforces maker-checker: the user who recorded the measurement cannot verify it.
    Maintains audit trace and prevents silent overwriting of verified records.
    """
    heat = db.execute(
        select(HeatHeader)
        .options(
            selectinload(HeatHeader.charge_lines),
            selectinload(HeatHeader.parts_produced),
            selectinload(HeatHeader.metal_tapped_uom),
        )
        .where(HeatHeader.id == heat_id)
    ).scalar_one_or_none()

    if not heat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heat ID {heat_id} not found",
        )

    # Maker-Checker check
    if heat.heel_recorded_by and heat.heel_recorded_by == verified_by:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maker-checker violation: User who recorded the liquid heel cannot verify their own measurement.",
        )

    # Check if already verified
    if heat.heel_verification_status == HeelVerificationStatus.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Heat ID {heat_id} liquid heel has already been verified by {heat.heel_verified_by} at {heat.heel_verified_at}. Cannot overwrite verified measurement.",
        )

    now_utc = datetime.now(timezone.utc)
    if decision == "VERIFY":
        heat.heel_verification_status = HeelVerificationStatus.VERIFIED.value
        heat.heel_verified_by = verified_by
        heat.heel_verified_at = now_utc
    elif decision == "REJECT":
        heat.heel_verification_status = HeelVerificationStatus.REJECTED.value
        heat.heel_verified_by = verified_by
        heat.heel_verified_at = now_utc
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid decision '{decision}'. Must be 'VERIFY' or 'REJECT'.",
        )

    # Audit traceability in notes
    audit_entry = f"[HEEL_AUDIT] {decision} by {verified_by} at {now_utc.isoformat()}."
    if comments:
        audit_entry += f" Comments: {comments}"
    heat.notes = f"{heat.notes}\n{audit_entry}" if heat.notes else audit_entry

    db.add(heat)
    db.commit()
    db.refresh(heat)
    return heat
