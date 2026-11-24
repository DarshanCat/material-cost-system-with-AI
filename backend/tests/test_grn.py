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


def test_grn_intra_document_duplicate_lines_warning(client: TestClient, db_session: Session, management_headers: dict):
    """Verify duplicate material_item_id entries within a GRN trigger non-blocking advisory warnings."""
    vendor = Vendor(
        name="Kirloskar Ferrous",
        normalized_name=normalize_vendor_name("Kirloskar Ferrous"),
        gstin="29AAACK1919A1Z5",
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item1 = MaterialItem(
        item_code="FDY-RM-010",
        name="Foundry Pig Iron Grade 1",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    item2 = MaterialItem(
        item_code="FDY-RM-011",
        name="Foundry Pig Iron Grade 2",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # 1. Unique items produce no duplicate line warning
    resp_unique = client.post(
        "/api/v1/grn/",
        json={
            "receipt_date": str(date.today()),
            "source_type": "EXTERNAL_VENDOR",
            "vendor_id": vendor.id,
            "vendor_invoice_no": "INV-UNIQ-001",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "100.00", "rate_ex_gst": "40.00"},
                {"line_number": 2, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "200.00", "rate_ex_gst": "45.00"},
            ],
        },
    )
    assert resp_unique.status_code == 201
    data_unique = resp_unique.json()
    assert not any("Duplicate material line warning" in w for w in data_unique["validation_warnings"])
    assert len(data_unique["lines"]) == 2

    # 2. Two occurrences of item1 (lines 1 and 2) produce warning with line numbers
    resp_two = client.post(
        "/api/v1/grn/",
        json={
            "receipt_date": str(date.today()),
            "source_type": "EXTERNAL_VENDOR",
            "vendor_id": vendor.id,
            "vendor_invoice_no": "INV-SPLIT-002",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "500.00", "rate_ex_gst": "42.00"},
                {"line_number": 2, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "300.00", "rate_ex_gst": "42.00"},
            ],
        },
    )
    assert resp_two.status_code == 201
    data_two = resp_two.json()
    assert len(data_two["lines"]) == 2
    assert Decimal(str(data_two["lines"][0]["quantity"])) == Decimal("500.0000")
    assert Decimal(str(data_two["lines"][1]["quantity"])) == Decimal("300.0000")
    dup_warnings_two = [w for w in data_two["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_two) == 1
    assert "FDY-RM-010" in dup_warnings_two[0]
    assert "lines 1, 2" in dup_warnings_two[0]

    # 3. Three occurrences across lines 1, 2, and 4
    resp_three = client.post(
        "/api/v1/grn/",
        json={
            "receipt_date": str(date.today()),
            "source_type": "EXTERNAL_VENDOR",
            "vendor_id": vendor.id,
            "vendor_invoice_no": "INV-SPLIT-003",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "100.00", "rate_ex_gst": "42.00"},
                {"line_number": 2, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "150.00", "rate_ex_gst": "42.00"},
                {"line_number": 3, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "50.00", "rate_ex_gst": "45.00"},
                {"line_number": 4, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "200.00", "rate_ex_gst": "42.00"},
            ],
        },
    )
    assert resp_three.status_code == 201
    data_three = resp_three.json()
    assert len(data_three["lines"]) == 4
    dup_warnings_three = [w for w in data_three["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_three) == 1
    assert "lines 1, 2, 4" in dup_warnings_three[0]

    # 4. Combination: Duplicate vendor invoice AND intra-document duplicate line warnings coexist
    resp_combo = client.post(
        "/api/v1/grn/",
        json={
            "receipt_date": str(date.today()),
            "source_type": "EXTERNAL_VENDOR",
            "vendor_id": vendor.id,
            "vendor_invoice_no": "INV-SPLIT-003",  # Same invoice as above
            "lines": [
                {"line_number": 1, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "100.00", "rate_ex_gst": "45.00"},
                {"line_number": 2, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "100.00", "rate_ex_gst": "45.00"},
            ],
        },
    )
    assert resp_combo.status_code == 201
    warnings_combo = resp_combo.json()["validation_warnings"]
    assert any("Possible duplicate invoice" in w for w in warnings_combo)
    assert any("Duplicate material line warning" in w and "FDY-RM-011" in w and "lines 1, 2" in w for w in warnings_combo)

    # 5. Approval posts each line accurately to stock ledger
    grn_id = resp_two.json()["id"]
    client.post(f"/api/v1/grn/{grn_id}/submit", json={})
    app_res = client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=management_headers)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"


def test_internal_grn_sourcing_and_stock_impact(client: TestClient, db_session: Session, management_headers: dict):
    """
    Verify internal GRN sourcing modes (INTERNAL_VSPL and SEGREGATION_YARD):
    - vendor_id and rate_ex_gst are optional.
    - Approval generates INTERNAL_INWARD movements in the stock ledger with positive quantity.
    """
    from app.models.ledger import StockLedgerEntry, MovementType
    from app.services.ledger_service import get_material_stock_balance

    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item_internal = MaterialItem(
        item_code="FDY-RM-040",
        name="Internal Transfer Billet",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    item_yard = MaterialItem(
        item_code="FDY-RM-041",
        name="Segregation Yard Recovered Scrap",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add_all([item_internal, item_yard])
    db_session.commit()

    # 1. INTERNAL_VSPL (Factory transfer / subcontract return)
    payload_internal = {
        "receipt_date": str(date.today()),
        "source_type": "INTERNAL_VSPL",
        "notes": "Internal plant inter-unit transfer",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item_internal.id,
                "uom_id": uom.id,
                "quantity": "2500.00",
            }
        ],
    }
    resp1 = client.post("/api/v1/grn/", json=payload_internal)
    assert resp1.status_code == 201, resp1.text
    grn1_id = resp1.json()["id"]
    assert resp1.json()["source_type"] == "INTERNAL_VSPL"

    # Submit and approve
    client.post(f"/api/v1/grn/{grn1_id}/submit", json={"comments": "Transfer received at gate"})
    app1 = client.post(f"/api/v1/grn/{grn1_id}/approve", json={"comments": "Verified and stored"}, headers=management_headers)
    assert app1.status_code == 200

    bal1, _, _, _ = get_material_stock_balance(db_session, item_internal.id)
    assert bal1 == Decimal("2500.0000")

    entry1 = db_session.query(StockLedgerEntry).filter_by(
        source_document_id=grn1_id,
        material_item_id=item_internal.id,
    ).first()
    assert entry1 is not None
    assert entry1.movement_type == MovementType.INTERNAL_INWARD.value
    assert entry1.quantity_delta == Decimal("2500.0000")

    # 2. SEGREGATION_YARD (Segregation yard recovery)
    payload_yard = {
        "receipt_date": str(date.today()),
        "source_type": "SEGREGATION_YARD",
        "notes": "Recovered runner pieces from yard segregation",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item_yard.id,
                "uom_id": uom.id,
                "quantity": "750.00",
            }
        ],
    }
    resp2 = client.post("/api/v1/grn/", json=payload_yard)
    assert resp2.status_code == 201, resp2.text
    grn2_id = resp2.json()["id"]
    assert resp2.json()["source_type"] == "SEGREGATION_YARD"

    # Submit and approve
    client.post(f"/api/v1/grn/{grn2_id}/submit", json={})
    app2 = client.post(f"/api/v1/grn/{grn2_id}/approve", json={}, headers=management_headers)
    assert app2.status_code == 200

    bal2, _, _, _ = get_material_stock_balance(db_session, item_yard.id)
    assert bal2 == Decimal("750.0000")

    entry2 = db_session.query(StockLedgerEntry).filter_by(
        source_document_id=grn2_id,
        material_item_id=item_yard.id,
    ).first()
    assert entry2 is not None
    assert entry2.movement_type == MovementType.INTERNAL_INWARD.value
    assert entry2.quantity_delta == Decimal("750.0000")


