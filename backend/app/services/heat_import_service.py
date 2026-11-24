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
import openpyxl
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


CANONICAL_HEAT_HEADERS: Dict[str, List[str]] = {
    "heat_number": ["heat_number", "heatnumber", "heat_no", "heatno", "heat"],
    "heat_date": ["heat_date", "heatdate", "date"],
    "furnace_id": ["furnace_id", "furnaceid", "furnace", "furnace_no"],
    "shift": ["shift"],
    "material_description": [
        "material_description",
        "materialdescription",
        "material",
        "description",
        "item_description",
        "material_desc",
    ],
    "charged_quantity": [
        "charged_quantity",
        "chargedquantity",
        "charged_qty",
        "quantity",
        "qty",
        "charged_weight",
    ],
    "uom_code": ["uom_code", "uomcode", "uom", "unit"],
    "part_description": [
        "part_description",
        "partdescription",
        "part",
        "part_name",
        "casting",
        "casting_description",
    ],
    "quantity_produced": [
        "quantity_produced",
        "quantityproduced",
        "qty_produced",
        "part_qty",
        "cast_quantity",
        "cast_qty",
    ],
    "remarks": ["remarks", "remark", "notes", "note"],
}

REQUIRED_HEAT_HEADERS = {"heat_number", "heat_date", "material_description", "charged_quantity"}


def _normalize_header_name(header_str: str) -> Optional[str]:
    """Normalizes an Excel column header into a canonical field name."""
    if not header_str:
        return None
    cleaned = str(header_str).strip().lower().replace(" ", "_").replace("-", "_")
    compact = cleaned.replace("_", "")
    for canonical, aliases in CANONICAL_HEAT_HEADERS.items():
        if cleaned in aliases or compact in aliases:
            return canonical
    return None


def parse_date(val: Any) -> Optional[date]:
    """Safely parses date from string or date/datetime object."""
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    if not val:
        return None
    s = str(val).strip()
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


def _parse_flattened_sheet(sheet) -> List[Dict[str, Any]]:
    """Extracts rows from a single flattened worksheet."""
    all_rows = list(sheet.iter_rows(values_only=True))
    if not all_rows:
        return []

    header_row = None
    header_row_idx = 0
    for idx, row in enumerate(all_rows):
        if any(cell is not None and str(cell).strip() != "" for cell in row):
            header_row = row
            header_row_idx = idx
            break

    if not header_row:
        return []

    col_mapping: Dict[int, str] = {}
    for col_idx, cell_val in enumerate(header_row):
        if cell_val is not None:
            canon = _normalize_header_name(str(cell_val))
            if canon:
                col_mapping[col_idx] = canon

    present_canonical = set(col_mapping.values())
    missing_required = REQUIRED_HEAT_HEADERS - present_canonical
    if missing_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Excel worksheet missing required column(s): {', '.join(sorted(missing_required))}.",
        )

    data_rows: List[Dict[str, Any]] = []
    for row in all_rows[header_row_idx + 1:]:
        if not any(cell is not None and str(cell).strip() != "" for cell in row):
            continue

        row_dict: Dict[str, Any] = {}
        for col_idx, canon in col_mapping.items():
            if col_idx < len(row):
                cell = row[col_idx]
                if cell is None:
                    row_dict[canon] = ""
                elif isinstance(cell, (datetime, date)):
                    dt_val = cell.date() if isinstance(cell, datetime) else cell
                    row_dict[canon] = dt_val.isoformat()
                else:
                    row_dict[canon] = str(cell).strip()
            else:
                row_dict[canon] = ""

        if not row_dict.get("uom_code"):
            row_dict["uom_code"] = "KG"

        data_rows.append(row_dict)

    return data_rows


