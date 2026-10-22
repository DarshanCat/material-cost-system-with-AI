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


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
