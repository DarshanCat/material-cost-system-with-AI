"""
Tests for Waste Disposition module.
Verifies waste categories, disposition types, and supervisor approval flow.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem


def test_waste_disposition_lifecycle(client: TestClient, db_session: Session, management_headers: dict):
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-BOR-001",
        name="SG Iron Machining Borings",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # 1. Create waste disposition
    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "BORINGS",
        "disposition_type": "INTERNAL_RECOVERY",
        "source_department_id": dept_ms.id,
        "destination_notes": "Transferred to foundry melting yard for remelting",
        "notes": "Weekly machine shop boring collection",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "450.00",
                "reason": "Machining generation",
            }
        ],
    }

    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["waste_number"].startswith("WST-")
    waste_id = data["id"]

    # 2. Submit
    sub_resp = client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Approve
    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Recovery verified"}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"


def test_waste_scrap_outward_blocked_on_uninitialized_stock(client: TestClient, db_session: Session, management_headers: dict):
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-WST-UNINIT",
        name="Uninitialized Waste Item",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "SLAG",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": dept_ms.id,
        "destination_notes": "External scrap yard sale",
        "notes": "Scrap outward test",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
                "reason": "Scrap outward disposal",
            }
        ],
    }
    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201
    waste_id = resp.json()["id"]

    sub_resp = client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    assert sub_resp.status_code == 200

    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Should fail on uninitialized"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stock baseline has not been initialized" in app_resp.json()["detail"]


def test_waste_scrap_outward_blocked_on_insufficient_stock(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-WST-INSUFF",
        name="Insufficient Stock Waste Item",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 20 kg
    ob = StockLedgerEntry(
        entry_number="STK-WST-OB-01",
        posting_group_id="POST-WST-OB-01",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("20.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-WST-01",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Request to scrap 50 kg (available is only 20 kg)
    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "SLAG",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": dept_ms.id,
        "destination_notes": "External disposal",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
            }
        ],
    }
    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201
    waste_id = resp.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Should fail on insufficient stock"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Insufficient inventory" in app_resp.json()["detail"]

    # Balance must remain unchanged at 20.0000 kg
    bal_resp = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_resp.json()["current_balance"])) == Decimal("20.0000")


def test_waste_scrap_outward_multiline_cumulative_check(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-WST-MULTILINE",
        name="Multiline Waste Item",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-WST-OB-02",
        posting_group_id="POST-WST-OB-02",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-WST-02",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Line 1: 60 kg, Line 2: 50 kg -> Total 110 kg > 100 kg
    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "SLAG",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": dept_ms.id,
        "destination_notes": "Split load outward scrap",
        "lines": [
            {"line_number": 1, "material_item_id": item.id, "uom_id": uom_kg.id, "quantity": "60.00"},
            {"line_number": 2, "material_item_id": item.id, "uom_id": uom_kg.id, "quantity": "50.00"},
        ],
    }
    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201
    waste_id = resp.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Cumulative overdraw"}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Insufficient inventory" in app_resp.json()["detail"]

    # Verify atomic rollback: exactly 0 scrap ledger entries posted, balance remains 100 kg
    bal_resp = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_resp.json()["current_balance"])) == Decimal("100.0000")
    assert bal_resp.json()["movement_count"] == 1


def test_waste_scrap_outward_successful_posting(client: TestClient, db_session: Session, management_headers: dict):
    from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-WST-SUCCESS",
        name="Valid Waste Scrap Item",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initial balance = 100 kg
    ob = StockLedgerEntry(
        entry_number="STK-WST-OB-03",
        posting_group_id="POST-WST-OB-03",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-WST-03",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "SLAG",
        "disposition_type": "SCRAP_OUTWARD",
        "source_department_id": dept_ms.id,
        "destination_notes": "Valid scrap disposal",
        "lines": [
            {"line_number": 1, "material_item_id": item.id, "uom_id": uom_kg.id, "quantity": "40.00"},
        ],
    }
    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201
    waste_id = resp.json()["id"]

    client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Approved 40kg scrap outward"}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Balance must now be 60 kg (100 - 40)
    bal_resp = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_resp.json()["current_balance"])) == Decimal("60.0000")
    assert bal_resp.json()["movement_count"] == 2


def test_waste_disposition_intra_document_duplicate_lines_warning(client: TestClient, db_session: Session):
    """Verify duplicate material_item_id lines on a waste disposition trigger non-blocking advisory warnings."""
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item1 = MaterialItem(
        item_code="MS-WST-010",
        name="SG Iron Borings Grade A",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom.id,
    )
    item2 = MaterialItem(
        item_code="MS-WST-011",
        name="SG Iron Borings Grade B",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom.id,
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # 1. Unique items produce no duplicate line warning
    resp_unique = client.post(
        "/api/v1/waste/",
        json={
            "disposition_date": str(date.today()),
            "waste_type": "BORINGS",
            "disposition_type": "INTERNAL_RECOVERY",
            "source_department_id": dept_ms.id,
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "50.00"},
                {"line_number": 2, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "60.00"},
            ],
        },
    )
    assert resp_unique.status_code == 201
    data_uniq = resp_unique.json()
    assert not any("Duplicate material line warning" in w for w in data_uniq["validation_warnings"])
    assert len(data_uniq["lines"]) == 2

    # 2. Two occurrences of item1 on lines 1 and 2
    resp_two = client.post(
        "/api/v1/waste/",
        json={
            "disposition_date": str(date.today()),
            "waste_type": "BORINGS",
            "disposition_type": "INTERNAL_RECOVERY",
            "source_department_id": dept_ms.id,
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "80.00"},
                {"line_number": 2, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "40.00"},
            ],
        },
    )
    assert resp_two.status_code == 201
    data_two = resp_two.json()
    assert len(data_two["lines"]) == 2
    assert Decimal(str(data_two["lines"][0]["quantity"])) == Decimal("80.0000")
    assert Decimal(str(data_two["lines"][1]["quantity"])) == Decimal("40.0000")
    dup_warnings_two = [w for w in data_two["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_two) == 1
    assert "MS-WST-010" in dup_warnings_two[0]
    assert "lines 1, 2" in dup_warnings_two[0]

    # 3. Three occurrences on lines 1, 2, 3
    resp_three = client.post(
        "/api/v1/waste/",
        json={
            "disposition_date": str(date.today()),
            "waste_type": "BORINGS",
            "disposition_type": "INTERNAL_RECOVERY",
            "source_department_id": dept_ms.id,
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "20.00"},
                {"line_number": 2, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "30.00"},
                {"line_number": 3, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "50.00"},
            ],
        },
    )
    assert resp_three.status_code == 201
    data_three = resp_three.json()
    assert len(data_three["lines"]) == 3
    dup_warnings_three = [w for w in data_three["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_three) == 1
    assert "lines 1, 2, 3" in dup_warnings_three[0]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
