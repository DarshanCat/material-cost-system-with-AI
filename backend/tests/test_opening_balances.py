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
