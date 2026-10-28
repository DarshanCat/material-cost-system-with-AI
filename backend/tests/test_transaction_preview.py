"""
Automated tests for Transaction Import Preview Engine (Read-Only Source Validation).
Verifies:
1. Pure read-only execution (0 DB writes, 0 draft documents, 0 ledger entries).
2. Mandatory field validation (dates, item codes, quantities, document refs).
3. 381 Ledger-only codes held for formal Item Code Generator approval.
4. 'NOT FOUND' codes held for approval.
5. UOM compatibility checks against approved item master.
6. Furnace raw-material charge segregation from general departmental issues.
7. Intra-workbook and cross-workbook duplicate detection (e.g. Waste Disposition).
8. Multi-line vendor invoice analysis (Mahalakshmi Packing Works invoice 664).
"""

import io
from datetime import date
from decimal import Decimal
import openpyxl
import pytest
from sqlalchemy.orm import Session

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.ledger import StockLedgerEntry
from app.models.grn import GRNHeader
from app.models.issue import MaterialIssueHeader
from app.models.waste import WasteDispositionHeader
from app.schemas.transaction_preview import (
    PreviewRowStatus,
    PreviewTransactionType,
    TransactionImportPreviewSummary,
)
from app.services.transaction_preview_service import (
    TransactionImportPreviewEngine,
    parse_date_value,
    parse_decimal_value,
)


def _build_test_workbook(
    grn_rows: list = None,
    issue_rows: list = None,
    waste_rows: list = None,
) -> bytes:
    """Creates a memory-only openpyxl workbook mimicking VSPL daily material entry format."""
    wb = openpyxl.Workbook()
    # Sheet 1: Read Me
    ws_readme = wb.active
    ws_readme.title = "Read Me"
    ws_readme.append(["Information sheet"])

    # Sheet: 3. Receipt GRN
    ws_grn = wb.create_sheet(title="3. Receipt GRN")
    ws_grn.append([
        "Receipt Date", "GRN No", "Vendor Name", "Supplier Invoice No", "PO No",
        "Work order number", "Item Description", "Item Code", "Item Category",
        "UOM", "Quantity Received", "Remarks", "Received By"
    ])
    if grn_rows:
        for r in grn_rows:
            ws_grn.append(r)

    # Sheet: 4. Issue
    ws_issue = wb.create_sheet(title="4. Issue")
    ws_issue.append([
        "Date", "Issue Slip No", "Item Description", "Item Code", "UOM",
        "Quantity Issued", "Consuming Section", "Unit/Location",
        "Product Family / Work Order", "Issued To (Dept)", "Issued By", "Remarks"
    ])
    if issue_rows:
        for r in issue_rows:
            ws_issue.append(r)

    # Sheet: 5. Waste Disposition
    ws_waste = wb.create_sheet(title="5. Waste Disposition")
    ws_waste.append([
        "Date", "Disposal Note No", "Item Description", "Item Code", "UOM",
        "Quantity", "Waste Type", "Reason", "Section / Cost Centre",
        "Disposed To", "Approved By", "Remarks"
    ])
    if waste_rows:
        for r in waste_rows:
            ws_waste.append(r)

    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def test_transaction_preview_strictly_read_only(db_session: Session):
    """Verifies that running the preview engine performs ZERO mutations to the database."""
    # Count rows before
    grn_before = db_session.query(GRNHeader).count()
    iss_before = db_session.query(MaterialIssueHeader).count()
    wst_before = db_session.query(WasteDispositionHeader).count()
    ledg_before = db_session.query(StockLedgerEntry).count()

    grn_data = [
        ["2026-10-12", "101", "Vendor A", "INV-001", "PO-01", "", "Pig Iron", "FDY-RM-001", "RM", "Kg", 500.0]
    ]
    issue_data = [
        ["2026-10-12", "102607-3857", "Pig Iron", "FDY-RM-001", "Kg", 200.0, "Foundry - Melting/Pouring", "Peenya"]
    ]
    wb_bytes = _build_test_workbook(grn_rows=grn_data, issue_rows=issue_data)

    engine = TransactionImportPreviewEngine(db=db_session)
    # Mock approved item
    engine.approved_items["FDY-RM-001"] = {"name": "Pig Iron", "category": "Raw Material", "uom": "Kg"}

    summary = engine.validate_workbooks([("test_day1.xlsx", wb_bytes)])

    assert summary.is_read_only is True
    assert summary.total_rows_scanned == 2

    # Verify zero database mutations
    assert db_session.query(GRNHeader).count() == grn_before
    assert db_session.query(MaterialIssueHeader).count() == iss_before
    assert db_session.query(WasteDispositionHeader).count() == wst_before
    assert db_session.query(StockLedgerEntry).count() == ledg_before
    assert len(db_session.new) == 0
    assert len(db_session.dirty) == 0
    assert len(db_session.deleted) == 0


