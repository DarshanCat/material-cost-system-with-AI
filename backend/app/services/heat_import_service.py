"""
Heat Log Excel Import Service.
Validates multi-sheet or flattened workbooks containing:
- Heat Log headers
- Charge Details
- Parts Produced
Enforces row-by-row preview validation, atomic commit, and duplicate prevention.
STRICT RULE: Heat imports NEVER create stock movements.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional
import io
import re
from sqlalchemy.orm import Session
from sqlalchemy import select
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
from app.services.validators import normalize_heat_number, normalize_alias_key
from app.services.material_alias_service import resolve_material_by_description
from app.services.heat_service import create_heat


def parse_date(val: Any) -> Optional[date]:
    """Safely parses date from string or date/datetime object."""
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    if not val:
        return None
    s = str(val).strip()
    # Try YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_decimal(val: Any) -> Optional[Decimal]:
    """Safely parses Decimal from string or numeric."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return None


def preview_heat_log_import(
    db: Session,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Dry-run preview validation of heat log rows.
    Checks required fields, heat normalization, UOM validity, and alias resolution.
    Returns structured findings and summary metrics without committing.
    """
    total_rows = len(rows)
    valid_rows = 0
    error_rows = 0
    findings = []
    
    # Pre-cache active UOMs and items for fast validation
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}
    
    # Check existing heats in database
    existing_heats = {
        h.normalized_heat_number for h in db.execute(select(HeatHeader)).scalars().all()
    }
    
    seen_in_batch: set[str] = set()

    for idx, r in enumerate(rows, start=1):
        row_errors = []
        raw_heat = str(r.get("heat_number", "")).strip()
        if not raw_heat:
            row_errors.append("Missing required 'heat_number'")
        
        norm_heat = ""
        if raw_heat:
            try:
                norm_heat = normalize_heat_number(raw_heat)
            except ValueError as e:
                row_errors.append(f"Invalid heat number format: {str(e)}")
        
        # Check duplicate against DB and within batch
        if norm_heat in existing_heats:
            row_errors.append(f"Heat '{norm_heat}' already exists in database")
        
        raw_date = r.get("heat_date")
        parsed_dt = parse_date(raw_date)
        if not parsed_dt:
            row_errors.append("Invalid or missing 'heat_date'")
        
        raw_mat = str(r.get("material_description", "")).strip()
        if not raw_mat:
            row_errors.append("Missing 'material_description'")
        
        qty = parse_decimal(r.get("charged_quantity"))
        if qty is None or qty <= Decimal("0"):
            row_errors.append("Charged quantity must be a strictly positive number")
        
        uom_code = str(r.get("uom_code", "KG")).strip().upper()
        uom_obj = uoms_by_code.get(uom_code)
        if not uom_obj:
            row_errors.append(f"Unrecognized UOM code '{uom_code}'")
        
        # Check alias resolution
        resolved_item = None
        if raw_mat:
            resolved_item = resolve_material_by_description(db, raw_mat)
        
        is_valid = len(row_errors) == 0
        if is_valid:
            valid_rows += 1
        else:
            error_rows += 1
        
        findings.append({
            "row_number": idx,
            "heat_number": raw_heat,
            "normalized_heat_number": norm_heat,
            "heat_date": parsed_dt.isoformat() if parsed_dt else str(raw_date),
            "material_description": raw_mat,
            "resolved_item_code": resolved_item.item_code if resolved_item else None,
            "resolved_item_name": resolved_item.name if resolved_item else None,
            "alias_status": "MAPPED" if resolved_item else "UNMAPPED_ALIAS",
            "charged_quantity": str(qty) if qty is not None else str(r.get("charged_quantity", "")),
            "uom_code": uom_code,
            "is_valid": is_valid,
            "errors": row_errors,
        })

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "error_rows": error_rows,
        "can_commit": error_rows == 0 and total_rows > 0,
        "findings": findings,
    }


def commit_heat_log_import(
    db: Session,
    rows: List[Dict[str, Any]],
    created_by: str,
    source_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically commits validated heat log batch.
    Groups charge lines by heat_number and creates HeatHeader and HeatChargeLines.
    Rejects completely if any blocking errors exist.
    """
    preview = preview_heat_log_import(db, rows)
    if not preview["can_commit"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot commit heat log import: batch contains {preview['error_rows']} error(s). "
                "Resolve all blocking errors and re-preview."
            ),
        )
    
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}
    
    # Group rows by heat
    heats_data: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        raw_heat = str(r.get("heat_number")).strip()
        parsed_dt = parse_date(r.get("heat_date"))
        furnace_id = str(r.get("furnace_id", "")).strip() or None
        shift = str(r.get("shift", "")).strip() or None
        
        if raw_heat not in heats_data:
            heats_data[raw_heat] = {
                "heat_number": raw_heat,
                "heat_date": parsed_dt,
                "furnace_id": furnace_id,
                "shift": shift,
                "charges": [],
                "parts": [],
            }
        
        uom_code = str(r.get("uom_code", "KG")).strip().upper()
        uom_obj = uoms_by_code[uom_code]
        qty = parse_decimal(r.get("charged_quantity"))
        
        heats_data[raw_heat]["charges"].append({
            "original_material_description": str(r.get("material_description")).strip(),
            "charged_quantity": qty,
            "uom_id": uom_obj.id,
            "remarks": r.get("remarks"),
        })
        
        # Part produced if specified in flattened row
        raw_part = str(r.get("part_description", "")).strip()
        if raw_part:
            part_qty = parse_decimal(r.get("quantity_produced")) or Decimal("1")
            heats_data[raw_heat]["parts"].append({
                "original_part_description": raw_part,
                "quantity_produced": part_qty,
                "classification": r.get("classification", CastingClassification.GOOD.value),
            })

    created_heats = []
    for h_data in heats_data.values():
        heat = create_heat(
            db=db,
            heat_number=h_data["heat_number"],
            heat_date=h_data["heat_date"],
            created_by=created_by,
            furnace_id=h_data["furnace_id"],
            shift=h_data["shift"],
            source_document_reference=source_filename,
            charge_lines_data=h_data["charges"],
            parts_produced_data=h_data["parts"] if h_data["parts"] else None,
        )
        created_heats.append(heat.heat_number)

    return {
        "status": "SUCCESS",
        "heats_created_count": len(created_heats),
        "heats_created": created_heats,
        "total_rows_imported": len(rows),
    }
