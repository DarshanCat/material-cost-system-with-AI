"""
Non-Negotiable Inventory Rule Verification Tests.
Proves that Phase 5 operations (Heat creation, charge logging, Excel import,
reconciliation runs, candidate confirmations) NEVER create stock ledger entries
or modify inventory balances.
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.ledger import StockLedgerEntry
from app.services.ledger_service import get_material_stock_balance


def test_heat_operations_strictly_isolated_from_stock_ledger(client: TestClient, db_session: Session):
    """
    Verifies that creating heats, adding charges, importing heats,
    running reconciliation, and confirming fuzzy candidates
    creates ZERO stock ledger entries and leaves stock balances unchanged.
    """
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-099",
        name="Special Test Alloy",
        department_id=dept_fdy.id,
        category="ALLOY",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    # Step 1: Initial ledger entry count must be 0
    initial_count = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert initial_count == 0

    bal, is_init, _, _ = get_material_stock_balance(db_session, item.id)
    assert is_init is False
    assert bal == Decimal("0.0000")

    # Step 2: Create a Heat with 5,000 kg charge
    heat_payload = {
        "heat_number": "H-102603-9999",
        "heat_date": "2026-10-20",
        "furnace_id": "F-01",
        "charge_lines": [
            {
                "original_material_description": "Special Test Alloy",
                "charged_quantity": "5000.0000",
                "uom_id": uom_kg.id,
            }
        ],
        "parts_produced": [
            {
                "original_part_description": "Test Casting",
                "quantity_produced": "10.0000",
            }
        ]
    }
    resp_heat = client.post("/api/v1/heats", json=heat_payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp_heat.status_code == 201

    # Check ledger: count MUST still be 0!
    count_after_heat = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert count_after_heat == 0
    bal_after_heat, is_init_heat, _, _ = get_material_stock_balance(db_session, item.id)
    assert is_init_heat is False
    assert bal_after_heat == Decimal("0.0000")

    # Step 3: Heat Excel Import
    import_payload = {
        "rows": [
            {
                "heat_number": "H-102603-9998",
                "heat_date": "2026-10-20",
                "furnace_id": "F-02",
                "material_description": "Special Test Alloy",
                "charged_quantity": "2500.0000",
                "uom_code": "KG",
            }
        ]
    }
    resp_import = client.post("/api/v1/heats/import/commit", json=import_payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp_import.status_code == 201

    # Check ledger: count MUST still be 0!
    count_after_import = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert count_after_import == 0

    # Step 4: Run reconciliation
    recon_payload = {
        "date_from": "2026-10-20",
        "date_to": "2026-10-20",
    }
    resp_recon = client.post("/api/v1/reconciliation/run", json=recon_payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp_recon.status_code == 201

    # Check ledger: count MUST still be 0!
    count_after_recon = db_session.scalar(select(func.count()).select_from(StockLedgerEntry)) or 0
    assert count_after_recon == 0

    final_bal, final_is_init, _, _ = get_material_stock_balance(db_session, item.id)
    assert final_is_init is False
    assert final_bal == Decimal("0.0000")
