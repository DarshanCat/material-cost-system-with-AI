"""
Tests for Heat Log & Furnace-Charge Dry-Run Reconciliation Engine.
Verifies:
1. Exact match between stores issues and furnace bath charges.
2. Tolerance precedence limits (max(0.5 kg, 2% * Issued Qty)).
3. Multi-addition charge line aggregation within the same heat.
4. Floor consumables segregation (Moulding Sand, Slax) from bath charges.
5. Zero-quantity suppression.
6. Unmatched heats and charge lines detection.
7. Strictly read-only invariant (zero database mutations, zero ledger movements, double-deduction prevention).
"""

from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.ledger import StockLedgerEntry
from app.models.heat import HeatHeader
from app.models.issue import MaterialIssueHeader
from app.schemas.heat_reconciliation_preview import ReconciliationVarianceClass
from app.services.heat_reconciliation_preview_service import (
    HeatReconciliationPreviewEngine,
    clean_heat_key,
)


def test_clean_heat_key():
    assert clean_heat_key("H-102607-3857") == "102607-3857"
    assert clean_heat_key("102607-3857") == "102607-3857"
    assert clean_heat_key("h-102608-3914 ") == "102608-3914"
    assert clean_heat_key("") == ""


def test_exact_match_and_tolerance_classes():
    """Verifies exact matches, OK within tolerance, and excess/short classifications."""
    engine = HeatReconciliationPreviewEngine()

    furnace_charges = [
        # Line 1: Exact match (500 kg issued vs 500 kg charged)
        {
            "heat_slip": "102607-3857",
            "code": "FDY-RM-007",
            "desc": "CRC Scrap",
            "qty": 500.0,
            "uom": "Kg",
            "date": "2026-10-12",
        },
        # Line 2: Within 2% tolerance (100 kg issued vs 99 kg charged; diff 1.0 kg <= 2.0 kg tol)
        {
            "heat_slip": "102607-3857",
            "code": "FDY-RM-002",
            "desc": "Borings-450/10",
            "qty": 100.0,
            "uom": "Kg",
            "date": "2026-10-12",
        },
        # Line 3: Excess Issue beyond tolerance (50 kg issued vs 45 kg charged; diff 5 kg > 1.0 kg tol)
        {
            "heat_slip": "102607-3857",
            "code": "FDY-RM-013",
            "desc": "Graphite Carbonizer",
            "qty": 50.0,
            "uom": "Kg",
            "date": "2026-10-12",
        },
        # Line 4: Short Issue beyond tolerance (10 kg issued vs 15 kg charged; diff -5 kg < -0.5 kg tol)
        {
            "heat_slip": "102607-3857",
            "code": "FDY-RM-016",
            "desc": "Magnesium",
            "qty": 10.0,
            "uom": "Kg",
            "date": "2026-10-12",
        },
    ]

    mock_heat_charges = {
        "102607-3857": [
            {"code": "FDY-RM-007", "description": "CRC Scrap", "quantity": Decimal("500.0000"), "uom": "Kg"},
            {"code": "FDY-RM-002", "description": "Borings-450/10", "quantity": Decimal("99.0000"), "uom": "Kg"},
            {"code": "FDY-RM-013", "description": "Graphite Carbonizer", "quantity": Decimal("45.0000"), "uom": "Kg"},
            {"code": "FDY-RM-016", "description": "Magnesium", "quantity": Decimal("15.0000"), "uom": "Kg"},
        ]
    }

    summary = engine.reconcile_furnace_charges(furnace_charges, mock_heat_charges)

    assert summary.total_heats_evaluated == 1
    assert summary.matched_heats_count == 1
    assert summary.exact_matches_count == 1
    assert summary.tolerance_ok_count == 2  # exact + within tol
    assert summary.variance_excess_count == 1
    assert summary.variance_short_count == 1

    # Check finding statuses
    matches_by_code = {m.item_code: m for m in summary.matches}
    assert matches_by_code["FDY-RM-007"].variance_class == ReconciliationVarianceClass.OK
    assert matches_by_code["FDY-RM-002"].variance_class == ReconciliationVarianceClass.OK
    assert matches_by_code["FDY-RM-013"].variance_class == ReconciliationVarianceClass.EXCESS_ISSUE
    assert matches_by_code["FDY-RM-016"].variance_class == ReconciliationVarianceClass.SHORT_ISSUE