def test_furnace_charge_segregation():
    """Verifies that furnace heat charges are segregated from general store issues."""
    issue_data = [
        # Furnace Charge (Melting/Pouring + Heat Number)
        ["2026-10-12", "102607-3857", "CRC Scrap", "FDY-RM-007", "Kg", 250.0, "Foundry - Melting/Pouring", "Peenya"],
        # General Issue (Maintenance Dept)
        ["2026-10-12", "ISS-1001", "Bearing 32212", "MNT-BR-001", "Nos", 2.0, "Machine Shop", "Peenya"],
    ]
    wb_bytes = _build_test_workbook(issue_rows=issue_data)

    engine = TransactionImportPreviewEngine()
    engine.approved_items["FDY-RM-007"] = {"name": "CRC Scrap", "category": "Raw Material", "uom": "Kg"}
    engine.approved_items["MNT-BR-001"] = {"name": "Bearing 32212", "category": "Maintenance", "uom": "Nos"}

    summary = engine.validate_workbooks([("test_furnace.xlsx", wb_bytes)])

    assert summary.furnace_charge_count == 1
    assert summary.general_issue_count == 1

    furnace_finding = [f for f in summary.findings if f.transaction_type == PreviewTransactionType.FURNACE_CHARGE][0]
    assert furnace_finding.is_furnace_charge is True
    assert "Heat Log & Reconciliation" in furnace_finding.reason

    general_finding = [f for f in summary.findings if f.transaction_type == PreviewTransactionType.GENERAL_ISSUE][0]
    assert general_finding.is_furnace_charge is False


def test_unapproved_and_not_found_codes_held():
    """Verifies that 381 ledger-only codes and 'NOT FOUND' codes are held for approval, not auto-approved."""
    grn_data = [
        ["2026-10-13", "102", "Vendor B", "INV-002", "PO-02", "", "Old Foundry Tool", "FDY-TL-999", "Tools", "Nos", 5.0],
        ["2026-10-13", "103", "Vendor C", "INV-003", "PO-03", "", "Unknown Special Box", "NOT FOUND", "", "Nos", 10.0],
    ]
    wb_bytes = _build_test_workbook(grn_rows=grn_data)

    engine = TransactionImportPreviewEngine()
    engine.ledger_only_codes.add("FDY-TL-999")

    summary = engine.validate_workbooks([("test_held.xlsx", wb_bytes)])

    assert summary.held_for_approval_count == 2
    f_ledger = [f for f in summary.findings if f.item_code == "FDY-TL-999"][0]
    assert f_ledger.status == PreviewRowStatus.HELD_FOR_APPROVAL
    assert "381 unapproved ledger-only" in f_ledger.reason

    f_not_found = [f for f in summary.findings if f.item_code == "NOT FOUND"][0]
    assert f_not_found.status == PreviewRowStatus.HELD_FOR_APPROVAL
    assert "Item Code marked 'NOT FOUND'" in f_not_found.reason


def test_uom_mismatch_flagged_as_conflicting():
    """Verifies that UOM mismatches against approved master base UOM are flagged."""
    issue_data = [
        # In master UOM is Kg, but sheet recorded Nos
        ["2026-10-14", "ISS-1002", "Grinding Wheel 5 Inch", "FDY-CN-014", "Nos", 5.0, "Stores", "Peenya"]
    ]
    wb_bytes = _build_test_workbook(issue_rows=issue_data)

    engine = TransactionImportPreviewEngine()
    engine.approved_items["FDY-CN-014"] = {"name": "Grinding Wheel", "category": "Consumables", "uom": "Kg"}

    summary = engine.validate_workbooks([("test_uom.xlsx", wb_bytes)])

    assert summary.conflicting_count == 1
    f = summary.findings[0]
    assert f.status == PreviewRowStatus.CONFLICTING
    assert "UOM mismatch" in f.reason
    assert "source receipt UOM 'Nos'" in f.reason or "issue UOM 'Nos'" in f.reason


