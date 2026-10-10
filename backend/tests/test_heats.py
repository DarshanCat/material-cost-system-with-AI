"""
Tests for Induction Furnace Heat Log and charge details.
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.heat import HeatHeader, ProductionStatus


def test_heat_creation_and_normalization(client: TestClient, db_session: Session):
    """Verifies heat creation, reference normalization ('102603-3721' -> 'H-102603-3721'), and charge storage."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Grade A",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    payload = {
        "heat_number": "102603-3721",  # Raw without prefix
        "heat_date": "2026-10-15",
        "furnace_id": "FURNACE-1",
        "shift": "SHIFT_A",
        "metal_tapped_weight": "5000.0000",
        "metal_tapped_uom_id": uom_kg.id,
        "production_status": "COMPLETED",
        "notes": "Test heat batch",
        "charge_lines": [
            {
                "original_material_description": "Pig Iron Grade A",
                "charged_quantity": "3500.0000",
                "uom_id": uom_kg.id,
                "remarks": "Main charge",
            },
            {
                "original_material_description": "Foundry Returns",
                "charged_quantity": "1500.0000",
                "uom_id": uom_kg.id,
                "remarks": "Return scrap",
            }
        ],
        "parts_produced": [
            {
                "original_part_description": "SG Iron Differential Case",
                "quantity_produced": "120.0000",
                "unit_cast_weight": "35.5000",
                "weight_uom_id": uom_kg.id,
                "classification": "GOOD",
            }
        ]
    }

    resp = client.post("/api/v1/heats", json=payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["original_heat_number"] == "102603-3721"
    assert data["normalized_heat_number"] == "H-102603-3721"
    assert len(data["charge_lines"]) == 2
    assert len(data["parts_produced"]) == 1
    assert Decimal(str(data["charge_lines"][0]["charged_quantity"])) == Decimal("3500.0000")
    # First charge line resolved to item
    assert data["charge_lines"][0]["material_item_id"] == item.id


def test_duplicate_heat_prevention(client: TestClient, db_session: Session):
    """Verifies that duplicate heat numbers (both raw and normalized collisions) are rejected with 409 Conflict."""
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    payload = {
        "heat_number": "H-102603-3722",
        "heat_date": "2026-10-15",
        "charge_lines": [
            {
                "original_material_description": "Test Material",
                "charged_quantity": "100.0000",
                "uom_id": uom_kg.id,
            }
        ]
    }

    resp1 = client.post("/api/v1/heats", json=payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp1.status_code == 201

    # Exact duplicate
    resp2 = client.post("/api/v1/heats", json=payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp2.status_code == 409

    # Normalized collision without prefix: '102603-3722' resolves to 'H-102603-3722'
    payload_colliding = {
        "heat_number": "102603-3722",
        "heat_date": "2026-10-15",
        "charge_lines": [
            {
                "original_material_description": "Test Material",
                "charged_quantity": "100.0000",
                "uom_id": uom_kg.id,
            }
        ]
    }
    resp3 = client.post("/api/v1/heats", json=payload_colliding, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp3.status_code == 409


def test_heat_charge_positive_quantity_enforcement(client: TestClient, db_session: Session):
    """Verifies that non-positive quantities in heat charge lines are rejected."""
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    payload = {
        "heat_number": "H-102603-3723",
        "heat_date": "2026-10-15",
        "charge_lines": [
            {
                "original_material_description": "Invalid Material",
                "charged_quantity": "0.0000",
                "uom_id": uom_kg.id,
            }
        ]
    }

    resp = client.post("/api/v1/heats", json=payload, headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"})
    assert resp.status_code == 422
