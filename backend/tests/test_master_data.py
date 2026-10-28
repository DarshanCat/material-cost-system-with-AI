import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.item_code import ItemMasterAuditLog
from app.services.item_code_service import ItemCodeService


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
    """Verify v1.0 item code format DEPT-CAT-### (e.g. FDY-RM-001, FDY-RM-002) from the allocator."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))
    service = ItemCodeService(db_session)

    code1, serial1 = service.allocate_code("FDY", "RM")
    assert (code1, serial1) == ("FDY-RM-001", 1)

    # Insert item with code1
    item = MaterialItem(
        item_code=code1,
        name="Pig Iron Batch A",
        department_id=fdy.id,
        category="Raw Material",
        base_uom_id=kg.id,
    )
    db_session.add(item)
    db_session.commit()

    # Next serial should be 002
    code2, _ = service.allocate_code("FDY", "RM")
    assert code2 == "FDY-RM-002"
    db_session.rollback()


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
    """Verify item categories endpoint returns the 15 Nomenclature Standard v1.0 categories."""
    res = client.get("/api/v1/items/categories", headers=stores_headers)
    assert res.status_code == 200
    cats = res.json()
    assert {c["code"] for c in cats} == {
        "RM", "LN", "MD", "CN", "PT", "CB", "IT", "OL", "BR", "BL", "BN", "QC", "PK", "FU", "SF",
    }
    # Legacy (pre-v1.0) categories are no longer offered
    assert not {"RAW_MATERIAL", "ALLOY", "CONSUMABLE", "RETURN", "BORING", "GATING"} & {c["category"] for c in cats}

    # Check structure: `category` is the stored text used by the GET /items category filter
    rm = next(c for c in cats if c["code"] == "RM")
    assert rm["category"] == "Raw Material"
    assert rm["name"] == "Raw Material"
    assert rm["department_code"] == "FDY"
    assert rm["cost_head"] == "Material Cost"
    bn = next(c for c in cats if c["code"] == "BN")
    assert (bn["category"], bn["department_code"], bn["cost_head"]) == ("Bolts & Nuts", "MNT", "Maintenance Cost")


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

    # 1. Update metadata and retire; retiring requires a recorded reason
    update_payload = {
        "subcategory": "GRADE_A_PLUS",
        "description": "High-purity foundry pig iron for ductile iron production",
        "is_active": False,
    }
    no_reason = client.put(f"/api/v1/items/{item.id}", json=update_payload, headers=management_headers)
    assert no_reason.status_code == 400
    assert "change_reason" in no_reason.json()["detail"]

    update_payload["change_reason"] = "Superseded by grade B pig iron."
    res = client.put(f"/api/v1/items/{item.id}", json=update_payload, headers=management_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["subcategory"] == "GRADE_A_PLUS"
    assert data["description"] == update_payload["description"]
    assert data["is_active"] is False
    assert data["item_code"] == "FDY-RM-099"  # Immutable code preserved

    # 2. Reactivate (reason required)
    res_reactivate = client.put(
        f"/api/v1/items/{item.id}",
        json={"is_active": True, "change_reason": "Grade B supply discontinued."},
        headers=management_headers,
    )
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["is_active"] is True

    # Every change is in the append-only item history, attributed to the verified actor
    history = client.get(f"/api/v1/items/{item.id}/history", headers=management_headers).json()
    actions = [(e["action"], e["field_name"]) for e in history["events"]]
    assert ("RETIRED", "is_active") in actions
    assert ("REACTIVATED", "is_active") in actions
    assert ("METADATA_UPDATED", "subcategory") in actions
    assert history["registry"] is None  # legacy item: created outside the generator
    assert db_session.query(ItemMasterAuditLog).filter_by(material_item_id=item.id, action="RETIRED").one().reason == (
        "Superseded by grade B pig iron."
    )

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


def test_items_response_envelope_and_limit_alias(
    client: TestClient,
    db_session: Session,
    stores_headers: dict,
):
    """Verify GET /api/v1/items returns PaginatedItemsResponse envelope and supports limit alias."""
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))

    for i in range(5):
        db_session.add(
            MaterialItem(
                item_code=f"FDY-RM-90{i}",
                name=f"Envelope Test Item {i}",
                department_id=fdy.id,
                category="RAW_MATERIAL",
                base_uom_id=kg.id,
            )
        )
    db_session.commit()

    # 1. Verify PaginatedItemsResponse contract shape
    res = client.get("/api/v1/items?q=Envelope+Test", headers=stores_headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, dict), "Response must be an envelope object, not a bare list"
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "size" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 5

    # 2. Verify limit parameter acts as alias for size and supports up to 1000
    res_limit = client.get("/api/v1/items?limit=500", headers=stores_headers)
    assert res_limit.status_code == 200
    body_limit = res_limit.json()
    assert body_limit["size"] == 500
    assert isinstance(body_limit["items"], list)

    # 3. Verify size query parameter supports up to 1000 without 422
    res_size = client.get("/api/v1/items?size=500", headers=stores_headers)
    assert res_size.status_code == 200
    assert res_size.json()["size"] == 500


def test_vendors_response_supports_large_page_size(
    client: TestClient,
    stores_headers: dict,
):
    """Verify GET /api/v1/vendors supports size up to 1000 for dropdowns."""
    res = client.get("/api/v1/vendors?size=200", headers=stores_headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, dict)
    assert "items" in body
    assert body["size"] == 200
