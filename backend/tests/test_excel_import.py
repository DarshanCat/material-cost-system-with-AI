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


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
