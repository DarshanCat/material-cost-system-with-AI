"""
Tests for Physical Inventory Stock Audits.
Verifies cutoff balance comparison, variance formula (Physical - System),
draft isolation, and adjustment journal posting.
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


def test_physical_audit_variance_and_adjustment_posting(client: TestClient, db_session: Session, management_headers: dict):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-401",
        name="Silico Manganese 60/14",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # System balance in ledger = 1,000 kg
    ob = StockLedgerEntry(
        entry_number="STK-TEST-401",
        posting_group_id="POST-OB-401",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-401",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    # 1. Create audit on 2026-10-15 with physical count = 980 kg (Variance = 980 - 1000 = -20 kg)
    audit_payload = {
        "audit_date": "2026-10-15",
        "department_id": dept.id,
        "notes": "Monthly physical audit for alloy yard",
        "lines": [
            {
                "material_item_id": item.id,
                "uom_id": uom.id,
                "physical_quantity": "980.00",
                "reason": "Normal handling & weighing shrinkage",
            }
        ],
    }

    create_resp = client.post("/api/v1/physical-audits/", json=audit_payload)
    assert create_resp.status_code == 201
    audit_data = create_resp.json()
    assert audit_data["status"] == "DRAFT"
    assert Decimal(str(audit_data["lines"][0]["system_quantity"])) == Decimal("1000.0000")
    assert Decimal(str(audit_data["lines"][0]["variance"])) == Decimal("-20.0000")
    audit_id = audit_data["id"]

    # Draft audit must not change stock balance
    bal_during = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_during.json()["current_balance"])) == Decimal("1000.0000")

    # 2. Submit
    sub_resp = client.post(f"/api/v1/physical-audits/{audit_id}/submit", json={})
    assert sub_resp.status_code == 200

    # 3. Approve -> Posts adjustment to ledger
    app_resp = client.post(f"/api/v1/physical-audits/{audit_id}/approve", json={"comments": "Variance approved"}, headers=management_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Verify ledger balance is now adjusted to exactly 980 kg (1000 + (-20) = 980)
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("980.0000")
    assert bal_after.json()["movement_count"] == 2  # Opening balance + Audit adjustment


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
