from tests.auth_helpers import bearer
"""
Tests for Material Description Alias Master.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.material_alias import MaterialAlias, AliasApprovalStatus
from app.services.material_alias_service import resolve_material_by_description


def test_alias_creation_and_resolution(client: TestClient, db_session: Session):
    """Verifies creating an alias and resolving diverse raw descriptions."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-002",
        name="CRC Scrap High Manganese",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    # Create alias: 'CRC Scrap-Low High MN' -> maps to item
    payload = {
        "alias_text": "CRC Scrap-Low High MN",
        "material_item_id": item.id,
        "status": "APPROVED",
    }
    resp = client.post("/api/v1/material-aliases", json=payload, headers=bearer("Stores"))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["normalized_alias_key"] == "crc scrap low high mn"

    # Test resolution helper
    resolved = resolve_material_by_description(db_session, "CRC Scrap-Low High MN")
    assert resolved is not None
    assert resolved.id == item.id

    # Test resolution with minor spacing/case differences
    resolved2 = resolve_material_by_description(db_session, "  crc  scrap-low high mn  ")
    assert resolved2 is not None
    assert resolved2.id == item.id


def test_ambiguous_alias_collision_prevention(client: TestClient, db_session: Session):
    """Verifies that mapping the same alias text to two different material items is blocked (409 Conflict)."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item1 = MaterialItem(
        item_code="FDY-RM-003",
        name="Steel Scrap Standard",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    item2 = MaterialItem(
        item_code="FDY-RM-004",
        name="Steel Scrap High Silicon",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # First mapping succeeds
    payload1 = {
        "alias_text": "Steel Scrap Mixed",
        "material_item_id": item1.id,
        "status": "APPROVED",
    }
    resp1 = client.post("/api/v1/material-aliases", json=payload1, headers=bearer("Stores"))
    assert resp1.status_code == 201

    # Second mapping with same alias key to item2 must fail
    payload2 = {
        "alias_text": "steel-scrap mixed",
        "material_item_id": item2.id,
        "status": "APPROVED",
    }
    resp2 = client.post("/api/v1/material-aliases", json=payload2, headers=bearer("Stores"))
    assert resp2.status_code == 409
    assert "Ambiguous multi-item aliases are prohibited" in resp2.json()["detail"]


def test_alias_rejection_requires_mandatory_comments(client: TestClient, db_session: Session):
    """Verifies that rejecting an alias requires a non-empty explanation comment."""
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-005",
        name="Inoculant FeSi 75",
        department_id=dept.id,
        category="ALLOY",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    alias = MaterialAlias(
        alias_text="FeSi Inoculant",
        normalized_alias_key="fesi inoculant",
        material_item_id=item.id,
        status="PENDING",
        created_by="usr_fdy",
    )
    db_session.add(alias)
    db_session.commit()

    # Reject without comments fails
    resp_empty = client.post(
        f"/api/v1/material-aliases/{alias.id}/reject",
        json={"decision_notes": ""},
        headers=bearer("Management"),
    )
    assert resp_empty.status_code == 422 or resp_empty.status_code == 400

    # Reject with valid comments succeeds
    resp_valid = client.post(
        f"/api/v1/material-aliases/{alias.id}/reject",
        json={"decision_notes": "Incorrect mesh size classification, please map to FeSi 70"},
        headers=bearer("Management"),
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["status"] == "REJECTED"
