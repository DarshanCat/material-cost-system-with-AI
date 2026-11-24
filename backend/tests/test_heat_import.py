from tests.auth_helpers import bearer
"""
Tests for Heat Log Excel Import preview, atomic commit, and direct .xlsx upload.
"""

from decimal import Decimal
import io
import openpyxl
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.heat import HeatHeader
from app.models.ledger import StockLedgerEntry


def make_excel(headers, data_rows, sheet_name="Heat_Log") -> bytes:
    """Helper to generate in-memory Excel workbooks for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in data_rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def test_heat_import_preview_and_atomic_commit(client: TestClient, db_session: Session):
    """Verifies dry-run preview, error detection, and atomic commit of heat log rows."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-020",
        name="Cast Iron Borings",
        department_id=dept.id,
        category="BORING",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    rows_with_error = [
        {
            "heat_number": "102603-4001",
            "heat_date": "2026-10-21",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1200.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "102603-4002",
            "heat_date": "",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "-500.0000",
            "uom_code": "KG",
        }
    ]

    preview_resp = client.post(
        "/api/v1/heats/import/preview",
        json={"rows": rows_with_error},
        headers=bearer("Foundry"),
    )
    assert preview_resp.status_code == 200
    p_data = preview_resp.json()
    assert p_data["can_commit"] is False
    assert p_data["error_rows"] == 1
    assert p_data["valid_rows"] == 1

    commit_fail = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": rows_with_error},
        headers=bearer("Foundry"),
    )
    assert commit_fail.status_code == 400

    valid_rows = [
        {
            "heat_number": "102603-4001",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1200.0000",
            "uom_code": "KG",
            "part_description": "Differential Housing",
            "quantity_produced": "45.0000",
        }
    ]

    commit_resp = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": valid_rows, "source_filename": "Furnace_Logs_Oct21.xlsx"},
        headers=bearer("Foundry"),
    )
    assert commit_resp.status_code == 201
    c_data = commit_resp.json()
    assert c_data["heats_created_count"] == 1
    assert "102603-4001" in c_data["heats_created"]

    heat = db_session.query(HeatHeader).filter_by(heat_number="102603-4001").first()
    assert heat is not None
    assert heat.normalized_heat_number == "H-102603-4001"
    assert len(heat.charge_lines) == 1
    assert heat.charge_lines[0].material_item_id == item.id


def test_heat_import_header_conflict_dates_rejected(client: TestClient, db_session: Session):
    """Verifies that rows belonging to the same heat with conflicting dates are flagged as blocking errors."""
    rows = [
        {
            "heat_number": "102603-5001",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1000.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "H-102603-5001",
            "heat_date": "2026-10-22",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "500.0000",
            "uom_code": "KG",
        },
    ]

    preview_resp = client.post("/api/v1/heats/import/preview", json={"rows": rows}, headers=bearer("Foundry"))
    assert preview_resp.status_code == 200
    p_data = preview_resp.json()
    assert p_data["can_commit"] is False
    assert p_data["error_rows"] == 2
    assert p_data["valid_rows"] == 0

    findings = p_data["findings"]
    assert any("Header conflict for heat 'H-102603-5001'" in err and "heat_date" in err for err in findings[0]["errors"])
    assert any("Header conflict for heat 'H-102603-5001'" in err and "heat_date" in err for err in findings[1]["errors"])

    commit_resp = client.post("/api/v1/heats/import/commit", json={"rows": rows}, headers=bearer("Foundry"))
    assert commit_resp.status_code == 400
    assert db_session.query(HeatHeader).filter_by(heat_number="102603-5001").first() is None
    assert db_session.query(HeatHeader).filter_by(normalized_heat_number="H-102603-5001").first() is None


def test_heat_import_header_conflict_furnace_ids_rejected(client: TestClient, db_session: Session):
    """Verifies that rows belonging to the same heat with conflicting furnace IDs are flagged as blocking errors."""
    rows = [
        {
            "heat_number": "102603-5002",
            "heat_date": "2026-10-21",
            "furnace_id": "FURNACE-1",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "800.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "102603-5002",
            "heat_date": "2026-10-21",
            "furnace_id": "FURNACE-2",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "400.0000",
            "uom_code": "KG",
        },
    ]

    preview_resp = client.post("/api/v1/heats/import/preview", json={"rows": rows}, headers=bearer("Foundry"))
    assert preview_resp.status_code == 200
    p_data = preview_resp.json()
    assert p_data["can_commit"] is False
    assert p_data["error_rows"] == 2

    findings = p_data["findings"]
    assert any("furnace_id" in err for err in findings[0]["errors"])
    assert any("furnace_id" in err for err in findings[1]["errors"])

    commit_resp = client.post("/api/v1/heats/import/commit", json={"rows": rows}, headers=bearer("Foundry"))
    assert commit_resp.status_code == 400


