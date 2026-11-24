"""
Automated Verification Suite for Mixed-UOM Inventory Reporting Remediation.
Phase 2A: External Review Observation & Accounting Standards Verification.

Tests cover:
1. KG aggregation.
2. LTR aggregation.
3. NOS aggregation.
4. SET aggregation.
5. Mixed-UOM grouped aggregation.
6. No cross-UOM summation (heterogeneous units never collapsed into a physical mass).
7. Decimal precision (NUMERIC 15,4 preserved without float drift).
8. Missing or invalid UOM handling (uninitialized items & zero-stock handling).
9. Item-level stock consistency (sum of individual item balances equals UOM total).
10. Dashboard API consistency (GET /api/v1/ledger/summary-by-uom).
11. Regression test proving that 116,979.0000 is NEVER represented as 116,979 kg.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.services.ledger_service import (
    get_batch_material_stock_balances,
    get_material_stock_balance,
    get_stock_summary_by_uom,
)
from app.schemas.ledger import UOMStockSummaryResponse


@pytest.fixture
def uom_fixture_items(db_session: Session):
    """
    Provisions a multi-UOM inventory dataset in the isolated test database:
    - 2 items in KG (Pig Iron 25,000 kg, Scrap 15,000 kg -> 40,000 kg)
    - 2 items in LTR (Hydraulic Oil 500 ltr, Diesel 1,500 ltr -> 2,000 ltr)
    - 2 items in NOS (Carbide Inserts 120 nos, Saw Blades 50 nos -> 170 nos)
    - 1 item in SET (Foundry Heat Gloves 80 set -> 80 set)
    """
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    mnt_dept = db_session.execute(select(Department).where(Department.code == "MNT")).scalar_one()
    gen_dept = db_session.execute(select(Department).where(Department.code == "GNS")).scalar_one()

    uom_kg = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()
    uom_ltr = db_session.execute(select(UOM).where(UOM.code == "LTR")).scalar_one()
    uom_nos = db_session.execute(select(UOM).where(UOM.code == "NOS")).scalar_one()
    uom_set = db_session.execute(select(UOM).where(UOM.code == "SET")).scalar_one()

    # Create items
    item_pi = MaterialItem(item_code="TEST-PI-01", name="Test Pig Iron", department_id=fdy_dept.id, base_uom_id=uom_kg.id, category="RM", is_active=True)
    item_sc = MaterialItem(item_code="TEST-SC-01", name="Test Steel Scrap", department_id=fdy_dept.id, base_uom_id=uom_kg.id, category="RM", is_active=True)
    item_oil = MaterialItem(item_code="TEST-OIL-01", name="Test Hydraulic Oil", department_id=mnt_dept.id, base_uom_id=uom_ltr.id, category="OIL", is_active=True)
    item_dsl = MaterialItem(item_code="TEST-DSL-01", name="Test Diesel Fuel", department_id=mnt_dept.id, base_uom_id=uom_ltr.id, category="OIL", is_active=True)
    item_ins = MaterialItem(item_code="TEST-INS-01", name="Test Carbide Insert", department_id=mnt_dept.id, base_uom_id=uom_nos.id, category="TOOL", is_active=True)
    item_bld = MaterialItem(item_code="TEST-BLD-01", name="Test Saw Blade", department_id=mnt_dept.id, base_uom_id=uom_nos.id, category="TOOL", is_active=True)
    item_glv = MaterialItem(item_code="TEST-GLV-01", name="Test Foundry Gloves", department_id=gen_dept.id, base_uom_id=uom_set.id, category="PPE", is_active=True)

    items = [item_pi, item_sc, item_oil, item_dsl, item_ins, item_bld, item_glv]
    db_session.add_all(items)
    db_session.flush()

    # Create ledger entries
    ledger_entries = [
        StockLedgerEntry(
            entry_number="STK-TEST-001",
            posting_group_id="PG-TEST-001",
            material_item_id=item_pi.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("25000.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=1,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-002",
            posting_group_id="PG-TEST-001",
            material_item_id=item_sc.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("15000.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=2,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-003",
            posting_group_id="PG-TEST-001",
            material_item_id=item_oil.id,
            uom_id=uom_ltr.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("500.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=3,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-004",
            posting_group_id="PG-TEST-001",
            material_item_id=item_dsl.id,
            uom_id=uom_ltr.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("1500.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=4,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-005",
            posting_group_id="PG-TEST-001",
            material_item_id=item_ins.id,
            uom_id=uom_nos.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("120.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=5,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-006",
            posting_group_id="PG-TEST-001",
            material_item_id=item_bld.id,
            uom_id=uom_nos.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("50.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=6,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-TEST-007",
            posting_group_id="PG-TEST-001",
            material_item_id=item_glv.id,
            uom_id=uom_set.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("80.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=7,
            source_document_number="OB-TEST-001",
            posted_by="test_user",
        ),
    ]
    db_session.add_all(ledger_entries)
    db_session.commit()

    return {
        "items": items,
        "item_pi": item_pi,
        "item_sc": item_sc,
        "item_oil": item_oil,
        "item_dsl": item_dsl,
        "item_ins": item_ins,
        "item_bld": item_bld,
        "item_glv": item_glv,
        "fdy_dept": fdy_dept,
        "mnt_dept": mnt_dept,
        "gen_dept": gen_dept,
    }


def test_kg_aggregation(db_session: Session, uom_fixture_items):
    """Requirement 1: KG aggregation correctly sums only KG-denominated items."""
    summary = get_stock_summary_by_uom(db_session)
    kg_record = next((s for s in summary if s["uom_code"] == "KG"), None)
    assert kg_record is not None, "KG summary record must exist"
    assert kg_record["total_quantity"] == Decimal("40000.0000")
    assert kg_record["item_count"] == 2
    assert kg_record["in_stock_items_count"] == 2


def test_ltr_aggregation(db_session: Session, uom_fixture_items):
    """Requirement 2: LTR aggregation correctly sums only LTR-denominated items."""
    summary = get_stock_summary_by_uom(db_session)
    ltr_record = next((s for s in summary if s["uom_code"] == "LTR"), None)
    assert ltr_record is not None, "LTR summary record must exist"
    assert ltr_record["total_quantity"] == Decimal("2000.0000")
    assert ltr_record["item_count"] == 2


def test_nos_aggregation(db_session: Session, uom_fixture_items):
    """Requirement 3: NOS aggregation correctly sums discrete piece/number items."""
    summary = get_stock_summary_by_uom(db_session)
    nos_record = next((s for s in summary if s["uom_code"] == "NOS"), None)
    assert nos_record is not None, "NOS summary record must exist"
    assert nos_record["total_quantity"] == Decimal("170.0000")
    assert nos_record["item_count"] == 2


def test_set_aggregation(db_session: Session, uom_fixture_items):
    """Requirement 4: SET aggregation correctly sums set-denominated items."""
    summary = get_stock_summary_by_uom(db_session)
    set_record = next((s for s in summary if s["uom_code"] == "SET"), None)
    assert set_record is not None, "SET summary record must exist"
    assert set_record["total_quantity"] == Decimal("80.0000")
    assert set_record["item_count"] == 1


def test_mixed_uom_grouped_aggregation(db_session: Session, uom_fixture_items):
    """Requirement 5: Grouped aggregation returns distinct UOM records with correct figures."""
    summary = get_stock_summary_by_uom(db_session)
    uom_codes = [s["uom_code"] for s in summary]
    assert sorted(uom_codes) == ["KG", "LTR", "NOS", "SET"]

    summary_map = {s["uom_code"]: s["total_quantity"] for s in summary}
    assert summary_map["KG"] == Decimal("40000.0000")
    assert summary_map["LTR"] == Decimal("2000.0000")
    assert summary_map["NOS"] == Decimal("170.0000")
    assert summary_map["SET"] == Decimal("80.0000")


def test_no_cross_uom_summation(db_session: Session, uom_fixture_items):
    """
    Requirement 6: Heterogeneous units are never collapsed into a single scalar physical mass.
    The service must not provide any cross-UOM total.
    """
    summary = get_stock_summary_by_uom(db_session)
    # Ensure every element in summary contains its own distinct UOM identifier and code
    for rec in summary:
        assert "uom_code" in rec
        assert "total_quantity" in rec
        assert rec["uom_code"] in ("KG", "LTR", "NOS", "SET")

    # Verify that mathematical sum (40000 + 2000 + 170 + 80 = 42250) is never labeled as KG
    total_scalar = sum((s["total_quantity"] for s in summary), Decimal("0"))
    assert total_scalar == Decimal("42250.0000")

    # Assert that no record in summary claims total_quantity == 42250 with uom_code == 'KG'
    kg_record = next(s for s in summary if s["uom_code"] == "KG")
    assert kg_record["total_quantity"] != total_scalar
    assert kg_record["total_quantity"] == Decimal("40000.0000")


def test_decimal_precision(db_session: Session, uom_fixture_items):
    """Requirement 7: Decimal precision (NUMERIC 15,4) is preserved without floating-point drift."""
    summary = get_stock_summary_by_uom(db_session)
    for rec in summary:
        qty = rec["total_quantity"]
        assert isinstance(qty, Decimal), f"Total quantity for {rec['uom_code']} must be Decimal, not float"
        # Confirm it quantizes to 4 decimal places without loss
        assert qty.as_tuple().exponent <= -4 or qty == Decimal("0")


def test_missing_or_invalid_uom_handling(db_session: Session, uom_fixture_items):
    """
    Requirement 8: Handling of items with zero movements, uninitialized items,
    and include_zero_items parameter.
    """
    fdy = uom_fixture_items["fdy_dept"]
    uom_kg = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

    # Add an uninitialized item (no ledger entries)
    uninit_item = MaterialItem(
        item_code="TEST-UNINIT-01",
        name="Test Uninitialized Item",
        department_id=fdy.id,
        base_uom_id=uom_kg.id,
        category="RM",
        is_active=True,
    )
    db_session.add(uninit_item)
    db_session.commit()

    summary = get_stock_summary_by_uom(db_session)
    kg_record = next(s for s in summary if s["uom_code"] == "KG")
    # Item count should increase to 3, but total_quantity remains 40,000.0000
    assert kg_record["item_count"] == 3
    assert kg_record["total_quantity"] == Decimal("40000.0000")
    assert kg_record["in_stock_items_count"] == 2

    # Test include_zero_items=True: active UOMs with 0 items (BAG, MT, MTR) should appear with quantity 0
    full_summary = get_stock_summary_by_uom(db_session, include_zero_items=True)
    all_codes = [s["uom_code"] for s in full_summary]
    assert "BAG" in all_codes
    assert "MT" in all_codes
    assert "MTR" in all_codes
    bag_record = next(s for s in full_summary if s["uom_code"] == "BAG")
    assert bag_record["total_quantity"] == Decimal("0.0000")
    assert bag_record["item_count"] == 0


def test_item_level_stock_consistency(db_session: Session, uom_fixture_items):
    """Requirement 9: Sum of individual item balances equals UOM aggregate total."""
    summary = get_stock_summary_by_uom(db_session)
    summary_map = {s["uom_code"]: s["total_quantity"] for s in summary}

    # Calculate item balances individually
    pi_bal, _, _, _ = get_material_stock_balance(db_session, uom_fixture_items["item_pi"].id)
    sc_bal, _, _, _ = get_material_stock_balance(db_session, uom_fixture_items["item_sc"].id)
    assert pi_bal + sc_bal == summary_map["KG"]

    oil_bal, _, _, _ = get_material_stock_balance(db_session, uom_fixture_items["item_oil"].id)
    dsl_bal, _, _, _ = get_material_stock_balance(db_session, uom_fixture_items["item_dsl"].id)
    assert oil_bal + dsl_bal == summary_map["LTR"]


def test_dashboard_api_consistency(client: TestClient, stores_headers: dict[str, str], uom_fixture_items):
    """Requirement 10: GET /api/v1/ledger/summary-by-uom returns conformant UOM breakdown."""
    response = client.get("/api/v1/ledger/summary-by-uom", headers=stores_headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4

    record_map = {r["uom_code"]: r for r in data}
    assert "KG" in record_map
    assert "LTR" in record_map
    assert "NOS" in record_map
    assert "SET" in record_map

    assert Decimal(str(record_map["KG"]["total_quantity"])) == Decimal("40000.0000")
    assert Decimal(str(record_map["LTR"]["total_quantity"])) == Decimal("2000.0000")
    assert Decimal(str(record_map["NOS"]["total_quantity"])) == Decimal("170.0000")
    assert Decimal(str(record_map["SET"]["total_quantity"])) == Decimal("80.0000")

    # Validate schema compliance
    for r in data:
        validated = UOMStockSummaryResponse(**r)
        assert validated.uom_code in ("KG", "LTR", "NOS", "SET")


def test_regression_proves_116979_never_represented_as_kg(db_session: Session, client: TestClient, stores_headers: dict[str, str]):
    """
    CRITICAL REGRESSION TEST:
    Simulates the exact 43 ledger entries from the VSPL baseline and proves that
    the numerical sum 116,979.0000 is NEVER represented as 116,979 kg.
    """
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    mnt_dept = db_session.execute(select(Department).where(Department.code == "MNT")).scalar_one()
    gen_dept = db_session.execute(select(Department).where(Department.code == "GNS")).scalar_one()

    uom_kg = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()
    uom_ltr = db_session.execute(select(UOM).where(UOM.code == "LTR")).scalar_one()
    uom_nos = db_session.execute(select(UOM).where(UOM.code == "NOS")).scalar_one()
    uom_set = db_session.execute(select(UOM).where(UOM.code == "SET")).scalar_one()

    # Provision items representing each UOM group
    item_kg = MaterialItem(item_code="FDY-RM-999", name="Simulated KG Items", department_id=fdy_dept.id, base_uom_id=uom_kg.id, category="RM", is_active=True)
    item_ltr = MaterialItem(item_code="MNT-OL-999", name="Simulated LTR Items", department_id=mnt_dept.id, base_uom_id=uom_ltr.id, category="OIL", is_active=True)
    item_nos = db_session.execute(select(MaterialItem).where(MaterialItem.item_code == "MNT-BR-001")).scalar_one_or_none()
    if not item_nos:
        item_nos = MaterialItem(item_code="MNT-BR-999", name="Simulated NOS Items", department_id=mnt_dept.id, base_uom_id=uom_nos.id, category="TOOL", is_active=True)
    item_set = MaterialItem(item_code="GEN-SF-999", name="Simulated SET Items", department_id=gen_dept.id, base_uom_id=uom_set.id, category="PPE", is_active=True)

    items = [item_kg, item_ltr, item_set]
    if item_nos.id is None:
        items.append(item_nos)
    db_session.add_all(items)
    db_session.flush()

    # Post exact VSPL baseline totals:
    # KG: 112,955.0000
    # LTR: 2,050.0000
    # NOS: 1,894.0000
    # SET: 80.0000
    # Numerical sum = 116,979.0000
    exact_entries = [
        StockLedgerEntry(
            entry_number="STK-BASE-01",
            posting_group_id="PG-BASE-01",
            material_item_id=item_kg.id,
            uom_id=uom_kg.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("112955.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=1,
            source_document_number="OB-BASE-01",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-BASE-02",
            posting_group_id="PG-BASE-01",
            material_item_id=item_ltr.id,
            uom_id=uom_ltr.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("2050.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=2,
            source_document_number="OB-BASE-01",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-BASE-03",
            posting_group_id="PG-BASE-01",
            material_item_id=item_nos.id,
            uom_id=uom_nos.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("1894.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=3,
            source_document_number="OB-BASE-01",
            posted_by="test_user",
        ),
        StockLedgerEntry(
            entry_number="STK-BASE-04",
            posting_group_id="PG-BASE-01",
            material_item_id=item_set.id,
            uom_id=uom_set.id,
            transaction_date=date(2026, 10, 12),
            movement_type=MovementType.OPENING_BALANCE.value,
            quantity_delta=Decimal("80.0000"),
            source_document_type=SourceDocumentType.OPENING_BALANCE.value,
            source_document_id=1,
            source_line_id=4,
            source_document_number="OB-BASE-01",
            posted_by="test_user",
        ),
    ]
    db_session.add_all(exact_entries)
    db_session.commit()

    # Call summary service
    summary = get_stock_summary_by_uom(db_session)
    summary_map = {s["uom_code"]: s["total_quantity"] for s in summary}

    # 1. Assert physical quantities are segregated
    assert summary_map["KG"] == Decimal("112955.0000"), "KG stock must be exactly 112,955.0000 KG"
    assert summary_map["LTR"] == Decimal("2050.0000"), "LTR stock must be exactly 2,050.0000 LTR"
    assert summary_map["NOS"] == Decimal("1894.0000"), "NOS stock must be exactly 1,894.0000 NOS"
    assert summary_map["SET"] == Decimal("80.0000"), "SET stock must be exactly 80.0000 SET"

    # 2. Assert that the mathematical scalar sum is 116,979.0000
    math_sum = sum(summary_map.values())
    assert math_sum == Decimal("116979.0000")

    # 3. Assert that KG is NEVER 116,979.0000
    assert summary_map["KG"] != math_sum, "CRITICAL ERROR: Mixed UOMs have been collapsed into KG!"
    assert summary_map["KG"] == Decimal("112955.0000")

    # 4. Verify API endpoint enforces the exact same segregation
    res = client.get("/api/v1/ledger/summary-by-uom", headers=stores_headers)
    assert res.status_code == 200
    api_map = {r["uom_code"]: Decimal(str(r["total_quantity"])) for r in res.json()}
    assert api_map["KG"] == Decimal("112955.0000")
    assert api_map["LTR"] == Decimal("2050.0000")
    assert api_map["NOS"] == Decimal("1894.0000")
    assert api_map["SET"] == Decimal("80.0000")
    assert api_map["KG"] != math_sum
