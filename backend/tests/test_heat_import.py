"""
Tests for Heat Log Excel Import preview and atomic commit.
"""

from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.heat import HeatHeader


def test_heat_import_preview_and_atomic_commit(client: TestClient, db_session: Session):
    """Verifies dry-run preview, error detection, and atomic commit of heat log rows."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-020",
        name="Cast Iron Borings",
        department_id=dept.id,
        category="BORING",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    # Batch with 1 valid row and 1 invalid row (missing date and negative qty)
    rows_with_error = [
        {
            "heat_number": "102603-4001",
            "heat_date": "2026-10-21",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1200.0000",
            "uom_code": "KG",
        },
        {
            "heat_number": "102603-4002",
            "heat_date": "",  # Missing date
            "material_description": "Cast Iron Borings",
            "charged_quantity": "-500.0000",  # Negative
            "uom_code": "KG",
        }
    ]

    # Preview detects errors
    preview_resp = client.post(
        "/api/v1/heats/import/preview",
        json={"rows": rows_with_error},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert preview_resp.status_code == 200
    p_data = preview_resp.json()
    assert p_data["can_commit"] is False
    assert p_data["error_rows"] == 1
    assert p_data["valid_rows"] == 1

    # Attempting commit with errors fails (400 Bad Request)
    commit_fail = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": rows_with_error},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert commit_fail.status_code == 400

    # Valid rows commit cleanly
    valid_rows = [
        {
            "heat_number": "102603-4001",
            "heat_date": "2026-10-21",
            "furnace_id": "F-01",
            "shift": "SHIFT_A",
            "material_description": "Cast Iron Borings",
            "charged_quantity": "1200.0000",
            "uom_code": "KG",
            "part_description": "Differential Housing",
            "quantity_produced": "45.0000",
        }
    ]

    commit_resp = client.post(
        "/api/v1/heats/import/commit",
        json={"rows": valid_rows, "source_filename": "Furnace_Logs_Oct21.xlsx"},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert commit_resp.status_code == 201
    c_data = commit_resp.json()
    assert c_data["heats_created_count"] == 1
    assert "102603-4001" in c_data["heats_created"]

    # Verify heat created in database
    heat = db_session.query(HeatHeader).filter_by(heat_number="102603-4001").first()
    assert heat is not None
    assert heat.normalized_heat_number == "H-102603-4001"
    assert len(heat.charge_lines) == 1
    assert heat.charge_lines[0].material_item_id == item.id