def test_heat_import_consistent_multiline_charges_succeeds(client: TestClient, db_session: Session):
    """Verifies that multiple charge lines with consistent header metadata aggregate cleanly under one heat."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item_returns = MaterialItem(
        item_code="FDY-RM-021",
        name="Foundry Returns Grade A",
        department_id=dept.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item_returns)
    db_session.commit()

    rows = [
        {
            "heat_number": "102603-5003",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1500.0000",
            "uom_code": "KG",
            "part_description": "Gear Housing Cast",
            "quantity_produced": "35.0000",
        },
        {
            "heat_number": "102603-5003",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Foundry Returns Grade A",
            "charged_quantity": "500.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "H-102603-5003",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "250.0000",
            "uom_code": "KG",
        },
    ]

    preview_resp = client.post("/api/v1/heats/import/preview", json={"rows": rows}, headers=bearer("Foundry"))
    assert preview_resp.status_code == 200
    p_data = preview_resp.json()
    assert p_data["can_commit"] is True
    assert p_data["valid_rows"] == 3
    assert p_data["error_rows"] == 0

    commit_resp = client.post("/api/v1/heats/import/commit", json={"rows": rows}, headers=bearer("Foundry"))
    assert commit_resp.status_code == 201
    c_data = commit_resp.json()
    assert c_data["heats_created_count"] == 1
    assert "102603-5003" in c_data["heats_created"]

    heat = db_session.query(HeatHeader).filter_by(normalized_heat_number="H-102603-5003").first()
    assert heat is not None
    assert len(heat.charge_lines) == 3
    total_charged = sum(cl.charged_quantity for cl in heat.charge_lines)
    assert total_charged == Decimal("2250.0000")
    assert len(heat.parts_produced) == 1
    assert heat.parts_produced[0].quantity_produced == Decimal("35.0000")


def test_heat_import_atomic_rejection_and_zero_stock_ledger_entries(client: TestClient, db_session: Session):
    """Verifies atomic batch rejection when one heat has header conflicts, and confirms zero stock ledger impact."""
    initial_ledger_count = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert initial_ledger_count == 0

    rows = [
        {
            "heat_number": "102603-5004",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1000.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "102603-5005",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1000.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "102603-5005",
            "heat_date": "2026-10-21",
            "furnace_id": "F-02",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "500.0000",
            "uom_code": "KG",
        },
    ]

    commit_resp = client.post("/api/v1/heats/import/commit", json={"rows": rows}, headers=bearer("Foundry"))
    assert commit_resp.status_code == 400

    assert db_session.query(HeatHeader).filter_by(normalized_heat_number="H-102603-5004").first() is None
    assert db_session.query(HeatHeader).filter_by(normalized_heat_number="H-102603-5005").first() is None

    ledger_count_after = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert ledger_count_after == 0


def test_heat_import_template_download(client: TestClient):
    """Verifies that the Excel template download endpoint generates a valid styled .xlsx workbook."""
    resp = client.get("/api/v1/heats/import/template", headers=bearer("Foundry"))
    assert resp.status_code == 200
    assert "spreadsheetml.sheet" in resp.headers["content-type"]
    assert "VSPL_Heat_Log_Import_Template.xlsx" in resp.headers["content-disposition"]

    wb = openpyxl.load_workbook(filename=io.BytesIO(resp.content))
    assert "Heat_Log_Template" in wb.sheetnames
    ws = wb["Heat_Log_Template"]
    headers = list(list(ws.iter_rows(values_only=True))[0])
    assert "heat_number" in headers
    assert "heat_date" in headers
    assert "material_description" in headers
    assert "charged_quantity" in headers


def test_heat_import_excel_upload_valid_and_commit(client: TestClient, db_session: Session):
    """Verifies direct .xlsx file upload, dry-run preview, and subsequent atomic commit."""
    headers = [
        "heat_number", "heat_date", "furnace_id", "shift",
        "material_description", "charged_quantity", "uom_code",
        "part_description", "quantity_produced"
    ]
    rows = [
        ["102603-6001", "2026-10-23", "F-01", "SHIFT_A", "Cast Iron Borings", 1800.0, "KG", "Valve Body Cast", 50],
        ["102603-6001", "2026-10-23", "F-01", "SHIFT_A", "Cast Iron Borings", 200.0, "KG", "", ""]
    ]
    excel_bytes = make_excel(headers, rows)

    upload_resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("Furnace_Batch_6001.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert upload_resp.status_code == 200, upload_resp.text
    p_data = upload_resp.json()
    assert p_data["can_commit"] is True
    assert p_data["total_rows"] == 2
    assert p_data["valid_rows"] == 2
    assert p_data["error_rows"] == 0
    assert p_data["source_filename"] == "Furnace_Batch_6001.xlsx"

    # User confirms and executes atomic commit using the returned parsed rows
    commit_resp = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": p_data["rows"], "source_filename": p_data["source_filename"]},
        headers=bearer("Foundry"),
    )
    assert commit_resp.status_code == 201
    c_data = commit_resp.json()
    assert c_data["heats_created_count"] == 1
    assert "102603-6001" in c_data["heats_created"]

    heat = db_session.query(HeatHeader).filter_by(normalized_heat_number="H-102603-6001").first()
    assert heat is not None
    assert len(heat.charge_lines) == 2
    assert len(heat.parts_produced) == 1


def test_heat_import_excel_upload_invalid_extension(client: TestClient):
    """Verifies that non-Excel file extensions are rejected with 400 Bad Request."""
    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("logs.csv", b"heat_number,heat_date\n102603-01,2026-10-21", "text/csv")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 400
    assert "Only modern Excel (.xlsx, .xlsm) files are accepted" in resp.json()["detail"]


def test_heat_import_excel_upload_empty_file(client: TestClient):
    """Verifies that an empty (0 byte) file is rejected with 400 Bad Request."""
    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("empty.xlsx", b"", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_heat_import_excel_upload_malformed_workbook(client: TestClient):
    """Verifies that corrupt Excel bytes are rejected with 400 Bad Request."""
    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("corrupt.xlsx", b"NOT_A_VALID_ZIP_ARCHIVE", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 400
    assert "Invalid or corrupt Excel workbook" in resp.json()["detail"]


def test_heat_import_excel_upload_missing_columns(client: TestClient):
    """Verifies that workbooks missing mandatory headers are rejected with 400 Bad Request."""
    bad_headers = ["random_col_1", "random_col_2"]
    bad_rows = [["val1", "val2"]]
    excel_bytes = make_excel(bad_headers, bad_rows)

    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("missing_cols.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 400
    assert "missing required column" in resp.json()["detail"].lower()


def test_heat_import_excel_upload_skips_blank_rows(client: TestClient):
    """Verifies that interspersed empty rows are gracefully skipped without creating phantom errors."""
    headers = ["heat_number", "heat_date", "furnace_id", "material_description", "charged_quantity", "uom_code"]
    rows = [
        ["102603-6002", "2026-10-23", "F-01", "Cast Iron Borings", 1000.0, "KG"],
        [None, None, None, None, None, None],
        ["", "", "", "", "", ""],
        ["102603-6002", "2026-10-23", "F-01", "Cast Iron Borings", 500.0, "KG"],
    ]
    excel_bytes = make_excel(headers, rows)

    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("with_blank_rows.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 200
    p_data = resp.json()
    assert p_data["total_rows"] == 2
    assert p_data["valid_rows"] == 2
    assert p_data["error_rows"] == 0


def test_heat_import_excel_upload_conflicting_headers_rejected(client: TestClient):
    """Verifies that header inconsistencies inside an uploaded .xlsx are flagged in preview."""
    headers = ["heat_number", "heat_date", "furnace_id", "material_description", "charged_quantity", "uom_code"]
    rows = [
        ["102603-6003", "2026-10-23", "F-01", "Cast Iron Borings", 1000.0, "KG"],
        ["102603-6003", "2026-10-24", "F-01", "Cast Iron Borings", 500.0, "KG"],
    ]
    excel_bytes = make_excel(headers, rows)

    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("conflicting_dates.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 200
    p_data = resp.json()
    assert p_data["can_commit"] is False
    assert p_data["error_rows"] == 2
    assert any("Header conflict for heat 'H-102603-6003'" in err for err in p_data["findings"][0]["errors"])


def test_heat_import_excel_upload_multisheet_support(client: TestClient):
    """Verifies multi-sheet workbook parsing with 'Heat Log' and 'Charge Details' sheets."""
    wb = openpyxl.Workbook()
    # Sheet 1: Heat Log
    ws_heat = wb.active
    ws_heat.title = "Heat Log"
    ws_heat.append(["heat_number", "heat_date", "furnace_id", "shift", "part_description", "quantity_produced"])
    ws_heat.append(["102603-6004", "2026-10-23", "F-02", "SHIFT_B", "Axle Bracket", 20])

    # Sheet 2: Charge Details
    ws_charge = wb.create_sheet(title="Charge Details")
    ws_charge.append(["heat_number", "material_description", "charged_quantity", "uom_code"])
    ws_charge.append(["102603-6004", "Cast Iron Borings", 3000.0, "KG"])
    ws_charge.append(["102603-6004", "Cast Iron Borings", 1000.0, "KG"])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    excel_bytes = buffer.getvalue()

    resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("multisheet.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 200, resp.text
    p_data = resp.json()
    assert p_data["total_rows"] == 2
    assert p_data["valid_rows"] == 2
    assert p_data["can_commit"] is True


def test_heat_import_excel_upload_zero_stock_ledger_entries(client: TestClient, db_session: Session):
    """Verifies that uploading and committing Excel batches never inserts stock ledger entries."""
    initial_ledger_count = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0

    headers = ["heat_number", "heat_date", "furnace_id", "material_description", "charged_quantity", "uom_code"]
    rows = [
        ["102603-6005", "2026-10-23", "F-01", "Cast Iron Borings", 1000.0, "KG"],
    ]
    excel_bytes = make_excel(headers, rows)

    upload_resp = client.post(
        "/api/v1/heats/import/upload",
        files={"file": ("zero_ledger.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=bearer("Foundry"),
    )
    assert upload_resp.status_code == 200
    p_data = upload_resp.json()

    commit_resp = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": p_data["rows"], "source_filename": "zero_ledger.xlsx"},
        headers=bearer("Foundry"),
    )
    assert commit_resp.status_code == 201

    ledger_count_after = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert ledger_count_after == initial_ledger_count
