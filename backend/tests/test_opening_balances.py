"""
Tests for Opening Balances Preview & Atomic Posting.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem


def test_opening_balance_preview_and_posting_lifecycle(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-301",
        name="Foundry Steel Scrap Grade 1",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
    )
    db_session.add(item)
    db_session.commit()

    rows = [
        {
            "item_code": "FDY-RM-301",
            "quantity": "15000.00",
            "uom_code": "KG",
            "baseline_date": "2026-10-12",
            "notes": "Physical yard weighment",
        }
    ]

    # 1. Preview
    prev_resp = client.post("/api/v1/opening-balances/preview", json=rows)
    assert prev_resp.status_code == 200
    p_data = prev_resp.json()
    assert p_data["can_commit"] is True
    assert p_data["valid_rows_count"] == 1
    assert p_data["error_rows_count"] == 0

    # Ensure preview did not write to ledger
    bal_check = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert bal_check.json()["is_initialized"] is False

    # 2. Post
    post_payload = {
        "baseline_date": "2026-10-12",
        "audit_reference": "PHYS-AUD-20261012-YARD",
        "rows": rows,
        "approver_id": "PlantManager",
        "approver_comments": "Verified against signed weighbridge slips",
    }
    post_resp = client.post("/api/v1/opening-balances/post", json=post_payload)
    assert post_resp.status_code == 200
    res = post_resp.json()
    assert res["success"] is True
    assert res["posted_count"] == 1

    # Verify balance is now initialized
    bal_after = client.get(f"/api/v1/ledger/balances/{item.id}")
    assert bal_after.json()["is_initialized"] is True
    assert Decimal(str(bal_after.json()["current_balance"])) == Decimal("15000.0000")

    # 3. Duplicate opening balance for the same item must be rejected
    dup_prev = client.post("/api/v1/opening-balances/preview", json=rows)
    assert dup_prev.status_code == 200
    assert dup_prev.json()["can_commit"] is False
    assert dup_prev.json()["error_rows_count"] == 1
    assert "already has an established opening balance" in dup_prev.json()["findings"][0]["errors"][0]


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)


def test_opening_balance_rejects_inactive_item(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    inactive_item = MaterialItem(
        item_code="FDY-RM-999-INACTIVE",
        name="Retired Scrap Metal",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
        is_active=False,
    )
    db_session.add(inactive_item)
    db_session.commit()

    rows = [
        {
            "item_code": "FDY-RM-999-INACTIVE",
            "quantity": "500.00",
            "uom_code": "KG",
            "baseline_date": "2026-10-12",
        }
    ]

    prev_resp = client.post("/api/v1/opening-balances/preview", json=rows)
    assert prev_resp.status_code == 200
    p_data = prev_resp.json()
    assert p_data["can_commit"] is False
    assert any("inactive" in err.lower() for err in p_data["findings"][0]["errors"])


def test_opening_balance_rejects_uom_mismatch(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-302",
        name="Cast Iron Boring",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    rows = [
        {
            "item_code": "FDY-RM-302",
            "quantity": "500",
            "uom_code": "NOS",
            "baseline_date": "2026-10-12",
        }
    ]

    prev_resp = client.post("/api/v1/opening-balances/preview", json=rows)
    assert prev_resp.status_code == 200
    p_data = prev_resp.json()
    assert p_data["can_commit"] is False
    assert any("does not match item master base uom" in err.lower() for err in p_data["findings"][0]["errors"])


def test_opening_balance_rejects_invalid_baseline_date(client: TestClient, db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-303",
        name="Pig Iron Batch",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    rows = [
        {
            "item_code": "FDY-RM-303",
            "quantity": "1000.00",
            "uom_code": "KG",
            "baseline_date": "2026-10-15",
        }
    ]

    prev_resp = client.post("/api/v1/opening-balances/preview?baseline_date=2026-10-15", json=rows)
    assert prev_resp.status_code == 200
    p_data = prev_resp.json()
    assert p_data["can_commit"] is False
    assert any("invalid" in err.lower() and "2026-10-12" in err for err in p_data["findings"][0]["errors"])

    post_payload = {
        "baseline_date": "2026-10-15",
        "audit_reference": "PHYS-AUD-INVALID",
        "rows": rows,
        "approver_id": "PlantManager",
    }
    post_resp = client.post("/api/v1/opening-balances/post", json=post_payload)
    assert post_resp.status_code == 422
    assert "violates rule l7" in post_resp.json()["detail"].lower()


@pytest.fixture(autouse=True)
def _authenticate_as_management(client: TestClient, management_headers: dict):
    """Opening balance operations require Management permission OPENING_BALANCE_POST."""
    client.headers.update(management_headers)

