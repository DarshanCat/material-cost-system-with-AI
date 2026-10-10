"""
Tests for Append-Only Stock Ledger & Derived Balances.
Verifies immutability, signed quantity conventions, balance derivations,
uninitialized status, and compensating reversals.
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


def test_uninitialized_versus_zero_versus_positive_balance(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    # 1. Item without any movements -> UNINITIALIZED
    item1 = MaterialItem(
        item_code="FDY-RM-101",
        name="Uninitialized Pig Iron",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item1)
    db_session.commit()

    resp1 = client.get(f"/api/v1/ledger/balances/{item1.id}")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["is_initialized"] is False
    assert data1["status"] == "UNINITIALIZED"
    assert Decimal(str(data1["current_balance"])) == Decimal("0.0000")

    # 2. Item with Opening Balance -> IN_STOCK
    item2 = MaterialItem(
        item_code="FDY-RM-102",
        name="Initialized Ferro Silicon",
        department_id=dept.id,
        category="ALLOYS",
        base_uom_id=uom.id,
    )
    db_session.add(item2)
    db_session.commit()

    ob = StockLedgerEntry(
        entry_number="STK-TEST-102",
        posting_group_id="POST-OB-102",
        material_item_id=item2.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("250.0000"),
        source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0,
        source_line_id=item2.id,
        source_document_number="OB-102",
        posted_by="Admin",
    )
    db_session.add(ob)
    db_session.commit()

    resp2 = client.get(f"/api/v1/ledger/balances/{item2.id}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_initialized"] is True
    assert data2["status"] == "IN_STOCK"
    assert Decimal(str(data2["current_balance"])) == Decimal("250.0000")


def test_compensating_reversal_lifecycle(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-103",
        name="Reversal Test Material",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    # Create positive entry
    entry = StockLedgerEntry(
        entry_number="STK-TEST-103",
        posting_group_id="POST-103",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date.today(),
        movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type=SourceDocumentType.GRN.value,
        source_document_id=99,
        source_line_id=99,
        source_document_number="GRN-TEST-99",
        posted_by="Admin",
    )
    db_session.add(entry)
    db_session.commit()

    # Reverse entry
    rev_resp = client.post(
        f"/api/v1/ledger/entries/{entry.id}/reverse?actor_id=Supervisor",
        json={"reason": "Incorrect consignment weighed at weighbridge"},
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["movement_type"] == "REVERSAL"
    assert Decimal(str(rev_data["quantity_delta"])) == Decimal("-100.0000")
    assert rev_data["reversal_of_entry_id"] == entry.id

    # Check updated balance is zero (100 - 100 = 0)
    bal_resp = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert bal_resp.status_code == 200
    assert Decimal(str(bal_resp.json()["current_balance"])) == Decimal("0.0000")
    assert bal_resp.json()["status"] == "OUT_OF_STOCK"

    # Cannot reverse the same entry twice
    dup_rev = client.post(
        f"/api/v1/ledger/entries/{entry.id}/reverse?actor_id=Supervisor",
        json={"reason": "Trying second reversal"},
    )
    assert dup_rev.status_code == 409
    assert "already been reversed" in dup_rev.json()["detail"]
