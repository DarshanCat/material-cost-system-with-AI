"""
Tests for Phase 4 Stage 1: Stock Balance Query Optimization & Ledger Integrity.
Verifies that:
1. Grouped SQL aggregation produces identical balances, initialized states, movement counts,
   and last movement dates compared to single-item queries across all four operational states.
2. Historical as_of_date point-in-time calculation behaves identically in batch and single queries.
3. Response schemas and status classifications match the authoritative contract.
4. Database query count for GET /api/v1/ledger/balances remains constant O(1) and does NOT grow
   linearly with the number of items.
"""

from datetime import date
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.services.ledger_service import (
    get_material_stock_balance,
    get_batch_material_stock_balances,
)


def _create_test_item(db: Session, code_suffix: str, dept: Department, uom: UOM) -> MaterialItem:
    item = MaterialItem(
        item_code=f"OPT-RM-{code_suffix}-{uuid.uuid4().hex[:4]}",
        name=f"Optimization Material {code_suffix}",
        department_id=dept.id,
        category="RAW_MATERIALS",
        base_uom_id=uom.id,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _create_ledger_entry(
    db: Session,
    item: MaterialItem,
    uom: UOM,
    tx_date: date,
    qty_delta: Decimal,
    movement_type: MovementType = MovementType.INWARD_RECEIPT,
) -> StockLedgerEntry:
    entry = StockLedgerEntry(
        entry_number=f"STK-OPT-{uuid.uuid4().hex[:8]}",
        posting_group_id=f"POST-OPT-{uuid.uuid4().hex[:6]}",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=tx_date,
        movement_type=movement_type.value,
        quantity_delta=qty_delta,
        source_document_type=SourceDocumentType.GRN.value,
        source_document_id=1,
        source_line_id=int(uuid.uuid4().int % 1000000) + 1,
        source_document_number="GRN-OPT-01",
        posted_by="test_user",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def test_batch_stock_balance_aggregation_equivalent_to_individual_queries(db_session: Session):
    """
    Proves that get_batch_material_stock_balances produces exact identical results
    to get_material_stock_balance across all four operational states:
    - UNINITIALIZED (0 movements)
    - IN_STOCK (> 0 balance)
    - OUT_OF_STOCK (== 0 balance after movements)
    - NEGATIVE_STOCK (< 0 balance)
    """
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    # 1. UNINITIALIZED item (no movements)
    item_uninit = _create_test_item(db_session, "UNINIT", dept, uom)

    # 2. IN_STOCK item (+100 on 2026-10-12, -20 on 2026-10-14 -> 80 kg)
    item_instock = _create_test_item(db_session, "INSTK", dept, uom)
    _create_ledger_entry(db_session, item_instock, uom, date(2026, 10, 12), Decimal("100.0000"))
    _create_ledger_entry(db_session, item_instock, uom, date(2026, 10, 14), Decimal("-20.0000"), MovementType.OUTWARD_ISSUE)

    # 3. OUT_OF_STOCK item (+50 on 2026-10-12, -50 on 2026-10-13 -> 0 kg)
    item_outofstock = _create_test_item(db_session, "OUTSTK", dept, uom)
    _create_ledger_entry(db_session, item_outofstock, uom, date(2026, 10, 12), Decimal("50.0000"))
    _create_ledger_entry(db_session, item_outofstock, uom, date(2026, 10, 13), Decimal("-50.0000"), MovementType.OUTWARD_ISSUE)

    # 4. NEGATIVE_STOCK item (-10 on 2026-10-12 -> -10 kg)
    item_negative = _create_test_item(db_session, "NEGSTK", dept, uom)
    _create_ledger_entry(db_session, item_negative, uom, date(2026, 10, 12), Decimal("-10.0000"), MovementType.OUTWARD_ISSUE)

    all_items = [item_uninit, item_instock, item_outofstock, item_negative]
    item_ids = [i.id for i in all_items]

    # Query individually
    individual_results = {}
    for item in all_items:
        individual_results[item.id] = get_material_stock_balance(db_session, item.id)

    # Query in single batch
    batch_results = get_batch_material_stock_balances(db_session, material_item_ids=item_ids)

    # Assert exact equivalence across all items and fields
    for item in all_items:
        ind_bal, ind_init, ind_date, ind_count = individual_results[item.id]
        batch_bal, batch_init, batch_date, batch_count = batch_results[item.id]

        assert ind_bal == batch_bal, f"Balance mismatch for {item.item_code}: {ind_bal} vs {batch_bal}"
        assert ind_init == batch_init, f"Init mismatch for {item.item_code}: {ind_init} vs {batch_init}"
        assert ind_date == batch_date, f"Date mismatch for {item.item_code}: {ind_date} vs {batch_date}"
        assert ind_count == batch_count, f"Count mismatch for {item.item_code}: {ind_count} vs {batch_count}"

    # Verify specific state values
    # UNINITIALIZED
    assert batch_results[item_uninit.id] == (Decimal("0.0000"), False, None, 0)
    # IN_STOCK
    assert batch_results[item_instock.id] == (Decimal("80.0000"), True, date(2026, 10, 14), 2)
    # OUT_OF_STOCK
    assert batch_results[item_outofstock.id] == (Decimal("0.0000"), True, date(2026, 10, 13), 2)
    # NEGATIVE_STOCK
    assert batch_results[item_negative.id] == (Decimal("-10.0000"), True, date(2026, 10, 12), 1)


def test_batch_stock_balance_historical_as_of_date_filtering(db_session: Session):
    """
    Proves that point-in-time historical cutoff (as_of_date) calculation
    is identical between individual and batch queries across time boundaries.
    """
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = _create_test_item(db_session, "HIST", dept, uom)
    _create_ledger_entry(db_session, item, uom, date(2026, 10, 12), Decimal("100.0000"))
    _create_ledger_entry(db_session, item, uom, date(2026, 10, 14), Decimal("50.0000"))
    _create_ledger_entry(db_session, item, uom, date(2026, 10, 16), Decimal("-30.0000"), MovementType.OUTWARD_ISSUE)

    check_dates = [
        (date(2026, 10, 11), Decimal("0.0000"), False, None, 0),
        (date(2026, 10, 12), Decimal("100.0000"), True, date(2026, 10, 12), 1),
        (date(2026, 10, 14), Decimal("150.0000"), True, date(2026, 10, 14), 2),
        (date(2026, 10, 16), Decimal("120.0000"), True, date(2026, 10, 16), 3),
        (date(2026, 10, 20), Decimal("120.0000"), True, date(2026, 10, 16), 3),
    ]

    for cutoff, exp_bal, exp_init, exp_date, exp_count in check_dates:
        indiv = get_material_stock_balance(db_session, item.id, as_of_date=cutoff)
        batch = get_batch_material_stock_balances(db_session, material_item_ids=[item.id], as_of_date=cutoff)[item.id]

        assert indiv == (exp_bal, exp_init, exp_date, exp_count)
        assert batch == (exp_bal, exp_init, exp_date, exp_count)


def test_get_all_stock_balances_api_contract_and_filters(client: TestClient, db_session: Session):
    """
    Verifies that GET /api/v1/ledger/balances returns accurate responses adhering
    to StockBalanceResponse schema with department and search filters.
    """
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    dept_ms = db_session.query(Department).filter_by(code="MSP").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    unique_tag = uuid.uuid4().hex[:6].upper()
    item_fdy = _create_test_item(db_session, f"FDY-{unique_tag}", dept_fdy, uom)
    item_ms = _create_test_item(db_session, f"MS-{unique_tag}", dept_ms, uom)

    _create_ledger_entry(db_session, item_fdy, uom, date(2026, 10, 12), Decimal("500.0000"))

    # 1. Fetch all balances with search query matching our unique tag
    resp_all = client.get(f"/api/v1/ledger/balances?q={unique_tag}")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert len(data_all) == 2

    by_id = {d["material_item_id"]: d for d in data_all}
    assert Decimal(str(by_id[item_fdy.id]["current_balance"])) == Decimal("500.0000")
    assert by_id[item_fdy.id]["status"] == "IN_STOCK"
    assert by_id[item_fdy.id]["movement_count"] == 1
    assert by_id[item_fdy.id]["department_name"] == "Foundry"

    assert Decimal(str(by_id[item_ms.id]["current_balance"])) == Decimal("0.0000")
    assert by_id[item_ms.id]["status"] == "UNINITIALIZED"
    assert by_id[item_ms.id]["movement_count"] == 0
    assert by_id[item_ms.id]["department_name"] == "Machine Shop"

    # 2. Filter by department
    resp_fdy = client.get(f"/api/v1/ledger/balances?department_id={dept_fdy.id}&q={unique_tag}")
    assert resp_fdy.status_code == 200
    data_fdy = resp_fdy.json()
    assert len(data_fdy) == 1
    assert data_fdy[0]["material_item_id"] == item_fdy.id


def test_query_count_does_not_grow_linearly_with_item_count(client: TestClient, db_session: Session):
    """
    CRITICAL PERFORMANCE TEST:
    Proves that the database query count for GET /api/v1/ledger/balances
    does NOT scale linearly O(N) with the number of items.
    
    Under the old N+1 implementation:
      - 5 items produced >= 6 queries
      - 20 items produced >= 21 queries
    Under the optimized implementation:
      - Query count is constant O(1) (exactly 2 queries: 1 items select + 1 grouped aggregate).
    """
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    # Create Batch A: 5 items
    tag_a = f"QA{uuid.uuid4().hex[:4].upper()}"
    items_a = []
    for i in range(5):
        it = _create_test_item(db_session, f"{tag_a}-{i}", dept, uom)
        _create_ledger_entry(db_session, it, uom, date(2026, 10, 12), Decimal("10.0000") * (i + 1))
        items_a.append(it)

    # Create Batch B: 20 items
    tag_b = f"QB{uuid.uuid4().hex[:4].upper()}"
    items_b = []
    for i in range(20):
        it = _create_test_item(db_session, f"{tag_b}-{i}", dept, uom)
        _create_ledger_entry(db_session, it, uom, date(2026, 10, 12), Decimal("5.0000") * (i + 1))
        items_b.append(it)

    engine = db_session.bind
    captured_queries = []

    def _query_capture(conn, cursor, statement, parameters, context, executemany):
        # Ignore internal PRAGMA or schema queries if any
        captured_queries.append(statement)

    event.listen(engine, "before_cursor_execute", _query_capture)

    try:
        # Measure query count for 5 items
        captured_queries.clear()
        resp_a = client.get(f"/api/v1/ledger/balances?q={tag_a}")
        assert resp_a.status_code == 200
        assert len(resp_a.json()) == 5
        count_a = len(captured_queries)

        # Measure query count for 20 items
        captured_queries.clear()
        resp_b = client.get(f"/api/v1/ledger/balances?q={tag_b}")
        assert resp_b.status_code == 200
        assert len(resp_b.json()) == 20
        count_b = len(captured_queries)

    finally:
        event.remove(engine, "before_cursor_execute", _query_capture)

    # PROOF OF O(1) PERFORMANCE:
    # Both 5 items and 20 items must issue the exact same constant number of queries (2 queries total).
    assert count_a == 2, f"Expected exactly 2 queries for 5 items, got {count_a}"
    assert count_b == 2, f"Expected exactly 2 queries for 20 items, got {count_b}"
    assert count_a == count_b, f"Query count must be constant O(1)! Got {count_a} queries for 5 items vs {count_b} for 20 items."


@pytest.fixture(autouse=True)
def _authenticate_as_admin(client: TestClient, admin_headers: dict):
    client.headers.update(admin_headers)
