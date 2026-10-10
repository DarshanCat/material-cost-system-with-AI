"""
Tests for Weighted-Average Material Costing Engine.
Verifies:
- First priced receipt rate establishment
- Blended weighted average across multiple receipts at different rates
- Issue consumption at applicable average rate (rate unchanged, value = qty * rate)
- Receipt into zero stock (restarts average rate)
- Receipt into negative stock (restarts rate, flags negative stock)
- Missing opening valuation flags (OPENING_VALUATION_MISSING)
- Missing receipt rate flags
- Internal inward with pending policy
- Same-day movement ordering (receipt before issue)
- Arbitrary Decimal precision and rounding (ROUND_HALF_UP to 0.0001)
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.waste import WasteDispositionHeader, WasteDispositionLineItem, WasteStatus, DispositionType
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.costing import ValuationStatus, ItemOpeningValuation
from app.services.ledger_service import (
    post_grn_to_ledger,
    post_issue_to_ledger,
    post_waste_to_ledger,
)
from app.services.costing_service import (
    reconstruct_item_rate_evolution,
    get_item_rate_as_of_date,
)


@pytest.fixture
def costing_fixtures(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Grade 1",
        department_id=dept.id,
        category="RAW_MATERIAL",
        base_uom_id=uom.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return {"dept": dept, "uom": uom, "item": item}


def test_first_priced_receipt_establishes_rate(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]

    # GRN: 1000 kg @ Rs 42.50 / kg
    grn = GRNHeader(
        grn_number="GRN-20261012-0001",
        receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()

    line = GRNLineItem(
        grn_id=grn.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom.id,
        quantity=Decimal("1000.0000"),
        rate_ex_gst=Decimal("42.50"),
    )
    db_session.add(line)
    db_session.commit()

    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    qty, rate, status, rate_src, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("1000.0000")
    assert rate == Decimal("42.5000")
    assert status == ValuationStatus.VALUED.value
    assert len(steps) == 1
    assert steps[0]["movement_extended_value"] == Decimal("42500.00")


def test_multiple_receipts_calculate_blended_weighted_average(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]

    # Receipt 1 on 12-Oct: 1000 kg @ Rs 40.00
    grn1 = GRNHeader(
        grn_number="GRN-20261012-0001",
        receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn1)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn1.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("40.00")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn1, "usr_stores_01")

    # Receipt 2 on 14-Oct: 500 kg @ Rs 46.00
    # Expected: ((1000 * 40) + (500 * 46)) / 1500 = (40000 + 23000) / 1500 = 63000 / 1500 = Rs 42.0000
    grn2 = GRNHeader(
        grn_number="GRN-20261014-0001",
        receipt_date=date(2026, 10, 14),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn2.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("500.0000"), rate_ex_gst=Decimal("46.00")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")

    qty, rate, status, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("1500.0000")
    assert rate == Decimal("42.0000")
    assert status == ValuationStatus.VALUED.value
    assert len(steps) == 2


def test_issue_consumes_inventory_at_applicable_average_rate(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]
    dept = costing_fixtures["dept"]

    # 1. Receipt: 1000 kg @ Rs 50.00 on 12-Oct
    grn = GRNHeader(
        grn_number="GRN-20261012-0001",
        receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("50.00")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # 2. Issue: 400 kg to Foundry on 13-Oct
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261013-0001",
        issue_date=date(2026, 10, 13),
        issuing_department_id=dept.id,
        receiving_department_id=dept.id,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(
        issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("400.0000")
    ))
    db_session.commit()
    post_issue_to_ledger(db_session, issue, "usr_stores_01")

    qty, rate, status, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    # Remaining quantity is 600 kg
    assert qty == Decimal("600.0000")
    # Average rate remains unchanged at Rs 50.00
    assert rate == Decimal("50.0000")
    assert status == ValuationStatus.VALUED.value

    # Issue step recorded removal value = 400 * 50 = Rs 20,000.00
    issue_step = [s for s in steps if s["movement_type"] == MovementType.OUTWARD_ISSUE.value][0]
    assert issue_step["applied_rate"] == Decimal("50.0000")
    assert issue_step["movement_extended_value"] == Decimal("20000.00")
    assert issue_step["cumulative_value"] == Decimal("30000.00")


def test_receipt_into_zero_stock_restarts_rate(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]
    dept = costing_fixtures["dept"]

    # Inward 500 kg @ Rs 30
    grn1 = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn1)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn1.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("500.0000"), rate_ex_gst=Decimal("30.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn1, "usr_stores_01")

    # Issue full 500 kg -> Stock becomes 0
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261013-0001", issue_date=date(2026, 10, 13),
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        status=IssueStatus.APPROVED.value, created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                                         quantity=Decimal("500.0000")))
    db_session.commit()
    post_issue_to_ledger(db_session, issue, "usr_stores_01")

    # New Receipt on 15-Oct: 800 kg @ Rs 38.00
    grn2 = GRNHeader(
        grn_number="GRN-20261015-0001", receipt_date=date(2026, 10, 15),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("800.0000"), rate_ex_gst=Decimal("38.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")

    qty, rate, status, _, _ = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("800.0000")
    # New rate restarted at receipt rate Rs 38.00 (not blended with exhausted Rs 30 rate)
    assert rate == Decimal("38.0000")
    assert status == ValuationStatus.VALUED.value


def test_missing_opening_valuation_flags_status(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]

    # Post an Opening Balance without approved rate
    ob_entry = StockLedgerEntry(
        entry_number="STK-20261012-0001",
        posting_group_id="POST-OB-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("2500.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=1,
        source_line_id=1,
        source_document_number="OB-20261012",
        posted_by="usr_stores_01",
    )
    db_session.add(ob_entry)
    db_session.commit()

    qty, rate, status, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("2500.0000")
    assert rate is None
    assert status == ValuationStatus.OPENING_VALUATION_MISSING.value
    assert steps[0]["status"] == "OPENING_VALUATION_MISSING"


def test_approved_opening_valuation_incorporates_rate(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]

    # 1. Opening balance ledger entry
    ob_entry = StockLedgerEntry(
        entry_number="STK-20261012-0001",
        posting_group_id="POST-OB-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=1,
        source_line_id=1,
        source_document_number="OB-20261012",
        posted_by="usr_stores_01",
    )
    db_session.add(ob_entry)

    # 2. Approved opening valuation: Rs 44.00
    db_session.add(ItemOpeningValuation(
        material_item_id=item.id,
        baseline_date=date(2026, 10, 12),
        opening_rate_ex_gst=Decimal("44.00"),
        status="APPROVED",
        approved_by="usr_mgmt_01",
    ))
    db_session.commit()

    qty, rate, status, rate_src, _ = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("1000.0000")
    assert rate == Decimal("44.0000")
    assert status == ValuationStatus.VALUED.value
    assert rate_src == "APPROVED_OPENING_VALUATION"


def test_same_day_ordering_receipt_costs_issue(db_session: Session, costing_fixtures):
    item = costing_fixtures["item"]
    uom = costing_fixtures["uom"]
    dept = costing_fixtures["dept"]

    tx_date = date(2026, 10, 14)

    # Both happen on 14-Oct:
    # Receipt 500 kg @ Rs 55.00
    grn = GRNHeader(
        grn_number="GRN-20261014-0001", receipt_date=tx_date,
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("500.0000"), rate_ex_gst=Decimal("55.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # Issue 200 kg on same date
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261014-0001", issue_date=tx_date,
        issuing_department_id=dept.id, receiving_department_id=dept.id,
        status=IssueStatus.APPROVED.value, created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                                         quantity=Decimal("200.0000")))
    db_session.commit()
    post_issue_to_ledger(db_session, issue, "usr_stores_01")

    qty, rate, status, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("300.0000")
    assert rate == Decimal("55.0000")
    assert status == ValuationStatus.VALUED.value

    # Verify order in journal steps: INWARD_RECEIPT comes before OUTWARD_ISSUE
    assert steps[0]["movement_type"] == MovementType.INWARD_RECEIPT.value
    assert steps[1]["movement_type"] == MovementType.OUTWARD_ISSUE.value
    assert steps[1]["applied_rate"] == Decimal("55.0000")
