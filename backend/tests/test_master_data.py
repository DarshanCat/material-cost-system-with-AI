import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.services.item_request_service import ItemRequestService


def test_seed_departments_and_uoms(db_session: Session):
    """Verify the 8 required departments and standard UOMs with precision are seeded."""
    departments = db_session.scalars(select(Department)).all()
    assert len(departments) == 8

    dept_names = {d.name for d in departments}
    expected_names = {
        "Foundry",
        "Machine Shop",
        "Maintenance",
        "General/Stores",
        "Packing",
        "Quality",
        "F3 HMC",
        "F3 CNC",
    }
    assert dept_names == expected_names

    dept_codes = {d.code for d in departments}
    assert dept_codes == {"FDY", "MSP", "MNT", "GNS", "PKG", "QLT", "HMC", "CNC"}

    # Verify UOM precision rules
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))
    assert kg is not None
    assert kg.decimal_precision == 4

    nos = db_session.scalar(select(UOM).where(UOM.code == "NOS"))
    assert nos is not None
    assert nos.decimal_precision == 0

    ltr = db_session.scalar(select(UOM).where(UOM.code == "LTR"))
    assert ltr is not None
    assert ltr.decimal_precision == 3


def test_material_item_code_uniqueness(db_session: Session):
    """Verify item code duplicate constraint at the database level."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))

    item1 = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Grade 1",
        department_id=fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=kg.id,
        is_active=True,
    )
    db_session.add(item1)
    db_session.commit()

    # Attempt inserting duplicate item code
    item2 = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Grade 1 Duplicate",
        department_id=fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=kg.id,
        is_active=True,
    )
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_item_code_generation_convention(db_session: Session):
    """Verify item code format: DEPT-CATEGORY-SERIAL (e.g. FDY-RM-001, FDY-RM-002)."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))
    service = ItemRequestService(db_session)

    code1 = service.generate_next_item_code(fdy.id, "RAW_MATERIAL")
    assert code1 == "FDY-RM-001"

    # Insert item with code1
    item = MaterialItem(
        item_code=code1,
        name="Pig Iron Batch A",
        department_id=fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Next serial should be 002
    code2 = service.generate_next_item_code(fdy.id, "RAW_MATERIAL")
    assert code2 == "FDY-RM-002"


def test_api_list_departments_and_uoms(client: TestClient, stores_headers: dict):
    """Verify department and UOM listing endpoints."""
    res_depts = client.get("/api/v1/departments", headers=stores_headers)
    assert res_depts.status_code == 200
    depts = res_depts.json()
    assert len(depts) == 8

    res_uoms = client.get("/api/v1/uoms", headers=stores_headers)
    assert res_uoms.status_code == 200
    uoms = res_uoms.json()
    assert len(uoms) >= 7
    # Verify decimal precision is returned
    kg_entry = next((u for u in uoms if u["code"] == "KG"), None)
    assert kg_entry is not None
    assert kg_entry["decimal_precision"] == 4



def test_api_list_categories(client: TestClient, stores_headers: dict):
    """Verify item categories endpoint returns standard foundry categories."""
    res = client.get("/api/v1/items/categories", headers=stores_headers)
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) >= 6
    cat_keys = {c["category"] for c in cats}
    assert "RAW_MATERIAL" in cat_keys
    assert "ALLOY" in cat_keys
    assert "CONSUMABLE" in cat_keys
    assert "RETURN" in cat_keys
    assert "BORING" in cat_keys
    assert "GATING" in cat_keys

    # Check structure
    rm = next(c for c in cats if c["category"] == "RAW_MATERIAL")
    assert rm["code"] == "RM"
    assert rm["name"] == "Raw Material"


def test_api_update_item_metadata(
    client: TestClient,
    db_session: Session,
    management_headers: dict,
):
    """Verify updating item description, subcategory, active status, and duplicate name check."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))

    item = MaterialItem(
        item_code="FDY-RM-099",
        name="SG Pig Iron Standard",
        department_id=fdy.id,
        category="RAW_MATERIAL",
        subcategory="GRADE_A",
        base_uom_id=kg.id,
        description="Initial description",
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    # 1. Update metadata
    update_payload = {
        "subcategory": "GRADE_A_PLUS",
        "description": "High-purity foundry pig iron for ductile iron production",
        "is_active": False,
    }
    res = client.put(f"/api/v1/items/{item.id}", json=update_payload, headers=management_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["subcategory"] == "GRADE_A_PLUS"
    assert data["description"] == update_payload["description"]
    assert data["is_active"] is False
    assert data["item_code"] == "FDY-RM-099"  # Immutable code preserved

    # 2. Reactivate
    res_reactivate = client.put(f"/api/v1/items/{item.id}", json={"is_active": True}, headers=management_headers)
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["is_active"] is True

    # 3. Create second item in same department and verify duplicate name rejection
    item2 = MaterialItem(
        item_code="FDY-RM-100",
        name="Cast Scrap Grade 1",
        department_id=fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=kg.id,
        is_active=True,
    )
    db_session.add(item2)
    db_session.commit()

    # Attempt renaming item2 to item1's name -> 409 Conflict
    dup_res = client.put(
        f"/api/v1/items/{item2.id}",
        json={"name": "SG Pig Iron Standard"},
        headers=management_headers,
    )
    assert dup_res.status_code == 409
    assert "already exists in this department" in dup_res.json()["detail"]


def test_item_update_permissions(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
    foundry_headers: dict,
    purchase_headers: dict,
    management_headers: dict,
    admin_headers: dict,
):
    """Verify only MANAGEMENT and ADMIN can update item metadata."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))

    item = MaterialItem(
        item_code="FDY-CON-050",
        name="Foundry Ladle Shroud",
        department_id=fdy.id,
        category="CONSUMABLE",
        base_uom_id=kg.id,
    )
    db_session.add(item)
    db_session.commit()

    payload = {"description": "Updated spec"}

    # Unauthorized roles -> 403
    assert client.put(f"/api/v1/items/{item.id}", json=payload, headers=stores_headers).status_code == 403
    assert client.put(f"/api/v1/items/{item.id}", json=payload, headers=foundry_headers).status_code == 403
    assert client.put(f"/api/v1/items/{item.id}", json=payload, headers=purchase_headers).status_code == 403

    # Authorized roles -> 200
    assert client.put(f"/api/v1/items/{item.id}", json=payload, headers=management_headers).status_code == 200
    assert client.put(f"/api/v1/items/{item.id}", json=payload, headers=admin_headers).status_code == 200
