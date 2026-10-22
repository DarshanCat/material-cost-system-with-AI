"""
Tests for Waste Disposition module.
Verifies waste categories, disposition types, and supervisor approval flow.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem


def test_waste_disposition_lifecycle(client: TestClient, db_session: Session):
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="MS-BOR-001",
        name="SG Iron Machining Borings",
        department_id=dept_ms.id,
        category="RETURNS",
        base_uom_id=uom_kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # 1. Create waste disposition
    payload = {
        "disposition_date": str(date.today()),
        "waste_type": "BORINGS",
        "disposition_type": "INTERNAL_RECOVERY",
        "source_department_id": dept_ms.id,
        "destination_notes": "Transferred to foundry melting yard for remelting",
        "notes": "Weekly machine shop boring collection",
        "lines": [
            {
                "line_number": 1,
                "material_item_id": item.id,
                "uom_id": uom_kg.id,
                "quantity": "450.00",
                "reason": "Machining generation",
            }
        ],
    }

    resp = client.post("/api/v1/waste/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["waste_number"].startswith("WST-")
    waste_id = data["id"]

    # 2. Submit
    sub_resp = client.post(f"/api/v1/waste/{waste_id}/submit", json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Approve
    app_resp = client.post(f"/api/v1/waste/{waste_id}/approve", json={"comments": "Recovery verified"})
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    """Workflow tests exercise domain rules as Admin; RBAC itself is covered by test_security_routes.py."""
    client.headers.update(admin_headers)
