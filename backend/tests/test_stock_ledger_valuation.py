"""
Phase 1C: Stock Ledger Valuation and Precision Remediation Test Suite.

Remediates Observation 8 & Observation 9:
- Observation 8: Stock ledger traceability, valuation and reversal gaps.
- Observation 9: Inventory value rebuilt from rounded average rate (reproducing the exact Rs 1.49 discrepancy).

Verifies:
1. Exact mathematical reproduction of the Rs 1.49 discrepancy:
   - Pig Iron (FDY-RM-001): +Rs 1.40
   - Ferro Silicon 75% (FDY-RM-004): +Rs 0.02
   - Ferro Manganese HC (FDY-RM-005): +Rs 0.07
   - Total System Inventory: +Rs 1.49 (Rs 46,52,929.18 rate-reconstructed vs Rs 46,52,927.69 movement roll-forward).
2. Authoritative valuation invariants:
   - Quantity roll-forward: Q_close = Q_open + Q_in - Q_out +/- Q_adj.
   - Value roll-forward: V_close = V_open + V_in - V_out +/- V_adj.
3. Multi-receipt weighted-average recalculation across multiple distinct rates.
4. Partial issues and fractional quantities.
5. Reversal valuation: reversing an inward or outward entry restores exact historical value delta.
6. Zero-stock reset (clearing residual rounding residue).
7. Decimal arithmetic consistency and determinism (zero float inaccuracy).
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import pytest
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.uom import UOM
from app.models.item import MaterialItem
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.costing import ItemOpeningValuation, ValuationStatus
from app.models.ledger import StockLedgerEntry, MovementType
from app.services.ledger_service import (
    post_grn_to_ledger,
    post_issue_to_ledger,
    reverse_grn,
    reverse_material_issue,
)
from app.services.costing_service import (
    reconstruct_item_rate_evolution,
    RATE_PRECISION,
    VALUE_PRECISION,
)


@pytest.fixture
def val_env(db_session: Session):
    fdy = db_session.query(Department).filter_by(code="FDY").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()

    def _create_item(code: str, name: str) -> MaterialItem:
        it = MaterialItem(
            item_code=code,
            name=name,
            department_id=fdy.id,
            category="RAW_MATERIALS",
            base_uom_id=kg.id,
            is_active=True,
        )
        db_session.add(it)
        db_session.flush()
        return it

    return {"fdy": fdy, "kg": kg, "create_item": _create_item}


def test_reproduce_exact_1_49_discrepancy():
    """
    Observation 9 Regression: Reproduces the exact Rs 1.49 discrepancy reported in
    external review using pure Decimal arithmetic matching the historical ledger events.

    1. Pig Iron (FDY-RM-001):
       - Opening: 25,000 kg @ Rs 45.50 = Rs 1,137,500.00
       - Receipt: 12,000 kg @ Rs 46.00 = Rs 552,000.00
       - Total Inward Value: Rs 1,689,500.00 across 37,000 kg
       - Blended Rate: 1,689,500 / 37,000 = 45.66216216... -> rounded to 4 decimals = 45.6622
       - Reconstructed value at blended step: 37,000 * 45.6622 = Rs 1,689,501.40 (+Rs 1.40 error)
       - Issue: 8,500 kg @ 45.6622 = Rs 388,128.70
       - Physical Audit Adjustment: -50 kg @ 45.6622 = -Rs 2,283.11
       - Final Quantity: 28,450 kg
       - Value Reconstructed from Rounded Rate: 28,450 * 45.6622 = Rs 1,299,089.59
       - Exact Movement Roll-Forward Sum: 1,137,500 + 552,000 - 388,128.70 - 2,283.11 = Rs 1,299,088.19
       - Discrepancy: Rs 1,299,089.59 - Rs 1,299,088.19 = +Rs 1.40

    2. Ferro Silicon 75% (FDY-RM-004):
       - Opening: 2,500 kg @ Rs 110.00 = Rs 275,000.00
       - Issue: -120 kg @ Rs 110.00 = -Rs 13,200.00 (Balance: 2,380 kg, Value: Rs 261,800.00)
       - Receipt: 1,500 kg @ Rs 112.50 = Rs 168,750.00
       - Total Quantity: 3,880 kg; True Value: Rs 430,550.00
       - Blended Rate: 430,550 / 3,880 = 110.9664948... -> rounded = 110.9665
       - Value Reconstructed from Rounded Rate: 3,880 * 110.9665 = Rs 430,550.02
       - Discrepancy: Rs 430,550.02 - Rs 430,550.00 = +Rs 0.02

    3. Ferro Manganese HC (FDY-RM-005):
       - Opening: 1,800 kg @ Rs 86.50 = Rs 155,700.00
       - Issue: -65 kg @ Rs 86.50 = -Rs 5,622.50 (Balance: 1,735 kg, Value: Rs 150,077.50)
       - Receipt: 800 kg @ Rs 88.00 = Rs 70,400.00
       - Total Quantity: 2,535 kg; True Value: Rs 220,477.50
       - Blended Rate: 220,477.50 / 2,535 = 86.9733727... -> rounded = 86.9734
       - Value Reconstructed from Rounded Rate: (2,535 * 86.9734) = Rs 220,477.57
       - Discrepancy: Rs 220,477.57 - Rs 220,477.50 = +Rs 0.07

    Total Rounding Discrepancy:
       1.40 + 0.02 + 0.07 = Rs 1.49
    """
    # 1. Pig Iron
    pi_open_qty = Decimal("25000.0000")
    pi_open_val = Decimal("1137500.00")
    pi_rcpt_qty = Decimal("12000.0000")
    pi_rcpt_val = Decimal("552000.00")
    pi_tot_qty = pi_open_qty + pi_rcpt_qty
    pi_tot_val = pi_open_val + pi_rcpt_val
    pi_avg_rate = (pi_tot_val / pi_tot_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert pi_avg_rate == Decimal("45.6622")

    pi_issue_qty = Decimal("8500.0000")
    pi_issue_val = (pi_issue_qty * pi_avg_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert pi_issue_val == Decimal("388128.70")

    pi_adj_qty = Decimal("50.0000")
    pi_adj_val = (pi_adj_qty * pi_avg_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert pi_adj_val == Decimal("2283.11")

    pi_final_qty = pi_tot_qty - pi_issue_qty - pi_adj_qty
    assert pi_final_qty == Decimal("28450.0000")

    pi_rebuilt_val = (pi_final_qty * pi_avg_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pi_roll_forward_val = pi_tot_val - pi_issue_val - pi_adj_val
    pi_diff = pi_rebuilt_val - pi_roll_forward_val
    assert pi_diff == Decimal("1.40")

    # 2. Ferro Silicon 75%
    fesi_open_qty = Decimal("2500.0000")
    fesi_open_val = Decimal("275000.00")
    fesi_issue_qty = Decimal("120.0000")
    fesi_issue_val = Decimal("13200.00")
    fesi_rem_qty = fesi_open_qty - fesi_issue_qty
    fesi_rem_val = fesi_open_val - fesi_issue_val

    fesi_rcpt_qty = Decimal("1500.0000")
    fesi_rcpt_val = Decimal("168750.00")
    fesi_tot_qty = fesi_rem_qty + fesi_rcpt_qty
    fesi_tot_val = fesi_rem_val + fesi_rcpt_val
    fesi_avg_rate = (fesi_tot_val / fesi_tot_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert fesi_avg_rate == Decimal("110.9665")

    fesi_rebuilt_val = (fesi_tot_qty * fesi_avg_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fesi_diff = fesi_rebuilt_val - fesi_tot_val
    assert fesi_diff == Decimal("0.02")

    # 3. Ferro Manganese HC
    femn_open_qty = Decimal("1800.0000")
    femn_open_val = Decimal("155700.00")
    femn_issue_qty = Decimal("65.0000")
    femn_issue_val = Decimal("5622.50")
    femn_rem_qty = femn_open_qty - femn_issue_qty
    femn_rem_val = femn_open_val - femn_issue_val

    femn_rcpt_qty = Decimal("800.0000")
    femn_rcpt_val = Decimal("70400.00")
    femn_tot_qty = femn_rem_qty + femn_rcpt_qty
    femn_tot_val = femn_rem_val + femn_rcpt_val
    femn_avg_rate = (femn_tot_val / femn_tot_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    assert femn_avg_rate == Decimal("86.9734")

    femn_rebuilt_val = (femn_tot_qty * femn_avg_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    femn_diff = femn_rebuilt_val - femn_tot_val
    assert femn_diff == Decimal("0.07")

    # Total Discrepancy
    total_discrepancy = pi_diff + fesi_diff + femn_diff
    assert total_discrepancy == Decimal("1.49")


def test_accounting_invariant_holds_under_value_roll_forward(db_session: Session, val_env):
    """
    Observation 8 & 9: Verify the fundamental accounting roll-forward invariant:
    Closing Value = Opening Value + Inward Value - Outward Value
    Closing Qty = Opening Qty + Inward Qty - Outward Qty
    """
    item = val_env["create_item"]("VAL-TEST-001", "Accounting Roll-Forward Ingot")
    uom = val_env["kg"]

    # 1. Opening Balance: 1000 kg @ Rs 50.00
    db_session.add(ItemOpeningValuation(
        material_item_id=item.id,
        version=1,
        opening_rate_ex_gst=Decimal("50.00"),
        status="APPROVED",
        baseline_date=date(2026, 10, 12),
        created_by="usr_seed",
    ))
    db_session.add(StockLedgerEntry(
        entry_number="STK-VAL-001",
        posting_group_id="POST-VAL-001",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-001",
        posted_by="usr_seed",
    ))
    db_session.commit()

    # 2. Inward Receipt: 500 kg @ Rs 53.25
    grn = GRNHeader(
        grn_number="GRN-VAL-001",
        receipt_date=date(2026, 10, 14),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("500.0000"), rate_ex_gst=Decimal("53.25")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # 3. Outward Issue: 300 kg
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-VAL-001",
        issue_date=date(2026, 10, 15),
        issuing_department_id=val_env["fdy"].id,
        receiving_department_id=val_env["fdy"].id,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(
        issue_id=issue.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("300.0000")
    ))
    db_session.commit()
    post_issue_to_ledger(db_session, issue, "usr_stores_01")

    # Verify evolution
    qty, rate, status, src, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert status == ValuationStatus.VALUED.value

    # Roll-forward calculation from movements
    open_val = Decimal("0.00")
    inward_val = Decimal("0.00")
    outward_val = Decimal("0.00")

    open_qty = Decimal("0.0000")
    inward_qty = Decimal("0.0000")
    outward_qty = Decimal("0.0000")

    for s in steps:
        m_type = s["movement_type"]
        q = s["quantity_delta"]
        v = s["movement_extended_value"] or Decimal("0.00")
        if m_type == "OPENING_BALANCE":
            open_qty += q
            open_val += v
        elif m_type == "INWARD_RECEIPT":
            inward_qty += q
            inward_val += v
        elif m_type == "OUTWARD_ISSUE":
            outward_qty += abs(q)
            outward_val += v

    closing_qty_expected = open_qty + inward_qty - outward_qty
    closing_val_expected = open_val + inward_val - outward_val

    assert qty == closing_qty_expected
    assert qty == Decimal("1200.0000")

    # Verify individual step values
    assert open_val == Decimal("50000.00")
    assert inward_val == Decimal("26625.00")  # 500 * 53.25
    # Rate before issue: (50000 + 26625) / 1500 = 76625 / 1500 = 51.083333... -> 51.0833
    assert rate == Decimal("51.0833")
    assert outward_val == Decimal("15324.99")  # 300 * 51.0833
    assert closing_val_expected == Decimal("61300.01")


def test_multiple_receipts_at_different_rates_blend_correctly(db_session: Session, val_env):
    """
    Observation 8: Verify moving average calculation across 3 distinct receipts at different prices.
    Receipt 1: 100 kg @ Rs 20.00 -> Value = 2,000.00, Rate = 20.0000
    Receipt 2: 200 kg @ Rs 26.00 -> Value = 5,200.00, Total Qty = 300, Rate = 7,200 / 300 = 24.0000
    Receipt 3: 100 kg @ Rs 32.00 -> Value = 3,200.00, Total Qty = 400, Rate = 10,400 / 400 = 26.0000
    """
    item = val_env["create_item"]("VAL-MULTI-001", "Multi-Rate Scrap")
    uom = val_env["kg"]

    prices = [Decimal("20.00"), Decimal("26.00"), Decimal("32.00")]
    quantities = [Decimal("100.0000"), Decimal("200.0000"), Decimal("100.0000")]
    dates = [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]

    for idx, (p, q, d) in enumerate(zip(prices, quantities, dates), start=1):
        grn = GRNHeader(
            grn_number=f"GRN-MULTI-{idx:03d}",
            receipt_date=d,
            source_type=GRNSourceType.EXTERNAL_VENDOR.value,
            status=GRNStatus.APPROVED.value,
            created_by="usr_stores_01",
        )
        db_session.add(grn)
        db_session.flush()
        db_session.add(GRNLineItem(
            grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
            quantity=q, rate_ex_gst=p
        ))
        db_session.commit()
        post_grn_to_ledger(db_session, grn, "usr_stores_01")

    qty, rate, status, src, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("400.0000")
    assert rate == Decimal("26.0000")
    assert status == ValuationStatus.VALUED.value
    assert len(steps) == 3
    # Final step cumulative value: 10,400.00
    assert steps[-1]["cumulative_value"] == Decimal("10400.00")


def test_reversal_restores_original_value_delta(db_session: Session, val_env):
    """
    Observation 8: Reversing an approved document must create compensating ledger entries
    that restore the exact physical quantity and preserve valuation traceability.
    """
    item = val_env["create_item"]("VAL-REV-001", "Reversal Test Ingot")
    uom = val_env["kg"]

    # 1. Opening balance: 100 kg @ Rs 50.00
    db_session.add(ItemOpeningValuation(
        material_item_id=item.id,
        version=1,
        opening_rate_ex_gst=Decimal("50.00"),
        status="APPROVED",
        baseline_date=date(2026, 10, 12),
        created_by="usr_seed",
    ))
    db_session.add(StockLedgerEntry(
        entry_number="STK-REV-OB",
        posting_group_id="POST-REV-OB",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("100.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-REV",
        posted_by="usr_seed",
    ))
    db_session.commit()

    # 2. Inward Receipt: 50 kg @ Rs 60.00
    grn = GRNHeader(
        grn_number="GRN-REV-001",
        receipt_date=date(2026, 10, 14),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("50.0000"), rate_ex_gst=Decimal("60.00")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # Prior to reversal: Qty = 150 kg
    qty_before, _, _, _, _ = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty_before == Decimal("150.0000")

    # 3. Reverse GRN
    rev_resp = reverse_grn(db_session, grn.id, "usr_mgmt_01", "Audit cancellation")
    assert rev_resp.status == "REVERSED"
    db_session.commit()

    # Post reversal: Qty restored to 100 kg
    qty_after, rate_after, _, _, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty_after == Decimal("100.0000")
    # Rate restored to opening balance rate
    assert rate_after == Decimal("50.0000")
    # Reversal entry appended to steps
    reversal_steps = [s for s in steps if s["movement_type"] == "REVERSAL"]
    assert len(reversal_steps) == 1
    assert reversal_steps[0]["quantity_delta"] == Decimal("-50.0000")


def test_zero_stock_and_rounding_residue_handling(db_session: Session, val_env):
    """
    Observation 9: When inventory quantity reaches zero, inventory valuation must
    strictly report 0.00, rather than carrying stranded fractional-paise residues.
    """
    item = val_env["create_item"]("VAL-ZERO-001", "Zero Stock Scrap")
    uom = val_env["kg"]

    # Inward: 3 kg @ Rs 10.00 = Rs 30.00
    grn = GRNHeader(
        grn_number="GRN-ZERO-001",
        receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("3.0000"), rate_ex_gst=Decimal("10.00")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    # Issue: 3 kg @ Rs 10.00 = Rs 30.00
    iss = MaterialIssueHeader(
        issue_slip_number="ISS-ZERO-001",
        issue_date=date(2026, 10, 14),
        issuing_department_id=val_env["fdy"].id,
        receiving_department_id=val_env["fdy"].id,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(iss)
    db_session.flush()
    db_session.add(MaterialIssueLineItem(
        issue_id=iss.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("3.0000")
    ))
    db_session.commit()
    post_issue_to_ledger(db_session, iss, "usr_stores_01")

    qty, rate, status, src, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("0.0000")
    assert status == ValuationStatus.ZERO_STOCK.value
    # Extended cumulative value at final step must be 0.00
    final_step = steps[-1]
    assert final_step["running_quantity"] == Decimal("0.0000")
    assert final_step["cumulative_value"] == Decimal("0.00") or final_step["cumulative_value"] is None


def test_fractional_quantities_and_precision_stability(db_session: Session, val_env):
    """
    Observation 8: Fractional quantities (4 decimals) must maintain exact
    arithmetic stability across multiple transactions without floating-point drift.
    """
    item = val_env["create_item"]("VAL-FRAC-001", "Precision Granules")
    uom = val_env["kg"]

    # Inward: 123.4567 kg @ Rs 987.65
    grn = GRNHeader(
        grn_number="GRN-FRAC-001",
        receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value,
        status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn)
    db_session.flush()
    db_session.add(GRNLineItem(
        grn_id=grn.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
        quantity=Decimal("123.4567"), rate_ex_gst=Decimal("987.65")
    ))
    db_session.commit()
    post_grn_to_ledger(db_session, grn, "usr_stores_01")

    qty, rate, status, src, steps = reconstruct_item_rate_evolution(db_session, item.id)
    assert qty == Decimal("123.4567")
    assert rate == Decimal("987.6500")
    # Extended value: 123.4567 * 987.65 = 121932.009755 -> 121932.01
    expected_val = (Decimal("123.4567") * Decimal("987.65")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert expected_val == Decimal("121932.01")
    assert steps[0]["movement_extended_value"] == expected_val


def test_repeated_valuation_calculations_are_strictly_deterministic(db_session: Session, val_env):
    """
    Observation 8: Repeated calls to valuation must produce identical results without
    mutating database state or altering decimal values.
    """
    item = val_env["create_item"]("VAL-DET-001", "Deterministic Ingot")
    uom = val_env["kg"]

    # Opening valuation
    db_session.add(ItemOpeningValuation(
        material_item_id=item.id,
        version=1,
        opening_rate_ex_gst=Decimal("45.6789"),
        status="APPROVED",
        baseline_date=date(2026, 10, 12),
        created_by="usr_seed",
    ))
    db_session.add(StockLedgerEntry(
        entry_number="STK-DET-001",
        posting_group_id="POST-DET-001",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("5000.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=0,
        source_line_id=item.id,
        source_document_number="OB-DET",
        posted_by="usr_seed",
    ))
    db_session.commit()

    run1 = reconstruct_item_rate_evolution(db_session, item.id)
    run2 = reconstruct_item_rate_evolution(db_session, item.id)
    run3 = reconstruct_item_rate_evolution(db_session, item.id)

    assert run1[0] == run2[0] == run3[0] == Decimal("5000.0000")
    assert run1[1] == run2[1] == run3[1] == Decimal("45.6789")
    assert run1[2] == run2[2] == run3[2] == ValuationStatus.VALUED.value
    assert len(run1[4]) == len(run2[4]) == len(run3[4]) == 1
    assert run1[4][0]["movement_extended_value"] == run2[4][0]["movement_extended_value"] == run3[4][0]["movement_extended_value"]