def test_duplicate_waste_detection_across_workbooks():
    """Verifies that duplicate waste records across workbooks (e.g. 16-Oct duplicating 14-Oct) are caught."""
    waste_day1 = [
        ["2026-10-13", "717", "Bearing 32212", "MNT-BR-001", "Nos", 2.0, "Scrap Sale", "USED/WARMOUT"]
    ]
    waste_day2 = [
        ["2026-10-13", "717", "Bearing 32212", "MNT-BR-001", "Nos", 2.0, "Scrap Sale", "USED/WARMOUT"]
    ]
    wb1 = _build_test_workbook(waste_rows=waste_day1)
    wb2 = _build_test_workbook(waste_rows=waste_day2)

    engine = TransactionImportPreviewEngine()
    engine.approved_items["MNT-BR-001"] = {"name": "Bearing 32212", "category": "Maintenance", "uom": "Nos"}

    summary = engine.validate_workbooks([("day1.xlsx", wb1), ("day2.xlsx", wb2)])

    assert summary.duplicate_count == 1
    dup_finding = [f for f in summary.findings if f.status == PreviewRowStatus.DUPLICATE][0]
    assert dup_finding.source_file == "day2.xlsx"
    assert "Duplicate waste disposition record" in dup_finding.reason


def test_mahalakshmi_packing_works_multiline_invoice():
    """
    Verifies that Mahalakshmi Packing Works invoice 664 rows with different descriptions
    are analyzed as multi-line box sizes, not duplicate receipts.
    """
    grn_data = [
        ["2026-10-14", "141", "Mahalakshmi Packing Works", "664", "151026-02", "", "Wooden Packing Box 750x440x190", "NOT FOUND", "", "Nos", 5.0],
        ["2026-10-14", "141", "Mahalakshmi Packing Works", "664", "151026-02", "", "Wooden Packing Box 750x750x230", "NOT FOUND", "", "Nos", 5.0],
    ]
    wb_bytes = _build_test_workbook(grn_rows=grn_data)

    engine = TransactionImportPreviewEngine()
    summary = engine.validate_workbooks([("test_mahalakshmi.xlsx", wb_bytes)])

    assert summary.receipt_grn_count == 2
    assert summary.duplicate_count == 0  # NOT marked as duplicate
    assert summary.held_for_approval_count == 2
    for f in summary.findings:
        assert f.status == PreviewRowStatus.HELD_FOR_APPROVAL
        assert "box_dimension_analysis" in f.details
        assert "Distinct packing dimension" in f.details["box_dimension_analysis"]


def test_blank_issue_slips_and_zero_quantities():
    """Verifies that blank issue slip numbers and non-positive quantities are flagged."""
    issue_data = [
        # Blank issue slip
        ["2026-10-14", None, "Borings-450/10", "FDY-RM-002", "Kg", 50.0, "Foundry", "Peenya"],
        # Zero quantity
        ["2026-10-14", "ISS-1005", "Copper", "FDY-RM-006", "Kg", 0.0, "Foundry", "Peenya"],
        # Blank item code
        ["2026-10-14", "ISS-1006", "Unknown Wire", None, "Kg", 10.0, "Foundry", "Peenya"],
    ]
    wb_bytes = _build_test_workbook(issue_rows=issue_data)

    engine = TransactionImportPreviewEngine()
    engine.approved_items["FDY-RM-002"] = {"name": "Borings-450/10", "category": "RM", "uom": "Kg"}
    engine.approved_items["FDY-RM-006"] = {"name": "Copper", "category": "RM", "uom": "Kg"}

    summary = engine.validate_workbooks([("test_anomalies.xlsx", wb_bytes)])

    # Blank slip -> CONFLICTING
    f_blank_slip = [f for f in summary.findings if f.document_ref is None and f.quantity == Decimal("50")][0]
    assert f_blank_slip.status == PreviewRowStatus.CONFLICTING
    assert "Missing mandatory Issue Slip" in f_blank_slip.reason

    # Zero qty -> CONFLICTING
    f_zero_qty = [f for f in summary.findings if f.quantity == Decimal("0")][0]
    assert f_zero_qty.status == PreviewRowStatus.CONFLICTING
    assert "non-positive" in f_zero_qty.reason

    # Blank item code -> REJECTED
    f_blank_code = [f for f in summary.findings if f.item_code is None][0]
    assert f_blank_code.status == PreviewRowStatus.REJECTED
    assert "Missing mandatory Item Code" in f_blank_code.reason
