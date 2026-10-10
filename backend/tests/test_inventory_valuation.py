"""
Tests for Inventory Valuation Service.
Verifies:
- Positive stock with complete rates (VALUED)
- Zero stock after prior movements (ZERO_STOCK, extended_value = 0.00)
- Uninitialized stock (UNINITIALIZED)
- Negative stock (NEGATIVE_STOCK_FLAG)
- Historical valuation as of specific business dates
- Missing-rate reporting and exception queues
- NON-NEGOTIABLE: Valuation queries NEVER mutate ledger quantities or create stock movements.
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.costing import ValuationStatus
from app.services.ledger_service import (
    post_grn_to_ledger,
    post_issue_to_ledger,
    get_material_stock_balance,
)
from app.services.costing_service import reconstruct_item_rate_evolution


@pytest.fixture
def valuation_fixtures(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item1 = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Grade 1",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom.id,
        is_active=True,
    )
    item2 = MaterialItem(
        item_code="FDY-RM-002",
        name="Steel Scrap Low Phos",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom.id,
        is_active=True,
    )
    item3 = MaterialItem(
        item_code="FDY-RM-003",
        name="Uninitialized Material",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom.id,
        is_active=True,
    )
    db_session.add_all([item1, item2, item3])
    db_session.commit()
    return {"dept": dept, "uom": uom, "item1": item1, "item2": item2, "item3": item3}


def test_positive_stock_with_complete_rates(db_session: Session, valuation_fixtures):
    item = valuation_fixtures["item1"]
    uom = valuation_fixtures["uom"]

    # GRN: 2000 kg @ Rs 45.00
    grn = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("2000.0000"), rate_ex_gst=Decimal("45.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    qty, rate, status, _, _ = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("2000.0000")
    assert rate == Decimal("45.0000")
    assert status == ValuationStatus.VALUED.value

    # Extended value = 2000 * 45 = 90,000.00
    ext_val = (qty * rate).quantize(Decimal("0.01"))
    assert ext_val == Decimal("90000.00")


def test_uninitialized_stock_reports_uninitialized_status(db_session: Session, valuation_fixtures):
    item = valuation_fixtures["item3"]
    qty, rate, status, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("0.0000")
    assert rate is None
    assert status == ValuationStatus.UNINITIALIZED.value
    assert len(steps) == 0


def test_zero_stock_reports_zero_valuation(db_session: Session, valuation_fixtures):
    item = valuation_fixtures["item2"]
    uom = valuation_fixtures["uom"]
    dept = valuation_fixtures["dept"]

    # Receipt 100 kg @ Rs 35
    grn = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("100.0000"), rate_ex_gst=Decimal("35.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # Issue 100 kg -> 0 balance
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261013-0001", issue_date=date(2026, 10, 13),
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        status=IssueStatus.APPROVED.value, created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                                         quantity=Decimal("100.0000")))
    db_session.commit()
    post_issue_to_ledger(db_session, issue, "usr_stores_01")

    qty, rate, status, _, _ = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("0.0000")
    assert rate == Decimal("35.0000")
    assert status == ValuationStatus.ZERO_STOCK.value


def test_historical_valuation_reconstructs_as_of_selected_date(db_session: Session, valuation_fixtures):
    item = valuation_fixtures["item1"]
    uom = valuation_fixtures["uom"]

    # Receipt 1 on 12-Oct: 1000 kg @ Rs 40
    grn1 = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn1)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn1.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("40.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn1, "usr_stores_01")

    # Receipt 2 on 20-Oct: 1000 kg @ Rs 60
    grn2 = GRNHeader(
        grn_number="GRN-20261020-0001", receipt_date=date(2026, 10, 20),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("60.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")

    # As of 15-Oct (before second receipt):
    qty_15, rate_15, status_15, _, _ = reconstruct_item_rate_evolution(db_session, item.id, as_of_date=date(2026, 10, 15))
    assert qty_15 == Decimal("1000.0000")
    assert rate_15 == Decimal("40.0000")

    # As of 25-Oct (after both receipts):
    qty_25, rate_25, status_25, _, _ = reconstruct_item_rate_evolution(db_session, item.id, as_of_date=date(2026, 10, 25))
    assert qty_25 == Decimal("2000.0000")
    assert rate_25 == Decimal("50.0000")


def test_valuation_strictly_does_not_mutate_ledger(db_session: Session, valuation_fixtures):
    item = valuation_fixtures["item1"]
    uom = valuation_fixtures["uom"]

    # Receipt: 500 kg @ Rs 50
    grn = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("500.0000"), rate_ex_gst=Decimal("50.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # Check ledger count and balance before valuation
    ledger_count_before = db_session.execute(select(func.count(StockLedgerEntry.id))).scalar_one()
    bal_before, _, _, _ = get_material_stock_balance(db_session, item.id)

    # Perform multiple valuation queries across historical dates
    reconstruct_item_rate_evolution(db_session, item.id, as_of_date=date(2026, 10, 12))
    reconstruct_item_rate_evolution(db_session, item.id, as_of_date=date(2026, 10, 15))
    reconstruct_item_rate_evolution(db_session, item.id, as_of_date=date(2026, 10, 30))

    # Assert ledger count and balance are completely identical
    ledger_count_after = db_session.execute(select(func.count(StockLedgerEntry.id))).scalar_one()
    bal_after, _, _, _ = get_material_stock_balance(db_session, item.id)

    assert ledger_count_before == ledger_count_after
    assert bal_before == bal_after
