"""
Excel Import Validation Engine.
Performs header validation, type coercion, master data reference lookup,
duplicate checks, and atomic preview / commit for bulk material entries.
"""

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import openpyxl
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.vendor import Vendor
from app.models.department import Department
from app.schemas.excel_import import (
    ExcelImportValidationSummary,
    RowValidationFinding,
    ExcelImportCommitRequest,
)
from app.schemas.grn import GRNCreate, GRNLineItemCreate
from app.schemas.issue import MaterialIssueCreate, MaterialIssueLineItemCreate
from app.schemas.waste import WasteDispositionCreate, WasteDispositionLineItemCreate
from app.models.grn import GRNSourceType
from app.models.waste import WasteType, DispositionType
from app.services.decimal_validator import validate_and_flag_quantity, validate_rate_and_gst
from app.services.duplicate_detector import check_grn_invoice_duplicate
from app.services.grn_service import create_grn
from app.services.issue_service import create_material_issue
from app.services.waste_service import create_waste_disposition


REQUIRED_HEADERS = {
    "GRN": [
        "Receipt Date",
        "Source Type",
        "Vendor Name",
        "Invoice No",
        "Invoice Date",
        "Item Code",
        "UOM",
        "Quantity",
        "Rate Ex GST",
        "GST %",
    ],
    "ISSUE": [
        "Issue Date",
        "Issuing Dept",
        "Receiving Dept",
        "Heat Ref No",
        "Item Code",
        "UOM",
        "Quantity",
        "Remarks",
    ],
    "WASTE": [
        "Disposition Date",
        "Waste Type",
        "Disposition Type",
        "Source Dept",
        "Item Code",
        "UOM",
        "Quantity",
        "Reason",
    ],
}


def parse_excel_date(val: Any) -> Optional[date]:
    """
    Robustly parses date cell values from Excel (datetime, date, or formatted strings).
    Supported string formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, ISO timestamps.
    Returns datetime.date or None if empty/invalid.
    """
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()

    s = str(val).strip()
    if not s:
        return None

    # Strip time part if present
    if "T" in s:
        s = s.split("T")[0].strip()
    elif " " in s:
        s = s.split(" ")[0].strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    return None