def test_multi_addition_aggregation():
    """
    Verifies that multiple additions of the same material in the same heat
    (e.g. Copper 3.0 kg + 2.05 kg trim addition) are aggregated together.
    """
    engine = HeatReconciliationPreviewEngine()

    furnace_charges = [
        # Two additions of Copper to heat 102608-3914
        {"heat_slip": "102608-3914", "code": "FDY-RM-006", "desc": "Copper", "qty": 3.0, "uom": "Kg"},
        {"heat_slip": "102608-3914", "code": "FDY-RM-006", "desc": "Copper", "qty": 2.05, "uom": "Kg"},
    ]

    mock_heat_charges = {
        "102608-3914": [
            {"code": "FDY-RM-006", "description": "Copper", "quantity": Decimal("5.0500"), "uom": "Kg"}
        ]
    }

    summary = engine.reconcile_furnace_charges(furnace_charges, mock_heat_charges)

    assert summary.matched_heats_count == 1
    assert len(summary.matches) == 1
    m = summary.matches[0]
    assert m.is_multi_addition is True
    assert m.issued_quantity == Decimal("5.0500")
    assert m.charged_quantity == Decimal("5.0500")
    assert m.variance_class == ReconciliationVarianceClass.OK


def test_floor_consumable_and_zero_qty_segregation():
    """
    Verifies that bulk sand / slag coagulants with blank slips are segregated,
    and zero-quantity placeholder records are suppressed.
    """
    engine = HeatReconciliationPreviewEngine()

    rows = [
        # Floor consumable (Pre-Coated Sand 1000 kg with blank slip)
        {"heat_slip": "", "code": "FDY-MD-001", "desc": "Pre Coated Sand", "qty": 1000.0, "uom": "Kg"},
        # Floor consumable (Slax 25 kg)
        {"heat_slip": "", "code": "FDY-RM-021", "desc": "Slax", "qty": 25.0, "uom": "Kg"},
        # Zero-quantity placeholder (Copper 0.0 kg)
        {"heat_slip": "102607-3858", "code": "FDY-RM-006", "desc": "Copper", "qty": 0.0, "uom": "Kg"},
        # Valid furnace charge
        {"heat_slip": "102607-3858", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 250.0, "uom": "Kg"},
    ]

    summary = engine.reconcile_furnace_charges(rows, {})

    assert summary.floor_consumables_segregated_count == 2
    assert summary.zero_qty_lines_suppressed_count == 1
    # Only the valid 250 kg charge row should be evaluated against heats
    assert summary.total_heats_evaluated == 1


def test_unmatched_heats_detection():
    """
    Verifies detection of unmatched issue slips (heat not in heat log)
    and unmatched heats (heat in heat log with no issue slip).
    """
    engine = HeatReconciliationPreviewEngine()

    # Stores issued to 102607-3899, but Heat Log only has 102607-3900
    furnace_charges = [
        {"heat_slip": "102607-3899", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 300.0, "uom": "Kg"}
    ]
    mock_heat_charges = {
        "102607-3900": [
            {"code": "FDY-RM-007", "description": "CRC Scrap", "quantity": Decimal("300.0000"), "uom": "Kg"}
        ]
    }

    summary = engine.reconcile_furnace_charges(furnace_charges, mock_heat_charges)

    assert summary.total_heats_evaluated == 2
    assert summary.matched_heats_count == 0
    assert summary.unmatched_heats_count == 2

    slip_unmatched = [m for m in summary.matches if m.heat_number == "102607-3899"][0]
    assert slip_unmatched.variance_class == ReconciliationVarianceClass.UNMATCHED_SLIP
    assert "missing from Heat Log Master" in slip_unmatched.notes

    heat_unmatched = [m for m in summary.matches if m.heat_number == "102607-3900"][0]
    assert heat_unmatched.variance_class == ReconciliationVarianceClass.UNMATCHED_HEAT


