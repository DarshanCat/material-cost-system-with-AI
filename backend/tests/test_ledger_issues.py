"""
Tests for Negative Stock Prevention & Material Issue Ledger Postings.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType


def test_issue_approval_blocked_on_uninitialized_stock(client: TestClient, db_session: Session, management_headers: dict):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    # Create uninitialized item
    item = MaterialItem(
        item_code="FDY-RM-201",
        name="Uninitialized Scrap",
        department_id=dept_fdy.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Create & submit issue slip
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
            }
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    # Approving must fail because stock is uninitialized!
    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Stock baseline has not been initialized" in app_resp.json()["detail"]


def test_issue_approval_blocked_on_insufficient_stock(client: TestClient, db_session: Session, management_headers: dict):
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-202",
        name="Limited Supply Ferro Manganese",
        department_id=dept_fdy.id,
        category="ALLOYS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Initialized with only 20 kg
    ob = StockLedgerEntry(
        entry_number="STK-TEST-202",
        posting_group_id="POST-OB-202",
        material_item_id=item.id,
        uom_id=uom_kg.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("20.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-202",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # Attempt to issue 50 kg (exceeds 20 kg)
    payload = {
        "issue_date": str(date.today()),
        "issuing_department_id": dept_fdy.id,
        "receiving_department_id": dept_ms.id,
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "50.00",
            }
        ],
    }
    resp = client.post("/api/v1/issues/", json=payload)
    assert resp.status_code == 201
    issue_id = resp.json()["id"]

    client.post(f"/api/v1/issues/{issue_id}/submit", json={})

    # Approval must be rejected with 409 Conflict
    app_resp = client.post(f"/api/v1/issues/{issue_id}/approve", json={}, headers=management_headers)
    assert app_resp.status_code == 409
    assert "Insufficient inventory" in app_resp.json()["detail"]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