def test_grn_gst_rate_separation_and_non_blending(client: TestClient, db_session: Session):
    """
    Verify Rule T2 & Rule 6:
    - Pre-GST rate (rate_ex_gst) and GST tax percentage (gst_percent) are strictly separated.
    - Tax is never blended into the inventory material unit rate.
    """
    vendor = Vendor(
        name="Kalyani Steels Ltd",
        normalized_name=normalize_vendor_name("Kalyani Steels Ltd"),
        gstin="29AAACK2020A1Z2",
    )
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    db_session.add(vendor)
    db_session.commit()

    item = MaterialItem(
        item_code="FDY-RM-050",
        name="Steel Scrap Bundle",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    payload = {
        "receipt_date": str(date.today()),
        "source_type": "EXTERNAL_VENDOR",
        "vendor_id": vendor.id,
        "vendor_invoice_no": "INV-KSL-9001",
        "invoice_date": str(date.today()),
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom.id,
                "quantity": "1000.00",
                "rate_ex_gst": "48.00",
                "gst_percent": "18.00",
            }
        ],
    }

    resp = client.post("/api/v1/grn/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    line = data["lines"][0]

    # Pre-GST rate remains 48.00, NOT 48.00 * 1.18 = 56.64
    assert Decimal(str(line["rate_ex_gst"])) == Decimal("48.00")
    assert Decimal(str(line["gst_percent"])) == Decimal("18.00")

    # Fetch directly from database to verify schema separation
    db_grn = db_session.query(GRNHeader).filter_by(id=data["id"]).first()
    db_line = db_grn.lines[0]
    assert db_line.rate_ex_gst == Decimal("48.00")
    assert db_line.gst_percent == Decimal("18.00")



@pytest.fixture(autouse=True)
def _authenticate_as_stores(client: TestClient, stores_headers: dict):
    """GRN creation and submission workflow tests run as Stores; approvals pass management_headers."""
    client.headers.update(stores_headers)


def test_admin_cannot_create_grn_without_receipt_create(
    anon_client: TestClient, db_session: Session, admin_headers: dict
):
    """Explicit RBAC guard: Admin lacks receipt:create and is rejected with 403 on GRN creation."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(
        item_code="FDY-RM-990",
        name="Admin Forbidden Test Item",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    payload = {
        "receipt_date": str(date.today()),
        "source_type": "INTERNAL_VSPL",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom.id,
                "quantity": "10.00",
            }
        ],
    }
    resp = anon_client.post("/api/v1/grn/", json=payload, headers=admin_headers)
    assert resp.status_code == 403
    assert "lacks permission 'receipt:create'" in resp.json()["detail"]