def test_double_deduction_prevention_read_only(db_session: Session):
    """
    Verifies non-negotiable double-deduction prevention:
    Reconciliation preview execution never mutates database and never creates stock ledger entries.
    """
    ledg_count_before = db_session.query(StockLedgerEntry).count()
    heat_count_before = db_session.query(HeatHeader).count()
    iss_count_before = db_session.query(MaterialIssueHeader).count()

    engine = HeatReconciliationPreviewEngine()
    furnace_charges = [
        {"heat_slip": "102607-3857", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 250.0, "uom": "Kg"}
    ]
    summary = engine.reconcile_furnace_charges(furnace_charges, {})

    assert summary.is_read_only is True

    # Check database isolation
    assert db_session.query(StockLedgerEntry).count() == ledg_count_before
    assert db_session.query(HeatHeader).count() == heat_count_before
    assert db_session.query(MaterialIssueHeader).count() == iss_count_before
    assert len(db_session.new) == 0
    assert len(db_session.dirty) == 0
    assert len(db_session.deleted) == 0


def test_uom_conflict_reporting():
    """Verifies that UOM mismatches between recorded slips and master base UOM are tracked."""
    engine = HeatReconciliationPreviewEngine(
        approved_items={
            "FDY-RM-007": {"name": "CRC Scrap", "category": "Raw Material", "uom": "Kg"}
        }
    )

    furnace_charges = [
        # Recorded in Nos instead of approved master Kg
        {"heat_slip": "102607-3857", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 250.0, "uom": "Nos"}
    ]
    summary = engine.reconcile_furnace_charges(furnace_charges, {})

    assert summary.uom_mismatches_count == 1


def test_tolerance_boundary_and_decimal_suspect_cases():
    """
    Verifies exact boundary conditions:
    1. Variance exactly equal to tolerance limit -> OK.
    2. Variance 0.01 above tolerance limit -> EXCESS_ISSUE.
    3. Small quantity where absolute 0.5 kg precedence dominates -> OK at 0.5 kg diff.
    4. Order-of-magnitude scale error (ratio >= 9.5) -> DECIMAL_SUSPECT.
    """
    engine = HeatReconciliationPreviewEngine()

    furnace_charges = [
        # Case 1: Exactly at tolerance limit (Issued: 100 kg, Charged: 98 kg, Tol: 2.0 kg -> OK)
        {"heat_slip": "102607-3801", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 100.0, "uom": "Kg"},
        # Case 2: Just beyond tolerance limit (Issued: 100 kg, Charged: 97.99 kg, Tol: 2.0 kg, Diff: 2.01 kg -> EXCESS)
        {"heat_slip": "102607-3802", "code": "FDY-RM-007", "desc": "CRC Scrap", "qty": 100.0, "uom": "Kg"},
        # Case 3: Absolute tolerance dominance (Issued: 10 kg, Charged: 9.5 kg, Tol: 0.5 kg -> OK)
        {"heat_slip": "102607-3803", "code": "FDY-RM-013", "desc": "Graphite Carbonizer", "qty": 10.0, "uom": "Kg"},
        # Case 4: Decimal suspect (Issued: 100 kg, Charged: 10 kg, Ratio 10.0 >= 9.5 -> DECIMAL_SUSPECT)
        {"heat_slip": "102607-3804", "code": "FDY-RM-020", "desc": "Silicon", "qty": 100.0, "uom": "Kg"},
    ]

    mock_heat_charges = {
        "102607-3801": [{"code": "FDY-RM-007", "description": "CRC Scrap", "quantity": Decimal("98.0000"), "uom": "Kg"}],
        "102607-3802": [{"code": "FDY-RM-007", "description": "CRC Scrap", "quantity": Decimal("97.9900"), "uom": "Kg"}],
        "102607-3803": [{"code": "FDY-RM-013", "description": "Graphite Carbonizer", "quantity": Decimal("9.5000"), "uom": "Kg"}],
        "102607-3804": [{"code": "FDY-RM-020", "description": "Silicon", "quantity": Decimal("10.0000"), "uom": "Kg"}],
    }

    summary = engine.reconcile_furnace_charges(furnace_charges, mock_heat_charges)

    matches_by_heat = {m.heat_number: m for m in summary.matches}

    # Case 1: OK at exact boundary
    assert matches_by_heat["102607-3801"].variance_class == ReconciliationVarianceClass.OK
    # Case 2: EXCESS_ISSUE just beyond boundary
    assert matches_by_heat["102607-3802"].variance_class == ReconciliationVarianceClass.EXCESS_ISSUE
    # Case 3: OK under absolute tolerance fallback
    assert matches_by_heat["102607-3803"].variance_class == ReconciliationVarianceClass.OK
    # Case 4: DECIMAL_SUSPECT
    assert matches_by_heat["102607-3804"].variance_class == ReconciliationVarianceClass.DECIMAL_SUSPECT

