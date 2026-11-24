"""
Tests for Material Issue slips and validations.
Verifies heat reference normalization (H-XXXXX), line validation, and state machine.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem


def test_material_issue_workflow_and_heat_reference(client: TestClient, db_session: Session, management_headers: dict):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-AL-001",
        name="Ferro Silicon 75%",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Establish opening balance so item is initialized with sufficient stock
    from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
    ob_entry = StockLedgerEntry(
        entry_number="STK-TEST-OB-01",
        posting_group_id="POST-OB-TEST",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("500.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-TEST",
        posted_by="Admin",
    )
    db_session.add(ob_entry)
    db_session.commit()

    # 1. Create issue with raw heat number "102603-3721" (should normalize to "H-102603-3721")
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "heat_reference_number": "102603-3721",
        "notes": "Alloy charge for ladle treatment",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "25.500",
                "remarks": "Inoculation charge",
            }
        ],
    }

    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["issue_slip_number"].startswith("ISS-")
    assert data["heat_reference_number"] == "H-102603-3721"
    issue_id = data["id"]

    # 2. Submit issue slip
    sub_resp = client.post(f"/api/v1/issues/{issue_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Approve issue slip
    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"


def test_material_issue_decimal_precision_rejection(client: TestClient, db_session: Session):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_nos = db_session.query(UOM).filter_by(code="NOS").first()  # Precision = 0

    item = MaterialItem(
        item_code="FDY-CS-001",
        name="Ceramic Pouring Cup",
        department_id=dept_fdy.id,
        category="CONSUMABLES",
        base_uom_id=uom_nos.id,
    )
    db_session.add(item)
    db_session.commit()

    # Fractional quantity for discrete UOM NOS must be rejected
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_fdy.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_nos.id,
                "quantity": "12.50",  # Invalid fraction!
            }
        ],
    }

    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 422
    assert "exceeds maximum allowed decimal places (0)" in resp.json()["detail"]


def test_material_issue_intra_document_duplicate_lines_warning(client: TestClient, db_session: Session):
    """Verify duplicate material_item_id lines on an issue slip trigger non-blocking advisory warnings."""
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item1 = MaterialItem(
        item_code="FDY-AL-010",
        name="Silico Manganese 60/14",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    item2 = MaterialItem(
        item_code="FDY-AL-011",
        name="Ferro Silicon Magnesium",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # 1. Unique items produce no duplicate line warning
    resp_unique = client.post(
        "/api/v1/issues/",
        json={
            "issue_date": str(date.today()),
            "issuing_department_id": dept_fdy.id,
            "receiving_department_id": dept_ms.id,
            "heat_reference_number": "H-102603-4001",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "15.000"},
                {"line_number": 2, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "10.000"},
            ],
        },
    )
    assert resp_unique.status_code == 201
    data_uniq = resp_unique.json()
    assert not any("Duplicate material line warning" in w for w in data_uniq["validation_warnings"])
    assert len(data_uniq["lines"]) == 2

    # 2. Two occurrences of item1 on lines 1 and 2
    resp_two = client.post(
        "/api/v1/issues/",
        json={
            "issue_date": str(date.today()),
            "issuing_department_id": dept_fdy.id,
            "receiving_department_id": dept_ms.id,
            "heat_reference_number": "H-102603-4002",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "12.000"},
                {"line_number": 2, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "8.000"},
            ],
        },
    )
    assert resp_two.status_code == 201
    data_two = resp_two.json()
    assert len(data_two["lines"]) == 2
    assert Decimal(str(data_two["lines"][0]["quantity"])) == Decimal("12.0000")
    assert Decimal(str(data_two["lines"][1]["quantity"])) == Decimal("8.0000")
    dup_warnings_two = [w for w in data_two["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_two) == 1
    assert "FDY-AL-010" in dup_warnings_two[0]
    assert "lines 1, 2" in dup_warnings_two[0]

    # 3. Three occurrences on lines 1, 3, 4
    resp_three = client.post(
        "/api/v1/issues/",
        json={
            "issue_date": str(date.today()),
            "issuing_department_id": dept_fdy.id,
            "receiving_department_id": dept_ms.id,
            "heat_reference_number": "H-102603-4003",
            "lines": [
                {"line_number": 1, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "5.000"},
                {"line_number": 2, "material_item_id": item2.id, "uom_id": uom.id, "quantity": "10.000"},
                {"line_number": 3, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "7.000"},
                {"line_number": 4, "material_item_id": item1.id, "uom_id": uom.id, "quantity": "3.000"},
            ],
        },
    )
    assert resp_three.status_code == 201
    data_three = resp_three.json()
    assert len(data_three["lines"]) == 4
    dup_warnings_three = [w for w in data_three["validation_warnings"] if "Duplicate material line warning" in w]
    assert len(dup_warnings_three) == 1
    assert "lines 1, 3, 4" in dup_warnings_three[0]




def test_direct_issue_slip_workflow_and_ledger_posting(client: TestClient, db_session: Session):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-DI-001",
        name="Direct Issue Inoculant",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
    ob_entry = StockLedgerEntry(
        entry_number="STK-TEST-OB-DI",
        posting_group_id="POST-OB-DI",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("200.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-DI-TEST",
        posted_by="Admin",
    )
    db_session.add(ob_entry)
    db_session.commit()

    # 1. Create a draft issue slip
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "heat_reference_number": "H-102603-4555",
        "notes": "Direct issue test slip",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "15.000",
                "remarks": "Inoculation charge",
            }
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    draft_id = resp.json()["id"]
    assert resp.json()["status"] == "DRAFT"

    # 2. Stores directly issues it to the stock ledger via direct-issue endpoint
    resp_di = client.post(f"/api/v1/issues/{draft_id}/direct-issue", json={"comments": "Shop floor direct issue"})
    assert resp_di.status_code == 200
    issued_data = resp_di.json()
    assert issued_data["status"] == "APPROVED"

    # 3. Verify stock ledger entry was posted
    ledger_entries = db_session.query(StockLedgerEntry).filter_by(
        source_document_type=SourceDocumentType.ISSUE.value,
        source_document_id=draft_id,
    ).all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].quantity_delta == Decimal("-15.0000")


def test_issues_list_trailing_slash_contract_and_heat_filter(client: TestClient, db_session: Session):
    """
    Verifies that GET /api/v1/issues/ answers without 307 redirect,
    and supports status and heat_reference_number query filters used by HeatLogManagementView.
    """
    resp = client.get("/api/v1/issues/?status=APPROVED&heat_reference_number=H-102603-3801", follow_redirects=False)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.fixture(autouse=True)
def _authenticate_as_stores(client: TestClient, stores_headers: dict):
    """Workflow tests exercise domain rules as Stores (which has issue:create/view); RBAC itself is covered by test_security_routes.py."""
    client.headers.update(stores_headers)
