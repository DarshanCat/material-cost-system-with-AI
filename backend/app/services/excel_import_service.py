"""
Excel Import Validation Engine.
Performs header validation, type coercion, master data reference lookup,
duplicate checks, and atomic preview / commit for bulk material entries.
"""

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional
import openpyxl
from sqlalchemy.orm import Session
from sqlalchemy import select

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


def parse_and_validate_excel(
    file_bytes: bytes,
    import_type: str,
    db: Session,
) -> ExcelImportValidationSummary:
    """
    Parses an uploaded Excel file, validates headers, and validates each data row.
    Guarantees atomic summary: can_commit is True ONLY when error_rows_count == 0.
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

    # Map headers normalized
    header_map: Dict[str, int] = {}
    for col_idx, val in enumerate(header_row):
        if val is not None:
            clean_col = str(val).strip().lower()
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
    vendors_by_norm = {v.normalized_name: v for v in db.execute(select(Vendor)).scalars().all()}
    departments_by_code = {d.code.upper(): d for d in db.execute(select(Department)).scalars().all()}
    departments_by_name = {d.name.upper(): d for d in db.execute(select(Department)).scalars().all()}

    findings: List[RowValidationFinding] = []
    valid_count = 0
    warning_count = 0
    error_count = 0

    # Row iteration
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
            matched_item = items_by_code.get(str(item_code_val).strip().upper())
            if not matched_item:
                row_errors.append(f"Material item code '{item_code_val}' does not exist in Item Master.")

        if not uom_val:
            row_errors.append("UOM is mandatory.")
        else:
            matched_uom = uoms_by_code.get(str(uom_val).strip().upper())
            if not matched_uom:
                row_errors.append(f"UOM '{uom_val}' does not exist in UOM Master.")

        if qty_val is None:
            row_errors.append("Quantity is mandatory.")
        else:
            qty_res = validate_and_flag_quantity(
                qty_val,
                matched_uom,
                matched_item.category if matched_item else None,
                matched_item.name if matched_item else None,
            )
            if not qty_res.is_valid:
                row_errors.extend(qty_res.errors)
            row_warnings.extend(qty_res.warnings)

        # Import Type Specifics
        if import_type == "GRN":
            source_type_val = (get_val("Source Type") or "EXTERNAL_VENDOR").upper()
            receipt_date_val = get_val("Receipt Date")
            vendor_name_val = get_val("Vendor Name")
            rate_val = get_val("Rate Ex GST")
            gst_val = get_val("GST %")

            if not receipt_date_val:
                row_errors.append("Receipt Date is mandatory.")

            if source_type_val == "EXTERNAL_VENDOR":
                if not vendor_name_val:
                    row_errors.append("Vendor Name is mandatory for EXTERNAL_VENDOR.")
                else:
                    from app.services.validators import normalize_vendor_name
                    norm_v = normalize_vendor_name(str(vendor_name_val))
                    if norm_v not in vendors_by_norm:
                        row_errors.append(f"Vendor '{vendor_name_val}' not found in Vendor Master.")

            # Rate validation
            dec_rate = Decimal(str(rate_val)) if rate_val not in (None, "") else None
            dec_gst = Decimal(str(gst_val)) if gst_val not in (None, "") else None
            rate_res = validate_rate_and_gst(
                source_type_val,
                matched_item.category if matched_item else None,
                dec_rate,
                dec_gst,
            )
            if not rate_res.is_valid:
                row_errors.extend(rate_res.errors)
            row_warnings.extend(rate_res.warnings)

        elif import_type == "ISSUE":
            issue_date_val = get_val("Issue Date")
            issuing_dept_val = get_val("Issuing Dept")
            receiving_dept_val = get_val("Receiving Dept")

            if not issue_date_val:
                row_errors.append("Issue Date is mandatory.")
            
            if not issuing_dept_val:
                row_errors.append("Issuing Dept is mandatory.")
            elif (
                str(issuing_dept_val).upper() not in departments_by_code
                and str(issuing_dept_val).upper() not in departments_by_name
            ):
                row_errors.append(f"Issuing Department '{issuing_dept_val}' not found.")

            if not receiving_dept_val:
                row_errors.append("Receiving Dept is mandatory.")
            elif (
                str(receiving_dept_val).upper() not in departments_by_code
                and str(receiving_dept_val).upper() not in departments_by_name
            ):
                row_errors.append(f"Receiving Department '{receiving_dept_val}' not found.")

        elif import_type == "WASTE":
            disp_date_val = get_val("Disposition Date")
            source_dept_val = get_val("Source Dept")
            waste_type_val = get_val("Waste Type")
            disp_type_val = get_val("Disposition Type")

            if not disp_date_val:
                row_errors.append("Disposition Date is mandatory.")

            if not source_dept_val:
                row_errors.append("Source Dept is mandatory.")
            elif (
                str(source_dept_val).upper() not in departments_by_code
                and str(source_dept_val).upper() not in departments_by_name
            ):
                row_errors.append(f"Source Department '{source_dept_val}' not found.")

            try:
                WasteType(str(waste_type_val).upper())
            except (ValueError, TypeError):
                row_errors.append(f"Invalid Waste Type '{waste_type_val}'. Allowed: {[e.value for e in WasteType]}.")

            try:
                DispositionType(str(disp_type_val).upper())
            except (ValueError, TypeError):
                row_errors.append(f"Invalid Disposition Type '{disp_type_val}'. Allowed: {[e.value for e in DispositionType]}.")

        # Status determination
        if row_errors:
            status = "ERROR"
            error_count += 1
        elif row_warnings:
            status = "WARNING"
            warning_count += 1
        else:
            status = "VALID"
            valid_count += 1

        findings.append(
            RowValidationFinding(
                row_number=row_idx,
                status=status,
                errors=row_errors,
                warnings=row_warnings,
                raw_data=row_data,
            )
        )

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
    If ANY row fails or violates constraints, the entire transaction rolls back.
    """
    import_type = request.import_type.upper()
    created_records = []

    # Fast cache
    items_by_code = {item.item_code.upper(): item for item in db.execute(select(MaterialItem)).scalars().all()}
    uoms_by_code = {u.code.upper(): u for u in db.execute(select(UOM)).scalars().all()}
    from app.services.validators import normalize_vendor_name
    vendors_by_norm = {v.normalized_name: v for v in db.execute(select(Vendor)).scalars().all()}
    departments_by_code = {d.code.upper(): d for d in db.execute(select(Department)).scalars().all()}
    departments_by_name = {d.name.upper(): d for d in db.execute(select(Department)).scalars().all()}

    try:
        if import_type == "GRN":
            # Group rows by (Receipt Date, Source Type, Vendor Name, Invoice No) to construct headers
            grouped: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                key = (
                    str(r.get("Receipt Date")),
                    str(r.get("Source Type") or "EXTERNAL_VENDOR").upper(),
                    str(r.get("Vendor Name") or "").strip(),
                    str(r.get("Invoice No") or "").strip(),
                    str(r.get("Invoice Date") or "").strip(),
                )
                grouped.setdefault(key, []).append(r)

            for key, rows in grouped.items():
                r_date_str, source_type, v_name, inv_no, inv_date_str = key
                receipt_date = (
                    datetime.strptime(r_date_str[:10], "%Y-%m-%d").date()
                    if "-" in r_date_str
                    else date.today()
                )
                inv_date = (
                    datetime.strptime(inv_date_str[:10], "%Y-%m-%d").date()
                    if inv_date_str and "-" in inv_date_str
                    else None
                )

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
                    qty = Decimal(str(row["Quantity"]))
                    rate = Decimal(str(row["Rate Ex GST"])) if row.get("Rate Ex GST") not in (None, "") else None
                    gst = Decimal(str(row["GST %"])) if row.get("GST %") not in (None, "") else None

                    lines.append(
                        GRNLineItemCreate(
                            line_number=line_idx,
                            material_item_id=item.id,
                            uom_id=uom.id,
                            quantity=qty,
                            rate_ex_gst=rate,
                            gst_percent=gst,
                            remarks=f"Imported from Excel batch row",
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
                header, _ = create_grn(db, grn_in, request.created_by)
                created_records.append(header.grn_number)

        elif import_type == "ISSUE":
            # Group rows by (Issue Date, Issuing Dept, Receiving Dept, Heat Ref No)
            grouped_issue: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                key = (
                    str(r.get("Issue Date")),
                    str(r.get("Issuing Dept")).strip().upper(),
                    str(r.get("Receiving Dept")).strip().upper(),
                    str(r.get("Heat Ref No") or "").strip(),
                )
                grouped_issue.setdefault(key, []).append(r)

            for key, rows in grouped_issue.items():
                iss_date_str, iss_dept_str, rec_dept_str, heat_ref = key
                issue_date = (
                    datetime.strptime(iss_date_str[:10], "%Y-%m-%d").date()
                    if "-" in iss_date_str
                    else date.today()
                )
                iss_dept = departments_by_code.get(iss_dept_str) or departments_by_name.get(iss_dept_str)
                rec_dept = departments_by_code.get(rec_dept_str) or departments_by_name.get(rec_dept_str)

                lines: List[MaterialIssueLineItemCreate] = []
                for line_idx, row in enumerate(rows, start=1):
                    item = items_by_code[str(row["Item Code"]).strip().upper()]
                    uom = uoms_by_code[str(row["UOM"]).strip().upper()]
                    qty = Decimal(str(row["Quantity"]))

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
                header, _ = create_material_issue(db, iss_in, request.created_by)
                created_records.append(header.issue_slip_number)

        elif import_type == "WASTE":
            # Group rows by (Disposition Date, Waste Type, Disposition Type, Source Dept)
            grouped_waste: Dict[tuple, List[Dict[str, Any]]] = {}
            for r in request.rows:
                key = (
                    str(r.get("Disposition Date")),
                    str(r.get("Waste Type")).strip().upper(),
                    str(r.get("Disposition Type")).strip().upper(),
                    str(r.get("Source Dept")).strip().upper(),
                )
                grouped_waste.setdefault(key, []).append(r)

            for key, rows in grouped_waste.items():
                disp_date_str, w_type, d_type, src_dept_str = key
                disp_date = (
                    datetime.strptime(disp_date_str[:10], "%Y-%m-%d").date()
                    if "-" in disp_date_str
                    else date.today()
                )
                src_dept = departments_by_code.get(src_dept_str) or departments_by_name.get(src_dept_str)

                lines: List[WasteDispositionLineItemCreate] = []
                for line_idx, row in enumerate(rows, start=1):
                    item = items_by_code[str(row["Item Code"]).strip().upper()]
                    uom = uoms_by_code[str(row["UOM"]).strip().upper()]
                    qty = Decimal(str(row["Quantity"]))

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
                header, _ = create_waste_disposition(db, wst_in, request.created_by)
                created_records.append(header.waste_number)

        return {
            "success": True,
            "created_count": len(created_records),
            "created_documents": created_records,
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