def _parse_multisheet_heat_log(wb, heat_sheet_name: str, charge_sheet_name: str) -> List[Dict[str, Any]]:
    """Joins 'Heat Log' and 'Charge Details' sheets by heat number."""
    ws_heat = wb[heat_sheet_name]
    ws_charge = wb[charge_sheet_name]

    heat_rows = list(ws_heat.iter_rows(values_only=True))
    if not heat_rows or len(heat_rows) < 2:
        return []
    heat_header_map = {
        col_idx: _normalize_header_name(str(val))
        for col_idx, val in enumerate(heat_rows[0])
        if val is not None and _normalize_header_name(str(val))
    }

    heat_meta: Dict[str, Dict[str, Any]] = {}
    for r in heat_rows[1:]:
        if not any(c is not None and str(c).strip() != "" for c in r):
            continue
        h_dict = {
            canon: (
                r[col].date().isoformat()
                if isinstance(r[col], datetime)
                else (r[col].isoformat() if isinstance(r[col], date) else str(r[col]).strip())
            )
            for col, canon in heat_header_map.items()
            if col < len(r) and r[col] is not None
        }
        h_num = h_dict.get("heat_number", "")
        if h_num:
            heat_meta[h_num] = h_dict
            try:
                norm = normalize_heat_number(h_num)
                heat_meta[norm] = h_dict
            except Exception:
                pass

    charge_rows = list(ws_charge.iter_rows(values_only=True))
    if not charge_rows or len(charge_rows) < 2:
        return []
    charge_header_map = {
        col_idx: _normalize_header_name(str(val))
        for col_idx, val in enumerate(charge_rows[0])
        if val is not None and _normalize_header_name(str(val))
    }

    combined_rows: List[Dict[str, Any]] = []
    for r in charge_rows[1:]:
        if not any(c is not None and str(c).strip() != "" for c in r):
            continue
        c_dict = {
            canon: str(r[col]).strip()
            for col, canon in charge_header_map.items()
            if col < len(r) and r[col] is not None
        }
        h_num = c_dict.get("heat_number", "")
        norm_h = ""
        if h_num:
            try:
                norm_h = normalize_heat_number(h_num)
            except Exception:
                norm_h = h_num
        meta = heat_meta.get(h_num) or heat_meta.get(norm_h) or {}

        row_dict = {
            "heat_number": h_num,
            "heat_date": meta.get("heat_date", ""),
            "furnace_id": meta.get("furnace_id", ""),
            "shift": meta.get("shift", ""),
            "material_description": c_dict.get("material_description", ""),
            "charged_quantity": c_dict.get("charged_quantity", ""),
            "uom_code": c_dict.get("uom_code", "KG") or "KG",
            "part_description": meta.get("part_description", ""),
            "quantity_produced": meta.get("quantity_produced", ""),
            "remarks": c_dict.get("remarks", ""),
        }
        combined_rows.append(row_dict)

    return combined_rows


def parse_excel_heat_log(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses modern Excel (.xlsx, .xlsm) workbooks into normalized row dictionaries.
    Supports either flattened single-sheet layout or multi-sheet ('Heat Log' + 'Charge Details').
    Validates workbook readability, non-empty content, and required columns.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded Excel file is empty.",
        )

    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupt Excel workbook: {str(e)}",
        )

    sheet_names_lower = {s.strip().lower(): s for s in wb.sheetnames}

    if "heat log" in sheet_names_lower and "charge details" in sheet_names_lower:
        rows = _parse_multisheet_heat_log(wb, sheet_names_lower["heat log"], sheet_names_lower["charge details"])
    else:
        sheet = wb.active
        if not sheet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Excel workbook contains no active worksheet.",
            )
        rows = _parse_flattened_sheet(sheet)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded Excel file contains no data rows.",
        )

    return rows