def parse_excel_decimal(val: Any) -> Optional[Decimal]:
    """
    Safely parses numeric decimal values from Excel cells without unhandled InvalidOperation crashes.
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val))
        except (InvalidOperation, ValueError):
            return None
    s = str(val).strip()
    if not s:
        return None
    clean = s.replace(",", "").replace("₹", "").replace("$", "").strip()
    try:
        return Decimal(clean)
    except (InvalidOperation, ValueError):
        return None


def parse_and_validate_excel(
    file_bytes: bytes,
    import_type: str,
    db: Session,
) -> ExcelImportValidationSummary:
    """
    Parses an uploaded Excel file, validates headers, and validates each data row.
    Guarantees atomic summary: can_commit is True ONLY when error_rows_count == 0 and total_rows > 0.
    Detects intra-document duplicate material lines and existing vendor invoice duplicates.
    """
    import_type = import_type.upper()
    if import_type not in REQUIRED_HEADERS:
        return ExcelImportValidationSummary(
            total_rows=0,
            valid_rows_count=0,
            warning_rows_count=0,
            error_rows_count=1,
            can_commit=False,
            message=f"Unsupported import type '{import_type}'. Must be GRN, ISSUE, or WASTE.",
            findings=[RowValidationFinding(row_number=0, status="ERROR", errors=[f"Invalid import type {import_type}"])]
        )

    try:
        workbook = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
        sheet = workbook.active
    except Exception as e:
        return ExcelImportValidationSummary(
            total_rows=0,
            valid_rows_count=0,
            warning_rows_count=0,
            error_rows_count=1,
            can_commit=False,
            message=f"Failed to open Excel workbook: {str(e)}",
            findings=[RowValidationFinding(row_number=0, status="ERROR", errors=["Invalid or corrupt Excel file format."])]
        )

    # 1. Header validation
    rows_iter = sheet.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        return ExcelImportValidationSummary(
            total_rows=0,
            valid_rows_count=0,
            warning_rows_count=0,
            error_rows_count=1,
            can_commit=False,
            message="Excel sheet is completely empty.",
            findings=[RowValidationFinding(row_number=1, status="ERROR", errors=["Empty worksheet."])]
        )

    # Map headers normalized (lowercase, stripped)
    header_map: Dict[str, int] = {}
    for col_idx, val in enumerate(header_row):
        if val is not None:
            clean_col = str(val).strip().lower()
            if clean_col:
                header_map[clean_col] = col_idx

    missing_headers = []
    for expected in REQUIRED_HEADERS[import_type]:
        if expected.strip().lower() not in header_map:
            missing_headers.append(expected)

    if missing_headers:
        return ExcelImportValidationSummary(
            total_rows=0,
            valid_rows_count=0,
            warning_rows_count=0,
            error_rows_count=1,
            can_commit=False,
            message=f"Missing required columns in sheet: {', '.join(missing_headers)}",
            findings=[
                RowValidationFinding(
                    row_number=1,
                    status="ERROR",
                    errors=[f"Sheet missing headers: {', '.join(missing_headers)}"],
                )
            ]
        )

    # 2. Pre-fetch master data caches for speed
    items_by_code = {item.item_code.upper(): item for item in db.execute(select(MaterialItem)).scalars().all()}
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}
    from app.services.validators import normalize_vendor_name
    vendors_by_norm = {v.normalized_name: v for v in db.execute(select(Vendor)).scalars().all()}
    departments_by_code = {d.code.upper(): d for d in db.execute(select(Department)).scalars().all()}
    departments_by_name = {d.name.upper(): d for d in db.execute(select(Department)).scalars().all()}

    findings: List[RowValidationFinding] = []
    # Document grouping tracker for duplicate material item detection within same document:
    # key -> doc_group_key, val -> dict[item_code, list[row_idx]]
    doc_item_rows: Dict[Any, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    row_finding_map: Dict[int, RowValidationFinding] = {}

    # 3. Row iteration
    for row_idx, row in enumerate(rows_iter, start=2):
        # Skip completely empty rows
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        row_errors: List[str] = []
        row_warnings: List[str] = []
        row_data: Dict[str, Any] = {}

        def get_val(col_name: str) -> Optional[Any]:
            idx = header_map.get(col_name.lower())
            if idx is not None and idx < len(row):
                v = row[idx]
                return str(v).strip() if isinstance(v, str) else v
            return None

        # Build raw dict
        for col_name in REQUIRED_HEADERS[import_type]:
            row_data[col_name] = get_val(col_name)

        # Common Line Validations (Item & UOM & Quantity)
        item_code_val = get_val("Item Code")
        uom_val = get_val("UOM")
        qty_val = get_val("Quantity")

        matched_item = None
        matched_uom = None

        if not item_code_val:
            row_errors.append("Item Code is mandatory.")
        else:
            clean_item_code = str(item_code_val).strip().upper()
            matched_item = items_by_code.get(clean_item_code)
            if not matched_item:
                row_errors.append(f"Material item code '{item_code_val}' does not exist in Item Master.")

        if not uom_val:
            row_errors.append("UOM is mandatory.")
        else:
            clean_uom = str(uom_val).strip().upper()
            matched_uom = uoms_by_code.get(clean_uom)
            if not matched_uom:
                row_errors.append(f"UOM '{uom_val}' does not exist in UOM Master.")

        if qty_val is None or str(qty_val).strip() == "":
            row_errors.append("Quantity is mandatory.")
        else:
            qty_dec = parse_excel_decimal(qty_val)
            if qty_dec is None:
                row_errors.append(f"Invalid numeric quantity: '{qty_val}'")
            else:
                qty_res = validate_and_flag_quantity(
                    qty_dec,
                    matched_uom,
                    matched_item.category if matched_item else None,
                    matched_item.name if matched_item else None,
                )
                if not qty_res.is_valid:
                    row_errors.extend(qty_res.errors)
                row_warnings.extend(qty_res.warnings)

        # Import Type Specifics
        doc_group_key: Any = None

        if import_type == "GRN":
            source_type_raw = get_val("Source Type") or "EXTERNAL_VENDOR"
            source_type_val = str(source_type_raw).strip().upper()
            receipt_date_raw = get_val("Receipt Date")
            vendor_name_val = get_val("Vendor Name")
            inv_no_val = get_val("Invoice No")
            inv_date_raw = get_val("Invoice Date")
            rate_val = get_val("Rate Ex GST")
            gst_val = get_val("GST %")

            # Validate Receipt Date
            parsed_receipt_date = parse_excel_date(receipt_date_raw)
            if not parsed_receipt_date:
                row_errors.append("Receipt Date is mandatory and must be a valid date (YYYY-MM-DD or DD/MM/YYYY).")

            # Validate Source Type
            try:
                GRNSourceType(source_type_val)
            except ValueError:
                row_errors.append(
                    f"Invalid Source Type '{source_type_raw}'. Allowed: {[e.value for e in GRNSourceType]}."
                )

            # Vendor validations & invoice duplicate check
            if source_type_val == "EXTERNAL_VENDOR":
                if not vendor_name_val:
                    row_errors.append("Vendor Name is mandatory for EXTERNAL_VENDOR.")
                else:
                    norm_v = normalize_vendor_name(str(vendor_name_val))
                    v_obj = vendors_by_norm.get(norm_v)
                    if not v_obj:
                        row_errors.append(f"Vendor '{vendor_name_val}' not found in Vendor Master.")
                    elif inv_no_val:
                        # Check duplicate invoice in DB
                        parsed_inv_date = parse_excel_date(inv_date_raw)
                        dup_check = check_grn_invoice_duplicate(
                            db, v_obj.id, str(inv_no_val), parsed_inv_date
                        )
                        if dup_check.has_conflict:
                            row_warnings.append(dup_check.message)

            # Rate and GST validation
            dec_rate = parse_excel_decimal(rate_val) if rate_val not in (None, "") else None
            if rate_val not in (None, "") and dec_rate is None:
                row_errors.append(f"Invalid numeric value '{rate_val}' for Rate Ex GST.")

            dec_gst = parse_excel_decimal(gst_val) if gst_val not in (None, "") else None
            if gst_val not in (None, "") and dec_gst is None:
                row_errors.append(f"Invalid numeric value '{gst_val}' for GST %.")

            if dec_rate is not None or dec_gst is not None or source_type_val == "EXTERNAL_VENDOR":
                rate_res = validate_rate_and_gst(
                    source_type_val,
                    matched_item.category if matched_item else None,
                    dec_rate,
                    dec_gst,
                )
                if not rate_res.is_valid:
                    row_errors.extend(rate_res.errors)
                row_warnings.extend(rate_res.warnings)

            # Document group key
            doc_group_key = (
                str(parsed_receipt_date) if parsed_receipt_date else str(receipt_date_raw),
                source_type_val,
                normalize_vendor_name(str(vendor_name_val)) if vendor_name_val else "",
                str(inv_no_val).strip().upper() if inv_no_val else "",
            )

        elif import_type == "ISSUE":
            issue_date_raw = get_val("Issue Date")
            issuing_dept_val = get_val("Issuing Dept")
            receiving_dept_val = get_val("Receiving Dept")
            heat_ref_val = get_val("Heat Ref No")

            parsed_issue_date = parse_excel_date(issue_date_raw)
            if not parsed_issue_date:
                row_errors.append("Issue Date is mandatory and must be a valid date (YYYY-MM-DD or DD/MM/YYYY).")

            iss_dept = None
            if not issuing_dept_val:
                row_errors.append("Issuing Dept is mandatory.")
            else:
                clean_iss = str(issuing_dept_val).strip().upper()
                iss_dept = departments_by_code.get(clean_iss) or departments_by_name.get(clean_iss)
                if not iss_dept:
                    row_errors.append(f"Issuing Department '{issuing_dept_val}' not found in Department Master.")

            rec_dept = None
            if not receiving_dept_val:
                row_errors.append("Receiving Dept is mandatory.")
            else:
                clean_rec = str(receiving_dept_val).strip().upper()
                rec_dept = departments_by_code.get(clean_rec) or departments_by_name.get(clean_rec)
                if not rec_dept:
                    row_errors.append(f"Receiving Department '{receiving_dept_val}' not found in Department Master.")

            doc_group_key = (
                str(parsed_issue_date) if parsed_issue_date else str(issue_date_raw),
                iss_dept.code if iss_dept else str(issuing_dept_val),
                rec_dept.code if rec_dept else str(receiving_dept_val),
                str(heat_ref_val).strip().upper() if heat_ref_val else "",
            )

        elif import_type == "WASTE":
            disp_date_raw = get_val("Disposition Date")
            source_dept_val = get_val("Source Dept")
            waste_type_val = get_val("Waste Type")
            disp_type_val = get_val("Disposition Type")

            parsed_disp_date = parse_excel_date(disp_date_raw)
            if not parsed_disp_date:
                row_errors.append("Disposition Date is mandatory and must be a valid date (YYYY-MM-DD or DD/MM/YYYY).")

            src_dept = None
            if not source_dept_val:
                row_errors.append("Source Dept is mandatory.")
            else:
                clean_src = str(source_dept_val).strip().upper()
                src_dept = departments_by_code.get(clean_src) or departments_by_name.get(clean_src)
                if not src_dept:
                    row_errors.append(f"Source Department '{source_dept_val}' not found in Department Master.")

            try:
                WasteType(str(waste_type_val).strip().upper())
            except (ValueError, TypeError):
                row_errors.append(f"Invalid Waste Type '{waste_type_val}'. Allowed: {[e.value for e in WasteType]}.")

            try:
                DispositionType(str(disp_type_val).strip().upper())
            except (ValueError, TypeError):
                row_errors.append(f"Invalid Disposition Type '{disp_type_val}'. Allowed: {[e.value for e in DispositionType]}.")

            doc_group_key = (
                str(parsed_disp_date) if parsed_disp_date else str(disp_date_raw),
                str(waste_type_val).strip().upper() if waste_type_val else "",
                str(disp_type_val).strip().upper() if disp_type_val else "",
                src_dept.code if src_dept else str(source_dept_val),
            )

        # Track item rows within document group for duplicate item warnings
        if item_code_val and doc_group_key:
            doc_item_rows[doc_group_key][str(item_code_val).strip().upper()].append(row_idx)

        finding = RowValidationFinding(
            row_number=row_idx,
            status="ERROR" if row_errors else ("WARNING" if row_warnings else "VALID"),
            errors=row_errors,
            warnings=row_warnings,
            raw_data=row_data,
        )
        findings.append(finding)
        row_finding_map[row_idx] = finding

    # 4. Attach intra-document duplicate line warnings to matching row findings
    for doc_key, items_dict in doc_item_rows.items():
        for item_code, row_numbers in items_dict.items():
            if len(row_numbers) > 1:
                warn_msg = f"Duplicate material line warning: Material '{item_code}' appears on multiple rows (rows {', '.join(str(r) for r in row_numbers)})."
                for r_num in row_numbers:
                    fnd = row_finding_map.get(r_num)
                    if fnd and warn_msg not in fnd.warnings:
                        fnd.warnings.append(warn_msg)
                        if fnd.status == "VALID":
                            fnd.status = "WARNING"

    # 5. Compute summary counts
    valid_count = sum(1 for f in findings if f.status == "VALID")
    warning_count = sum(1 for f in findings if f.status == "WARNING")
    error_count = sum(1 for f in findings if f.status == "ERROR")
    total_rows = len(findings)
    can_commit = (error_count == 0 and total_rows > 0)

    message = (
        f"Validation passed: {valid_count} valid, {warning_count} warnings, 0 errors. Ready for atomic commit."
        if can_commit
        else f"Validation failed: {error_count} row(s) contain blocking errors. Fix errors before committing."
    )

    return ExcelImportValidationSummary(
        total_rows=total_rows,
        valid_rows_count=valid_count,
        warning_rows_count=warning_count,
        error_rows_count=error_count,
        can_commit=can_commit,
        message=message,
        findings=findings,
    )


def commit_excel_import(
    request: ExcelImportCommitRequest,
    db: Session,
) -> Dict[str, Any]:
    """
    Executes atomic commit of validated rows inside a single database transaction.
    Re-validates rows before creation. If ANY row fails or violates constraints,
    the entire transaction rolls back cleanly with zero partial writes.
    """
    if not request.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot commit an empty import batch.",
        )

    import_type = request.import_type.upper()
    if import_type not in REQUIRED_HEADERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported import type '{import_type}'. Must be GRN, ISSUE, or WASTE.",
        )

    created_records = []
    collected_warnings = []

    # Fast cache
    items_by_code = {item.item_code.upper(): item for item in db.execute(select(MaterialItem)).scalars().all()}
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}
    from app.services.validators import normalize_vendor_name
    vendors_by_norm = {v.normalized_name: v for v in db.execute(select(Vendor)).scalars().all()}
    departments_by_code = {d.code.upper(): d for d in db.execute(select(Department)).scalars().all()}
    departments_by_name = {d.name.upper(): d for d in db.execute(select(Department)).scalars().all()}

    # 1. Pre-validate all rows to ensure zero invalid rows before any creation
    for idx, r in enumerate(request.rows, start=1):
        item_code = str(r.get("Item Code") or "").strip().upper()
        if not item_code or item_code not in items_by_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {idx}: Material Item Code '{item_code}' is missing or invalid.",
            )
        uom_code = str(r.get("UOM") or "").strip().upper()
        if not uom_code or uom_code not in uoms_by_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {idx}: UOM '{uom_code}' is missing or invalid.",
            )
        qty = parse_excel_decimal(r.get("Quantity"))
        if qty is None or qty <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {idx}: Quantity '{r.get('Quantity')}' is missing, non-numeric, or non-positive.",
            )

    try:
        created_headers = []

        if import_type == "GRN":
            # Group rows by (Receipt Date, Source Type, Vendor Name, Invoice No, Invoice Date)
            grouped: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                r_date = parse_excel_date(r.get("Receipt Date")) or date.today()
                s_type = str(r.get("Source Type") or "EXTERNAL_VENDOR").strip().upper()
                v_name = str(r.get("Vendor Name") or "").strip()
                inv_no = str(r.get("Invoice No") or "").strip()
                inv_date = parse_excel_date(r.get("Invoice Date"))
                key = (r_date, s_type, v_name, inv_no, inv_date)
                grouped.setdefault(key, []).append(r)

            for key, rows in grouped.items():
                receipt_date, source_type, v_name, inv_no, inv_date = key
                vendor_id = None
                if v_name:
                    norm = normalize_vendor_name(v_name)
                    v_obj = vendors_by_norm.get(norm)
                    if v_obj:
                        vendor_id = v_obj.id

                lines: List[GRNLineItemCreate] = []
                for line_idx, row in enumerate(rows, start=1):
                    item = items_by_code[str(row["Item Code"]).strip().upper()]
                    uom = uoms_by_code[str(row["UOM"]).strip().upper()]
                    qty = parse_excel_decimal(row["Quantity"]) or Decimal("0")
                    rate = parse_excel_decimal(row.get("Rate Ex GST")) if row.get("Rate Ex GST") not in (None, "") else None
                    gst = parse_excel_decimal(row.get("GST %")) if row.get("GST %") not in (None, "") else None

                    lines.append(
                        GRNLineItemCreate(
                            line_number=line_idx,
                            material_item_id=item.id,
                            uom_id=uom.id,
                            quantity=qty,
                            rate_ex_gst=rate,
                            gst_percent=gst,
                            remarks="Imported from Excel batch row",
                        )
                    )

                grn_in = GRNCreate(
                    receipt_date=receipt_date,
                    source_type=GRNSourceType(source_type),
                    vendor_id=vendor_id,
                    vendor_invoice_no=inv_no or None,
                    invoice_date=inv_date,
                    notes=f"Excel bulk import by {request.created_by}",
                    lines=lines,
                )
                header, warnings = create_grn(db, grn_in, request.created_by, auto_commit=False)
                created_headers.append(header)
                created_records.append(header.grn_number)
                collected_warnings.extend(warnings)

        elif import_type == "ISSUE":
            # Group rows by (Issue Date, Issuing Dept, Receiving Dept, Heat Ref No)
            grouped_issue: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                iss_date = parse_excel_date(r.get("Issue Date")) or date.today()
                iss_dept_str = str(r.get("Issuing Dept") or "").strip().upper()
                rec_dept_str = str(r.get("Receiving Dept") or "").strip().upper()
                heat_ref = str(r.get("Heat Ref No") or "").strip()
                key = (iss_date, iss_dept_str, rec_dept_str, heat_ref)
                grouped_issue.setdefault(key, []).append(r)

            for key, rows in grouped_issue.items():
                issue_date, iss_dept_str, rec_dept_str, heat_ref = key
                iss_dept = departments_by_code.get(iss_dept_str) or departments_by_name.get(iss_dept_str)
                rec_dept = departments_by_code.get(rec_dept_str) or departments_by_name.get(rec_dept_str)
                if not iss_dept or not rec_dept:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Department reference not found: issuing='{iss_dept_str}', receiving='{rec_dept_str}'",
                    )

                lines: List[MaterialIssueLineItemCreate] = []
                for line_idx, row in enumerate(rows, start=1):
                    item = items_by_code[str(row["Item Code"]).strip().upper()]
                    uom = uoms_by_code[str(row["UOM"]).strip().upper()]
                    qty = parse_excel_decimal(row["Quantity"]) or Decimal("0")

                    lines.append(
                        MaterialIssueLineItemCreate(
                            line_number=line_idx,
                            material_item_id=item.id,
                            uom_id=uom.id,
                            quantity=qty,
                            remarks=str(row.get("Remarks") or ""),
                        )
                    )

                iss_in = MaterialIssueCreate(
                    issue_date=issue_date,
                    issuing_department_id=iss_dept.id,
                    receiving_department_id=rec_dept.id,
                    heat_reference_number=heat_ref or None,
                    notes=f"Excel bulk import by {request.created_by}",
                    lines=lines,
                )
                header, warnings = create_material_issue(db, iss_in, request.created_by, auto_commit=False)
                created_headers.append(header)
                created_records.append(header.issue_slip_number)
                collected_warnings.extend(warnings)

        elif import_type == "WASTE":
            # Group rows by (Disposition Date, Waste Type, Disposition Type, Source Dept)
            grouped_waste: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                disp_date = parse_excel_date(r.get("Disposition Date")) or date.today()
                w_type = str(r.get("Waste Type") or "").strip().upper()
                d_type = str(r.get("Disposition Type") or "").strip().upper()
                src_dept_str = str(r.get("Source Dept") or "").strip().upper()
                key = (disp_date, w_type, d_type, src_dept_str)
                grouped_waste.setdefault(key, []).append(r)

            for key, rows in grouped_waste.items():
                disp_date, w_type, d_type, src_dept_str = key
                src_dept = departments_by_code.get(src_dept_str) or departments_by_name.get(src_dept_str)
                if not src_dept:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Source Department '{src_dept_str}' not found.",
                    )

                lines: List[WasteDispositionLineItemCreate] = []
                for line_idx, row in enumerate(rows, start=1):
                    item = items_by_code[str(row["Item Code"]).strip().upper()]
                    uom = uoms_by_code[str(row["UOM"]).strip().upper()]
                    qty = parse_excel_decimal(row["Quantity"]) or Decimal("0")

                    lines.append(
                        WasteDispositionLineItemCreate(
                            line_number=line_idx,
                            material_item_id=item.id,
                            uom_id=uom.id,
                            quantity=qty,
                            reason=str(row.get("Reason") or "Bulk Excel Entry"),
                        )
                    )

                wst_in = WasteDispositionCreate(
                    disposition_date=disp_date,
                    waste_type=WasteType(w_type),
                    disposition_type=DispositionType(d_type),
                    source_department_id=src_dept.id,
                    notes=f"Excel bulk import by {request.created_by}",
                    lines=lines,
                )
                header, warnings = create_waste_disposition(db, wst_in, request.created_by, auto_commit=False)
                created_headers.append(header)
                created_records.append(header.waste_number)
                collected_warnings.extend(warnings)

        # Single atomic commit for entire batch
        db.commit()
        for h in created_headers:
            db.refresh(h)

        return {
            "success": True,
            "created_count": len(created_records),
            "created_documents": created_records,
            "warnings": collected_warnings,
            "message": f"Successfully created {len(created_records)} documents from Excel import.",
        }
    except Exception as e:
        db.rollback()
        raise e


def generate_template_excel(import_type: str) -> bytes:
    """Generates a blank Excel template with correct headers and column widths."""
    import_type = import_type.upper()
    headers = REQUIRED_HEADERS.get(import_type, [])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{import_type}_Template"

    # Header styling
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 18

    # Output buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
