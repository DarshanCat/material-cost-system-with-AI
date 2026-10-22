"""
Tests for Goods Receipt Note (GRN) workflow and validations.
Verifies rate ex GST rules, decimal precision, duplicate invoice detection, and lifecycle.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.vendor import Vendor
from app.services.validators import normalize_vendor_name
from app.models.grn import GRNHeader, GRNStatus


def test_grn_creation_and_approval_lifecycle(client: TestClient, db_session: Session, management_headers: dict):
    # Setup test vendor and item
    vendor = Vendor(
        name="Tata Steel Ltd",
        normalized_name=normalize_vendor_name("Tata Steel Ltd"),
        gstin="27AAACT2727Q1ZW",
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Foundry Grade",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # 1. Create GRN
    payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": "INV-2026-9901",
        "invoice_date": str(date.today()),
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "5000.00",
                "rate_ex_gst": "42.50",
                "gst_percent": "18.00",
                "remarks": "Standard consignment",
            }
        ],
    }

    resp = client.post("/api/v1/grn/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["grn_number"].startswith("GRN-")
    assert len(data["lines"]) == 1
    assert data["lines"][0]["rate_ex_gst"] == "42.50"
    grn_id = data["id"]

    # 2. Submit GRN
    sub_resp = client.post(f"/api/v1/grn/{grn_id}/submit", json={"comments": "Checked physical delivery"})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Approve GRN
    app_resp = client.post(f"/api/v1/grn/{grn_id}/approve", json={"comments": "Approved for storage"}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"
    assert len(app_resp.json()["audit_logs"]) == 3  # CREATED, SUBMITTED, APPROVED


def test_grn_external_vendor_mandatory_rate_rule(client: TestClient, db_session: Session):
    vendor = Vendor(
        name="Jindal SAW",
        normalized_name=normalize_vendor_name("Jindal SAW"),
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item = MaterialItem(
        item_code="FDY-RM-002",
        name="Steel Scrap Grade A",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Rate missing for external raw material receipt -> must fail
    payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": "INV-JS-01",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "1200.00",
                "rate_ex_gst": None,  # Missing rate!
            }
        ],
    }

    resp = client.post("/api/v1/grn/", json=payload)
    assert resp.status_code == 422
    assert "requires rate per UOM" in resp.json()["detail"]


def test_grn_duplicate_invoice_warning_flag(client: TestClient, db_session: Session):
    vendor = Vendor(
        name="Hindalco Industries",
        normalized_name=normalize_vendor_name("Hindalco Industries"),
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item = MaterialItem(
        item_code="FDY-RM-003",
        name="Aluminum Ingot 99.7%",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    payload1 = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": "DUPLICATE-CHECK-001",
        "invoice_date": str(date.today()),
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom.id,
                "quantity": "100.00",
                "rate_ex_gst": "50.00",
            }
        ],
    }
    resp1 = client.post("/api/v1/grn/", json=payload1)
    assert resp1.status_code == 201

    # Second entry with identical vendor and invoice number -> creates with traceability warning
    resp2 = client.post("/api/v1/grn/", json=payload1)
    assert resp2.status_code == 201
    assert len(resp2.json()["validation_warnings"]) > 0
    assert "Possible duplicate invoice" in resp2.json()["validation_warnings"][0]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