def generate_heat_log_template_excel() -> bytes:
    """Generates a styled .xlsx template for bulk heat log imports."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Heat_Log_Template"

    headers = [
        "heat_number",
        "heat_date",
        "furnace_id",
        "shift",
        "material_description",
        "charged_quantity",
        "uom_code",
        "part_description",
        "quantity_produced",
        "remarks",
    ]
    ws.append(headers)

    header_fill = openpyxl.styles.PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    header_font = openpyxl.styles.Font(bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 20

    ws.append([
        "102603-3801",
        "2026-10-22",
        "FURNACE-1",
        "SHIFT_A",
        "Pig Iron Foundry Grade",
        3500.0,
        "KG",
        "Differential Housing",
        40,
        "Main charge",
    ])
    ws.append([
        "102603-3801",
        "2026-10-22",
        "FURNACE-1",
        "SHIFT_A",
        "Cast Iron Borings",
        1500.0,
        "KG",
        "",
        "",
        "Boring additions",
    ])
    ws.append([
        "102603-3802",
        "2026-10-22",
        "FURNACE-2",
        "SHIFT_B",
        "CRC Scrap High Manganese",
        4500.0,
        "KG",
        "Axle Housing",
        25,
        "Full melt",
    ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def preview_heat_log_import(
    db: Session,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Dry-run preview validation of heat log rows.
    Checks required fields, heat normalization, UOM validity, alias resolution,
    and in-batch header consistency across rows of the same heat.
    Returns structured findings and summary metrics without committing.
    """
    total_rows = len(rows)
    valid_rows = 0
    error_rows = 0
    findings = []

    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}

    existing_heats = {
        h.normalized_heat_number for h in db.execute(select(HeatHeader)).scalars().all()
    }

    rows_by_heat: Dict[str, List[Dict[str, Any]]] = {}
    for idx, r in enumerate(rows, start=1):
        raw_heat = str(r.get("heat_number", "")).strip()
        norm_h = ""
        if raw_heat:
            try:
                norm_h = normalize_heat_number(raw_heat)
            except ValueError:
                norm_h = ""

        parsed_d = parse_date(r.get("heat_date"))
        furnace_val = str(r.get("furnace_id", "")).strip() or None
        shift_val = str(r.get("shift", "")).strip() or None

        if norm_h:
            rows_by_heat.setdefault(norm_h, []).append({
                "row_number": idx,
                "heat_date": parsed_d,
                "furnace_id": furnace_val,
                "shift": shift_val,
            })

    header_conflict_errors: Dict[int, List[str]] = {}
    for norm_h, heat_rows in rows_by_heat.items():
        if len(heat_rows) <= 1:
            continue

        valid_date_rows = [hr for hr in heat_rows if hr["heat_date"] is not None]
        if len(valid_date_rows) > 1:
            first_dt_row = valid_date_rows[0]
            first_dt = first_dt_row["heat_date"]
            first_dt_idx = first_dt_row["row_number"]
            for hr in valid_date_rows[1:]:
                if hr["heat_date"] != first_dt:
                    msg_hr = (
                        f"Header conflict for heat '{norm_h}': heat_date '{hr['heat_date'].isoformat()}' "
                        f"in row {hr['row_number']} conflicts with row {first_dt_idx} ('{first_dt.isoformat()}')"
                    )
                    msg_first = (
                        f"Header conflict for heat '{norm_h}': heat_date '{first_dt.isoformat()}' "
                        f"in row {first_dt_idx} conflicts with row {hr['row_number']} ('{hr['heat_date'].isoformat()}')"
                    )
                    header_conflict_errors.setdefault(hr["row_number"], []).append(msg_hr)
                    if msg_first not in header_conflict_errors.setdefault(first_dt_idx, []):
                        header_conflict_errors[first_dt_idx].append(msg_first)

        first_furnace_row = heat_rows[0]
        first_furnace = first_furnace_row["furnace_id"]
        first_furnace_norm = (first_furnace or "").strip().upper()
        first_furnace_idx = first_furnace_row["row_number"]
        for hr in heat_rows[1:]:
            cur_furnace = hr["furnace_id"]
            cur_furnace_norm = (cur_furnace or "").strip().upper()
            if cur_furnace_norm != first_furnace_norm:
                msg_hr = (
                    f"Header conflict for heat '{norm_h}': furnace_id '{cur_furnace or ''}' "
                    f"in row {hr['row_number']} conflicts with row {first_furnace_idx} ('{first_furnace or ''}')"
                )
                msg_first = (
                    f"Header conflict for heat '{norm_h}': furnace_id '{first_furnace or ''}' "
                    f"in row {first_furnace_idx} conflicts with row {hr['row_number']} ('{cur_furnace or ''}')"
                )
                header_conflict_errors.setdefault(hr["row_number"], []).append(msg_hr)
                if msg_first not in header_conflict_errors.setdefault(first_furnace_idx, []):
                    header_conflict_errors[first_furnace_idx].append(msg_first)

        first_shift_row = heat_rows[0]
        first_shift = first_shift_row["shift"]
        first_shift_norm = (first_shift or "").strip().upper()
        first_shift_idx = first_shift_row["row_number"]
        for hr in heat_rows[1:]:
            cur_shift = hr["shift"]
            cur_shift_norm = (cur_shift or "").strip().upper()
            if cur_shift_norm != first_shift_norm:
                msg_hr = (
                    f"Header conflict for heat '{norm_h}': shift '{cur_shift or ''}' "
                    f"in row {hr['row_number']} conflicts with row {first_shift_idx} ('{first_shift or ''}')"
                )
                msg_first = (
                    f"Header conflict for heat '{norm_h}': shift '{first_shift or ''}' "
                    f"in row {first_shift_idx} conflicts with row {hr['row_number']} ('{cur_shift or ''}')"
                )
                header_conflict_errors.setdefault(hr["row_number"], []).append(msg_hr)
                if msg_first not in header_conflict_errors.setdefault(first_shift_idx, []):
                    header_conflict_errors[first_shift_idx].append(msg_first)

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

        if norm_heat in existing_heats:
            row_errors.append(f"Heat '{norm_heat}' already exists in database")

        if idx in header_conflict_errors:
            row_errors.extend(header_conflict_errors[idx])

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
        "rows": rows,
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

    heats_data: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        raw_heat = str(r.get("heat_number")).strip()
        norm_heat = normalize_heat_number(raw_heat)
        parsed_dt = parse_date(r.get("heat_date"))
        furnace_id = str(r.get("furnace_id", "")).strip() or None
        shift = str(r.get("shift", "")).strip() or None

        if norm_heat not in heats_data:
            heats_data[norm_heat] = {
                "heat_number": raw_heat,
                "normalized_heat_number": norm_heat,
                "heat_date": parsed_dt,
                "furnace_id": furnace_id,
                "shift": shift,
                "charges": [],
                "parts": [],
            }
        else:
            existing_entry = heats_data[norm_heat]
            if existing_entry["heat_date"] != parsed_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot commit import: conflicting heat_date for heat '{norm_heat}'. "
                        f"'{parsed_dt}' conflicts with '{existing_entry['heat_date']}'"
                    ),
                )
            if (existing_entry["furnace_id"] or "").strip().upper() != (furnace_id or "").strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot commit import: conflicting furnace_id for heat '{norm_heat}'. "
                        f"'{furnace_id}' conflicts with '{existing_entry['furnace_id']}'"
                    ),
                )
            if (existing_entry["shift"] or "").strip().upper() != (shift or "").strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot commit import: conflicting shift for heat '{norm_heat}'. "
                        f"'{shift}' conflicts with '{existing_entry['shift']}'"
                    ),
                )

        uom_code = str(r.get("uom_code", "KG")).strip().upper()
        uom_obj = uoms_by_code[uom_code]
        qty = parse_decimal(r.get("charged_quantity"))

        heats_data[norm_heat]["charges"].append({
            "original_material_description": str(r.get("material_description")).strip(),
            "charged_quantity": qty,
            "uom_id": uom_obj.id,
            "remarks": r.get("remarks"),
        })

        raw_part = str(r.get("part_description", "")).strip()
        if raw_part:
            part_qty = parse_decimal(r.get("quantity_produced")) or Decimal("1")
            heats_data[norm_heat]["parts"].append({
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
