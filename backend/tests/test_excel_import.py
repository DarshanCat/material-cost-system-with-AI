"""
Tests for Excel Import Validation and Atomic Commit Engine.
Verifies header validation, multi-row preview, error rejection, and atomic commit.
"""

import io
from datetime import date
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.vendor import Vendor
from app.services.validators import normalize_vendor_name


def _create_test_excel(headers: list, rows: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_excel_template_download(client: TestClient):
    resp = client.get("/api/v1/excel-import/template/GRN")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]


def test_excel_import_validation_and_atomic_commit(client: TestClient, db_session: Session):
    # Setup test entities
    vendor = Vendor(
        name="Bharat Forge Ltd",
        normalized_name=normalize_vendor_name("Bharat Forge Ltd"),
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item = MaterialItem(
        item_code="FDY-RM-099",
        name="Foundry Coke Premium",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    headers = [
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
    ]

    valid_rows = [
        [
            str(date.today()),
            "EXTERNAL_VENDOR",
            "Bharat Forge Ltd",
            "INV-BF-101",
            str(date.today()),
            "FDY-RM-099",
            "KG",
            1500.0,
            45.0,
            18.0,
        ]
    ]

    excel_bytes = _create_test_excel(headers, valid_rows)

    # 1. Validate preview
    files = {"file": ("test_grn.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"import_type": "GRN"}
    val_resp = client.post("/api/v1/excel-import/validate", data=data, files=files)
    assert val_resp.status_code == 200, val_resp.text
    summary = val_resp.json()
    assert summary["can_commit"] is True
    assert summary["valid_rows_count"] == 1
    assert summary["error_rows_count"] == 0

    # 2. Atomic Commit
    commit_payload = {
        "import_type": "GRN",
        "rows": [f["raw_data"] for f in summary["findings"]],
        "created_by": "ExcelImporter",
    }
    commit_resp = client.post("/api/v1/excel-import/commit", json=commit_payload)
    assert commit_resp.status_code == 200
    res = commit_resp.json()
    assert res["success"] is True
    assert res["created_count"] == 1
    assert res["created_documents"][0].startswith("GRN-")


def test_excel_import_blocking_errors_prevent_commit(client: TestClient, db_session: Session):
    headers = [
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
    ]

    # Row has non-existent item and invalid quantity
    invalid_rows = [
        [
            str(date.today()),
            "EXTERNAL_VENDOR",
            "NonExistent Vendor",
            "INV-BAD-01",
            str(date.today()),
            "UNKNOWN-ITEM-999",
            "KG",
            -50.0,  # Negative quantity!
            0,
            0,
        ]
    ]

    excel_bytes = _create_test_excel(headers, invalid_rows)
    files = {"file": ("bad_grn.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    val_resp = client.post("/api/v1/excel-import/validate", data={"import_type": "GRN"}, files=files)
    assert val_resp.status_code == 200
    summary = val_resp.json()
    assert summary["can_commit"] is False
    assert summary["error_rows_count"] == 1
    assert len(summary["findings"][0]["errors"]) >= 2


def test_excel_template_parser_roundtrip(client: TestClient):
    """Verify that downloaded templates for GRN, ISSUE, and WASTE parse without missing header errors."""
    for import_type in ["GRN", "ISSUE", "WASTE"]:
        resp = client.get(f"/api/v1/excel-import/template/{import_type}")
        assert resp.status_code == 200
        template_bytes = resp.content

        files = {"file": (f"{import_type}_template.xlsx", template_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        val_resp = client.post("/api/v1/excel-import/validate", data={"import_type": import_type}, files=files)
        assert val_resp.status_code == 200
        summary = val_resp.json()
        assert summary["error_rows_count"] == 0
        assert summary["total_rows"] == 0


def test_excel_import_missing_and_unexpected_headers(client: TestClient):
    """Verify missing required columns are identified at row 1, and unexpected extra columns are safely ignored."""
    # 1. Missing columns: only 3 of 10 headers
    bad_headers = ["Receipt Date", "Item Code", "Quantity"]
    excel_bytes = _create_test_excel(bad_headers, [])
    files = {"file": ("missing_cols.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/excel-import/validate", data={"import_type": "GRN"}, files=files)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["can_commit"] is False
    assert summary["error_rows_count"] == 1
    assert summary["findings"][0]["row_number"] == 1
    assert "Missing required columns in sheet" in summary["message"]

    # 2. Case-insensitive and extra unexpected columns
    mixed_headers = [
        "receipt date",
        "SOURCE TYPE",
        "Vendor Name",
        "INVOICE NO",
        "Invoice Date",
        "item code",
        "uom",
        "Quantity",
        "Rate Ex GST",
        "GST %",
        "Extra Notes Column",  # Unexpected extra column
        "Legacy Column ID",    # Unexpected extra column
    ]
    excel_bytes_extra = _create_test_excel(mixed_headers, [])
    files_extra = {"file": ("extra_cols.xlsx", excel_bytes_extra, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp_extra = client.post("/api/v1/excel-import/validate", data={"import_type": "GRN"}, files=files_extra)
    assert resp_extra.status_code == 200
    summary_extra = resp_extra.json()
    assert summary_extra["error_rows_count"] == 0
    assert summary_extra["total_rows"] == 0


def test_excel_import_empty_rows_and_malformed_numbers(client: TestClient, db_session: Session):
    """Verify completely empty rows are skipped and malformed numbers report row-specific errors without crashes."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    vendor = Vendor(name="Steel Authority of India Ltd", normalized_name=normalize_vendor_name("Steel Authority of India Ltd"))
    item = MaterialItem(item_code="FDY-RM-080", name="High Carbon Ferro Chrome", department_id=dept.id, category="RAW_MATERIALS", base_uom_id=uom.id)
    item2 = MaterialItem(item_code="FDY-RM-081", name="Low Carbon Ferro Chrome", department_id=dept.id, category="RAW_MATERIALS", base_uom_id=uom.id)
    db_session.add_all([vendor, item, item2])
    db_session.commit()

    headers = [
        "Receipt Date", "Source Type", "Vendor Name", "Invoice No", "Invoice Date",
        "Item Code", "UOM", "Quantity", "Rate Ex GST", "GST %",
    ]

    rows = [
        [str(date.today()), "EXTERNAL_VENDOR", "Steel Authority of India Ltd", "INV-M-01", str(date.today()), "FDY-RM-080", "KG", 100.0, 50.0, 18.0],
        [None, None, "", None, None, "", None, None, None, None],  # Completely empty row 3 -> skipped
        [str(date.today()), "EXTERNAL_VENDOR", "Steel Authority of India Ltd", "INV-M-01", str(date.today()), "FDY-RM-081", "KG", "invalid_qty", "not_a_rate", "bad_gst"],  # Row 4: Malformed
        ["", "", "", "", "", "", "", "", "", ""],  # Empty row 5 -> skipped
    ]

    excel_bytes = _create_test_excel(headers, rows)
    files = {"file": ("malformed.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/excel-import/validate", data={"import_type": "GRN"}, files=files)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_rows"] == 2  # Only 2 non-empty rows inspected
    assert summary["valid_rows_count"] == 1
    assert summary["error_rows_count"] == 1
    assert summary["can_commit"] is False

    error_finding = [f for f in summary["findings"] if f["status"] == "ERROR"][0]
    assert error_finding["row_number"] == 4
    assert any("Invalid numeric" in err for err in error_finding["errors"])


def test_excel_import_uom_precision_and_duplicate_lines(client: TestClient, db_session: Session):
    """Verify UOM decimal precision enforcement and intra-document duplicate material line advisory warnings."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_nos = db_session.query(UOM).filter_by(code="NOS").first()  # Precision 0
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()    # Precision 4

    vendor = Vendor(name="Foundry Ceramics India", normalized_name=normalize_vendor_name("Foundry Ceramics India"))
    item_filter = MaterialItem(item_code="FDY-CS-020", name="Ceramic Foam Filter 100x100", department_id=dept.id, category="CONSUMABLES", base_uom_id=uom_nos.id)
    item_sand = MaterialItem(item_code="FDY-RM-085", name="Silica Sand Coarse", department_id=dept.id, category="RAW_MATERIALS", base_uom_id=uom_kg.id)
    db_session.add_all([vendor, item_filter, item_sand])
    db_session.commit()

    headers = [
        "Receipt Date", "Source Type", "Vendor Name", "Invoice No", "Invoice Date",
        "Item Code", "UOM", "Quantity", "Rate Ex GST", "GST %",
    ]

    # Row 2 & Row 3 share same invoice (INV-SPLIT-88) and both contain item_sand (FDY-RM-085)
    # Row 4 contains item_filter (FDY-CS-020) with fractional quantity 25.5 on NOS UOM
    rows = [
        [str(date.today()), "EXTERNAL_VENDOR", "Foundry Ceramics India", "INV-SPLIT-88", str(date.today()), "FDY-RM-085", "KG", 1000.0, 30.0, 18.0],
        [str(date.today()), "EXTERNAL_VENDOR", "Foundry Ceramics India", "INV-SPLIT-88", str(date.today()), "FDY-RM-085", "KG", 500.0, 30.0, 18.0],
        [str(date.today()), "EXTERNAL_VENDOR", "Foundry Ceramics India", "INV-SPLIT-89", str(date.today()), "FDY-CS-020", "NOS", 25.5, 120.0, 18.0],  # Invalid fraction!
    ]

    excel_bytes = _create_test_excel(headers, rows)
    files = {"file": ("precision_dup.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/excel-import/validate", data={"import_type": "GRN"}, files=files)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["can_commit"] is False
    assert summary["error_rows_count"] == 1
    assert summary["warning_rows_count"] == 2

    # Check duplicate warnings on row 2 and row 3
    row2 = summary["findings"][0]
    row3 = summary["findings"][1]
    assert any("Duplicate material line warning" in w and "FDY-RM-085" in w and "rows 2, 3" in w for w in row2["warnings"])
    assert any("Duplicate material line warning" in w and "FDY-RM-085" in w and "rows 2, 3" in w for w in row3["warnings"])

    # Check precision error on row 4
    row4 = summary["findings"][2]
    assert row4["status"] == "ERROR"
    assert any("exceeds maximum allowed decimal places (0)" in err for err in row4["errors"])


def test_excel_import_all_or_nothing_rollback_on_failed_commit(client: TestClient, db_session: Session):
    """Verify that if ANY row fails pre-commit validation, zero documents are committed to the database."""
    from app.models.grn import GRNHeader

    initial_grn_count = db_session.query(GRNHeader).count()

    invalid_commit_payload = {
        "import_type": "GRN",
        "rows": [
            {
                "Receipt Date": str(date.today()),
                "Source Type": "EXTERNAL_VENDOR",
                "Vendor Name": "Ghost Vendor Nonexistent",
                "Invoice No": "INV-FAIL-01",
                "Item Code": "NONEXISTENT-CODE",
                "UOM": "KG",
                "Quantity": "100.0",
            }
        ],
        "created_by": "TestUser",
    }
    commit_resp = client.post("/api/v1/excel-import/commit", json=invalid_commit_payload)
    assert commit_resp.status_code == 400
    assert "Row 1: Material Item Code" in commit_resp.json()["detail"]

    # Verify zero partial records were created
    current_grn_count = db_session.query(GRNHeader).count()
    assert current_grn_count == initial_grn_count


def test_excel_import_empty_batch_commit_rejected(client: TestClient):
    """Verify committing an empty batch is rejected with HTTP 400."""
    resp = client.post("/api/v1/excel-import/commit", json={"import_type": "GRN", "rows": []})
    assert resp.status_code == 400
    assert "Cannot commit an empty import batch" in resp.json()["detail"]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
