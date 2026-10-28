"""
Regression tests: category filters match case-insensitively and leave stored category text unchanged.

The approved Item Master stores mixed-case categories such as 'Bolts & Nuts'. GET /api/v1/items used to
compare against category.upper() and the costing valuation endpoints compared exactly, so the same
filter value matched different items (or none) depending on the endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.item import MaterialItem
from app.models.uom import UOM

CATEGORY_ITEMS = {
    "MNT-BN-901": "Bolts & Nuts",
    "MNT-BN-902": "Bolts & Nuts",
    "FDY-RM-901": "Raw Material",
    "FDY-RM-902": "RAW_MATERIAL",  # legacy upper-case value must keep matching
}


@pytest.fixture
def mixed_case_items(db_session: Session) -> None:
    fdy = db_session.scalar(select(Department).where(Department.code == "FDY"))
    kg = db_session.scalar(select(UOM).where(UOM.code == "KG"))
    for code, category in CATEGORY_ITEMS.items():
        db_session.add(
            MaterialItem(item_code=code, name=f"Category filter {code}", department_id=fdy.id,
                         category=category, base_uom_id=kg.id)
        )
    db_session.commit()


def item_categories(client: TestClient, headers: dict, category: str) -> dict[str, str]:
    res = client.get("/api/v1/items", params={"category": category, "q": "Category filter"}, headers=headers)
    assert res.status_code == 200
    return {i["item_code"]: i["category"] for i in res.json()["items"]}


def valuation_categories(client: TestClient, headers: dict, category: str) -> dict[str, str]:
    res = client.get("/api/v1/costing/valuation/current", params={"category": category}, headers=headers)
    assert res.status_code == 200
    return {i["item_code"]: i["category"] for i in res.json()["items"] if i["item_code"] in CATEGORY_ITEMS}


@pytest.mark.parametrize("value", ["Bolts & Nuts", "bolts & nuts", "BOLTS & NUTS", "bOlTs & NuTs"])
def test_items_category_filter_is_case_insensitive(client, stores_headers, mixed_case_items, value):
    assert item_categories(client, stores_headers, value) == {
        "MNT-BN-901": "Bolts & Nuts",
        "MNT-BN-902": "Bolts & Nuts",
    }


@pytest.mark.parametrize("value", ["Bolts & Nuts", "bolts & nuts", "BOLTS & NUTS"])
def test_valuation_category_filter_is_case_insensitive(client, management_headers, mixed_case_items, value):
    assert valuation_categories(client, management_headers, value) == {
        "MNT-BN-901": "Bolts & Nuts",
        "MNT-BN-902": "Bolts & Nuts",
    }


@pytest.mark.parametrize("value", ["raw material", "Raw Material", "RAW_MATERIAL", "raw_material", "Bolts"])
def test_items_and_valuation_filters_agree(client, stores_headers, management_headers, mixed_case_items, value):
    assert item_categories(client, stores_headers, value) == valuation_categories(client, management_headers, value)


def test_distinct_category_text_is_not_merged(client, stores_headers, mixed_case_items):
    """Only case is ignored: 'Raw Material' and 'RAW_MATERIAL' remain different categories."""
    assert item_categories(client, stores_headers, "raw material") == {"FDY-RM-901": "Raw Material"}
    assert item_categories(client, stores_headers, "raw_material") == {"FDY-RM-902": "RAW_MATERIAL"}
    assert item_categories(client, stores_headers, "Bolts") == {}


def test_stored_category_text_is_unchanged(client, stores_headers, mixed_case_items, db_session):
    client.get("/api/v1/items", params={"category": "BOLTS & NUTS"}, headers=stores_headers)
    stored = dict(db_session.execute(
        select(MaterialItem.item_code, MaterialItem.category).where(MaterialItem.item_code.in_(CATEGORY_ITEMS))
    ).all())
    assert stored == CATEGORY_ITEMS
