"""
Unit tests for Heat Log Calculation Service (heat_calculations.py).
Tests Stage 1 & Stage 2 requirements:
- Exact Excel formula conformance and anomalies
- Material-wise percentage calculation
- Multiple raw materials and 100% summation
- Multiple produced parts & unequal part weights
- Missing unit weight handling (MISSING_UNIT_WEIGHT / INCOMPLETE_ALLOCATION)
- Zero good casting weight handling
- REJECT, RUNNERS, and GATING classifications exclusion
- Complete allocation reconciliation and variance
- Decimal precision
"""

from decimal import Decimal
import pytest
from app.services.heat_calculations import (
    calculate_heat_kpis,
    calculate_material_charge_percentages,
    calculate_parts_rm_allocation,
    calculate_heat_full_summary,
)


def test_h2004_workbook_scenario():
    """
    Validates the exact H-2004 scenario from VSPL_Foundry_Heat_Log_TEMPLATE.xlsx.
    Total Charge: 430 kg
    Metal Tapped: 450 kg
    Melt Loss: -20 kg
    Melt Loss %: -4.6512%
    Melting Recovery %: 104.6512%
    """
    charges = [
        Decimal("50.0"),   # Borings-450/10
        Decimal("100.0"),  # CRC Scrap
        Decimal("150.0"),  # Inoculant 250
        Decimal("30.0"),   # Magnesium
        Decimal("35.0"),   # Manganese
        Decimal("45.0"),   # Silicon
        Decimal("20.0"),   # Gattings-450/10
    ]
    tapped = Decimal("450.0")
    parts = [
        {
            "original_part_description": "HIN21",
            "quantity_produced": Decimal("10.0"),
            "unit_cast_weight": Decimal("150.0"),
            "classification": "GOOD",
        }
    ]

    kpis = calculate_heat_kpis(charges, tapped, parts)

    assert kpis.total_charge_kg == Decimal("430.0000")
    assert kpis.metal_tapped_kg == Decimal("450.0000")
    assert kpis.melt_loss_kg == Decimal("-20.0000")
    assert kpis.melt_loss_pct == Decimal("-4.6512")
    assert kpis.melting_recovery_pct == Decimal("104.6512")
    assert kpis.good_castings_kg == Decimal("1500.0000")
    assert kpis.casting_yield_pct == Decimal("348.8372")
    assert kpis.rm_per_good_kg == Decimal("0.2867")
    assert kpis.total_parts_count == 10

    # Anomalies should be flagged
    assert any("TAPPED_EXCEEDS_CHARGE" in a for a in kpis.anomalies)
    assert any("NEGATIVE_MELT_LOSS" in a for a in kpis.anomalies)
    assert any("GOOD_CASTINGS_EXCEED_TAPPED" in a for a in kpis.anomalies)


def test_normal_heat_calculations():
    """Tests standard heat with valid loss, yield, and RM per good kg."""
    charges = [Decimal("700.0"), Decimal("200.0"), Decimal("100.0")]
    tapped = Decimal("950.0")
    parts = [
        {"quantity_produced": 50, "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"quantity_produced": 20, "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"quantity_produced": 5, "unit_cast_weight": Decimal("10.0"), "classification": "REJECTED"},
    ]

    kpis = calculate_heat_kpis(charges, tapped, parts)

    assert kpis.total_charge_kg == Decimal("1000.0000")
    assert kpis.metal_tapped_kg == Decimal("950.0000")
    assert kpis.melt_loss_kg == Decimal("50.0000")
    assert kpis.melt_loss_pct == Decimal("5.0000")
    assert kpis.melting_recovery_pct == Decimal("95.0000")
    assert kpis.good_castings_kg == Decimal("700.0000")
    assert kpis.casting_yield_pct == Decimal("70.0000")
    assert kpis.rm_per_good_kg == Decimal("1.4286")
    assert kpis.total_parts_count == 75
    assert len(kpis.anomalies) == 0


def test_zero_or_missing_charge():
    """Tests zero charge handling safely."""
    kpis = calculate_heat_kpis([], None, None)
    assert kpis.total_charge_kg == Decimal("0.0000")
    assert kpis.melt_loss_kg is None
    assert kpis.melt_loss_pct is None
    assert kpis.melting_recovery_pct is None
    assert kpis.good_castings_kg is None
    assert kpis.casting_yield_pct is None
    assert kpis.rm_per_good_kg is None
    assert any("MISSING_OR_ZERO_CHARGE" in a for a in kpis.anomalies)


def test_zero_good_castings():
    """Tests safe division by zero when good castings is zero."""
    charges = [Decimal("500.0")]
    tapped = Decimal("480.0")
    parts = [
        {"quantity_produced": 10, "unit_cast_weight": Decimal("0.0"), "classification": "GOOD"},
        {"quantity_produced": 5, "unit_cast_weight": Decimal("20.0"), "classification": "REJECTED"},
    ]

    kpis = calculate_heat_kpis(charges, tapped, parts)
    assert kpis.good_castings_kg is None
    assert kpis.casting_yield_pct is None
    assert kpis.rm_per_good_kg is None


# ==============================================================================
# Stage 2 Tests: Material % of Charge
# ==============================================================================

def test_material_charge_percentage_single_and_multiple():
    """Tests line charge percentages and verifies they sum to 100%."""
    charge_lines = [
        {"line_number": 1, "original_material_description": "Pig Iron", "charged_quantity": Decimal("400.0")},
        {"line_number": 2, "original_material_description": "Steel Scrap", "charged_quantity": Decimal("300.0")},
        {"line_number": 3, "original_material_description": "Returns", "charged_quantity": Decimal("200.0")},
        {"line_number": 4, "original_material_description": "FeSi", "charged_quantity": Decimal("100.0")},
    ]

    calcs = calculate_material_charge_percentages(charge_lines)
    assert len(calcs) == 4
    assert calcs[0].percentage_of_charge == Decimal("40.0000")
    assert calcs[1].percentage_of_charge == Decimal("30.0000")
    assert calcs[2].percentage_of_charge == Decimal("20.0000")
    assert calcs[3].percentage_of_charge == Decimal("10.0000")

    total_pct = sum(c.percentage_of_charge for c in calcs)
    assert total_pct == Decimal("100.0000")


def test_material_charge_percentage_h2004_summation():
    """Tests H-2004 7-line charge mix percentages summing to 100% within precision."""
    charge_lines = [
        {"charged_quantity": Decimal("50.0")},
        {"charged_quantity": Decimal("100.0")},
        {"charged_quantity": Decimal("150.0")},
        {"charged_quantity": Decimal("30.0")},
        {"charged_quantity": Decimal("35.0")},
        {"charged_quantity": Decimal("45.0")},
        {"charged_quantity": Decimal("20.0")},
    ]
    calcs = calculate_material_charge_percentages(charge_lines, Decimal("430.0"))
    assert calcs[0].percentage_of_charge == Decimal("11.6279")
    assert calcs[1].percentage_of_charge == Decimal("23.2558")
    assert calcs[2].percentage_of_charge == Decimal("34.8837")
    assert calcs[3].percentage_of_charge == Decimal("6.9767")
    assert calcs[4].percentage_of_charge == Decimal("8.1395")
    assert calcs[5].percentage_of_charge == Decimal("10.4651")
    assert calcs[6].percentage_of_charge == Decimal("4.6512")

    total_pct = sum(c.percentage_of_charge for c in calcs)
    # Sum is 99.9999 due to 4-decimal rounding
    assert abs(total_pct - Decimal("100.0000")) < Decimal("0.001")


def test_material_charge_percentage_zero_charge():
    """Tests safe handling when total charge is zero or missing."""
    charge_lines = [
        {"charged_quantity": Decimal("0.0")},
    ]
    calcs = calculate_material_charge_percentages(charge_lines, Decimal("0.0"))
    assert calcs[0].percentage_of_charge is None


# ==============================================================================
# Stage 2 Tests: Physical RM Allocation & Reconciliation
# ==============================================================================

def test_parts_rm_allocation_multiple_parts_and_reconciliation():
    """
    Tests physical RM allocation across multiple parts with unequal weights:
    Charge: 1000 kg
    Part A (GOOD): 50 parts @ 10 kg = 500 kg -> (500/700)*1000 = 714.2857 kg
    Part B (GOOD): 20 parts @ 10 kg = 200 kg -> (200/700)*1000 = 285.7143 kg
    Total Good: 700 kg
    Reconciliation: 714.2857 + 285.7143 = 1000.0000 kg. Reconciled.
    """
    total_charge = Decimal("1000.0000")
    parts = [
        {"line_number": 1, "original_part_description": "Crankcase", "quantity_produced": Decimal("50"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"line_number": 2, "original_part_description": "Flywheel", "quantity_produced": Decimal("20"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
    ]

    allocated, recon = calculate_parts_rm_allocation(parts, total_charge)

    assert len(allocated) == 2
    assert allocated[0].total_weight_kg == Decimal("500.0000")
    assert allocated[0].rm_allocated_kg == Decimal("714.2857")
    assert allocated[0].allocation_status == "ALLOCATED"

    assert allocated[1].total_weight_kg == Decimal("200.0000")
    assert allocated[1].rm_allocated_kg == Decimal("285.7143")
    assert allocated[1].allocation_status == "ALLOCATED"

    assert recon.total_heat_charge_kg == Decimal("1000.0000")
    assert recon.total_good_castings_kg == Decimal("700.0000")
    assert recon.total_allocated_rm_kg == Decimal("1000.0000")
    assert recon.allocation_variance_kg == Decimal("0.0000")
    assert recon.reconciliation_status == "RECONCILED"
    assert recon.is_reconciled is True


def test_parts_rm_allocation_excludes_non_good_classifications():
    """
    Verifies that REJECT, RUNNERS, and GATING are strictly excluded from allocation.
    Charge: 1000 kg
    Part 1 (GOOD): 50 @ 10 kg = 500 kg
    Part 2 (REJECTED): 5 @ 10 kg = 50 kg
    Part 3 (RUNNERS): 10 @ 5 kg = 50 kg
    Part 4 (GATING): 20 @ 2 kg = 40 kg
    Good Castings = 500 kg.
    Part 1 gets 100% of charge: 1000.0000 kg.
    Parts 2, 3, 4 receive None with CLASSIFICATION_EXCLUDED.
    """
    total_charge = Decimal("1000.0000")
    parts = [
        {"line_number": 1, "original_part_description": "Bracket", "quantity_produced": Decimal("50"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"line_number": 2, "original_part_description": "Bracket Scrap", "quantity_produced": Decimal("5"), "unit_cast_weight": Decimal("10.0"), "classification": "REJECTED"},
        {"line_number": 3, "original_part_description": "Runners", "quantity_produced": Decimal("10"), "unit_cast_weight": Decimal("5.0"), "classification": "RUNNERS"},
        {"line_number": 4, "original_part_description": "Gating", "quantity_produced": Decimal("20"), "unit_cast_weight": Decimal("2.0"), "classification": "GATING"},
    ]

    allocated, recon = calculate_parts_rm_allocation(parts, total_charge)

    assert allocated[0].allocation_status == "ALLOCATED"
    assert allocated[0].rm_allocated_kg == Decimal("1000.0000")

    assert allocated[1].allocation_status == "CLASSIFICATION_EXCLUDED"
    assert allocated[1].rm_allocated_kg is None

    assert allocated[2].allocation_status == "CLASSIFICATION_EXCLUDED"
    assert allocated[2].rm_allocated_kg is None

    assert allocated[3].allocation_status == "CLASSIFICATION_EXCLUDED"
    assert allocated[3].rm_allocated_kg is None

    assert recon.total_good_castings_kg == Decimal("500.0000")
    assert recon.total_allocated_rm_kg == Decimal("1000.0000")
    assert recon.is_reconciled is True
    assert recon.reconciliation_status == "RECONCILED"


def test_parts_rm_allocation_missing_unit_weight():
    """
    Tests handling when a GOOD part has missing unit weight:
    - Marked MISSING_UNIT_WEIGHT.
    - Prevents silent redistribution over remaining parts when no external good weight exists.
    - Marks reconciliation INCOMPLETE_ALLOCATION with full charge variance.
    """
    total_charge = Decimal("1000.0000")
    parts = [
        {"line_number": 1, "original_part_description": "Housing", "quantity_produced": Decimal("50"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"line_number": 2, "original_part_description": "Cover", "quantity_produced": Decimal("20"), "unit_cast_weight": None, "classification": "GOOD"},
    ]

    allocated, recon = calculate_parts_rm_allocation(parts, total_charge)

    assert allocated[0].allocation_status == "INCOMPLETE_ALLOCATION"
    assert allocated[0].rm_allocated_kg is None

    assert allocated[1].allocation_status == "MISSING_UNIT_WEIGHT"
    assert allocated[1].rm_allocated_kg is None

    assert recon.reconciliation_status == "INCOMPLETE_ALLOCATION"
    assert recon.is_reconciled is False
    assert recon.allocation_variance_kg == Decimal("1000.0000")
    assert "missing unit cast weight" in recon.discrepancy_reason


def test_parts_rm_allocation_with_external_good_weight_and_missing_unit_weight():
    """
    When an explicit heat_good_castings_kg is provided, valid parts can be allocated,
    while unweighted parts produce variance and INCOMPLETE_ALLOCATION.
    """
    total_charge = Decimal("1000.0000")
    external_good_wt = Decimal("700.0000")
    parts = [
        {"line_number": 1, "original_part_description": "Housing", "quantity_produced": Decimal("50"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"line_number": 2, "original_part_description": "Cover", "quantity_produced": Decimal("20"), "unit_cast_weight": None, "classification": "GOOD"},
    ]

    allocated, recon = calculate_parts_rm_allocation(parts, total_charge, heat_good_castings_kg=external_good_wt)

    assert allocated[0].rm_allocated_kg == Decimal("714.2857")
    assert allocated[0].allocation_status == "ALLOCATED"

    assert allocated[1].rm_allocated_kg is None
    assert allocated[1].allocation_status == "MISSING_UNIT_WEIGHT"

    assert recon.total_allocated_rm_kg == Decimal("714.2857")
    assert recon.allocation_variance_kg == Decimal("285.7143")
    assert recon.reconciliation_status == "INCOMPLETE_ALLOCATION"
    assert recon.is_reconciled is False


def test_parts_rm_allocation_zero_good_casting_weight():
    """Tests zero good casting weight yields safe ZERO_GOOD_CASTING_WEIGHT."""
    total_charge = Decimal("500.0000")
    parts = [
        {"line_number": 1, "original_part_description": "Scrap Part", "quantity_produced": Decimal("10"), "unit_cast_weight": Decimal("10.0"), "classification": "REJECTED"},
    ]

    allocated, recon = calculate_parts_rm_allocation(parts, total_charge)

    assert allocated[0].allocation_status == "CLASSIFICATION_EXCLUDED"
    assert recon.total_allocated_rm_kg == Decimal("0.0000")
    assert recon.reconciliation_status == "ZERO_GOOD_CASTING_WEIGHT"
    assert recon.is_reconciled is False


def test_calculate_heat_full_summary():
    """Tests comprehensive summary integrating KPIs, charge percentages, parts, and reconciliation."""
    charge_lines = [
        {"charged_quantity": Decimal("600.0")},
        {"charged_quantity": Decimal("400.0")},
    ]
    tapped = Decimal("950.0")
    parts = [
        {"quantity_produced": Decimal("50"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
        {"quantity_produced": Decimal("20"), "unit_cast_weight": Decimal("10.0"), "classification": "GOOD"},
    ]

    result = calculate_heat_full_summary(charge_lines, tapped, parts)

    assert result.kpis.total_charge_kg == Decimal("1000.0000")
    assert result.kpis.metal_tapped_kg == Decimal("950.0000")
    assert result.kpis.melt_loss_kg == Decimal("50.0000")
    assert result.charge_lines[0].percentage_of_charge == Decimal("60.0000")
    assert result.charge_lines[1].percentage_of_charge == Decimal("40.0000")
    assert result.parts_allocated[0].rm_allocated_kg == Decimal("714.2857")
    assert result.parts_allocated[1].rm_allocated_kg == Decimal("285.7143")
    assert result.reconciliation.reconciliation_status == "RECONCILED"
    assert result.reconciliation.is_reconciled is True


# ==============================================================================
# Phase 2B-1 Investigation Tests: Edge Cases & Accounting Integrity
# ==============================================================================

def test_missing_tapped_weight_handling():
    """
    Validates KPI handling when metal_tapped_weight is None (as in Heats 4, 5, 6, 7).
    - Total Charge is computed.
    - Melt Loss and Melting Recovery are None (cannot be computed).
    - Casting yield can still be computed if good castings exist.
    - No divide-by-zero or crash occurs.
    """
    charges = [Decimal("3500.0"), Decimal("1500.0")]
    tapped = None
    parts = [
        {"quantity_produced": Decimal("40"), "unit_cast_weight": Decimal("75.0"), "classification": "GOOD"},
    ]

    kpis = calculate_heat_kpis(charges, tapped, parts)
    assert kpis.total_charge_kg == Decimal("5000.0000")
    assert kpis.metal_tapped_kg is None
    assert kpis.melt_loss_kg is None
    assert kpis.melt_loss_pct is None
    assert kpis.melting_recovery_pct is None
    assert kpis.good_castings_kg == Decimal("3000.0000")
    assert kpis.casting_yield_pct == Decimal("60.0000")
    assert kpis.rm_per_good_kg == Decimal("1.6667")


def test_distinction_melting_recovery_vs_casting_yield():
    """
    Verifies that Melting Recovery % and Casting Yield % are strictly distinct metrics:
    - Melting Recovery = (Metal Tapped / Total Charge) * 100 (liquid furnace recovery, ~95%)
    - Casting Yield = (Good Castings / Total Charge) * 100 (finished casting yield, ~65%)
    Asserts they are never conflated or assumed equal.
    """
    charges = [Decimal("7000.0")]  # 7000 kg solid charge
    tapped = Decimal("6650.0")    # 6650 kg liquid metal (5% melt loss, 95% recovery)
    parts = [
        # 4550 kg good finished castings (65% casting yield)
        {"quantity_produced": Decimal("130"), "unit_cast_weight": Decimal("35.0"), "classification": "GOOD"},
        # 350 kg rejected castings (5% rejection)
        {"quantity_produced": Decimal("10"), "unit_cast_weight": Decimal("35.0"), "classification": "REJECTED"},
    ]

    kpis = calculate_heat_kpis(charges, tapped, parts)

    assert kpis.melting_recovery_pct == Decimal("95.0000")
    assert kpis.casting_yield_pct == Decimal("65.0000")
    assert kpis.melting_recovery_pct != kpis.casting_yield_pct
    assert kpis.melt_loss_pct == Decimal("5.0000")
    assert kpis.melting_recovery_pct + kpis.melt_loss_pct == Decimal("100.0000")
    assert kpis.good_castings_kg == Decimal("4550.0000")


def test_missing_liquid_heel_and_carryover_anomaly():
    """
    Simulates Heats 1, 2, 3 where metal tapped exceeds charge due to unrecorded liquid heel:
    - Solid Charge: 7,150 kg
    - Molten Tapped: 7,420 kg (270 kg excess)
    Verifies:
    1. Melt Loss is negative (-270.0000 kg).
    2. Melting Recovery exceeds 100% (103.7762%).
    3. TAPPED_EXCEEDS_CHARGE and NEGATIVE_MELT_LOSS anomalies are both flagged.
    4. Proves that without liquid heel tracking, metallurgical mass balance fails.
    """
    charges = [
        Decimal("4200.0"),  # Pig Iron
        Decimal("2800.0"),  # Scrap
        Decimal("60.0"),    # FeSi
        Decimal("35.0"),    # FeMn
        Decimal("40.0"),    # CPC
        Decimal("15.0"),    # SMZ
    ]
    tapped = Decimal("7420.0")

    kpis = calculate_heat_kpis(charges, tapped, None)

    assert kpis.total_charge_kg == Decimal("7150.0000")
    assert kpis.metal_tapped_kg == Decimal("7420.0000")
    assert kpis.melt_loss_kg == Decimal("-270.0000")
    assert kpis.melt_loss_pct == Decimal("-3.7762")
    assert kpis.melting_recovery_pct == Decimal("103.7762")

    assert any("TAPPED_EXCEEDS_CHARGE" in a for a in kpis.anomalies)
    assert any("NEGATIVE_MELT_LOSS" in a for a in kpis.anomalies)


def test_heat_costing_without_approved_issue_linkage_gap(db_session: Session):
    """
    Isolated test demonstrating External Review Observation 14:
    The costing engine calculates heat material costs based on charge line items
    even when NO approved Stores issue slip exists for that heat.
    """
    from datetime import date
    from sqlalchemy import select
    from app.models.department import Department
    from app.models.uom import UOM
    from app.models.item import MaterialItem
    from app.models.heat import HeatHeader, HeatChargeLine
    from app.services.costing_service import calculate_heat_cost_detail

    # Provision isolated department, UOM, and item
    fdy_dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalar_one()
    uom_kg = db_session.execute(select(UOM).where(UOM.code == "KG")).scalar_one()

    test_item = MaterialItem(
        item_code="TEST-ISO-01",
        name="Isolated Pig Iron",
        department_id=fdy_dept.id,
        base_uom_id=uom_kg.id,
        category="RM",
        is_active=True,
    )
    db_session.add(test_item)
    db_session.flush()

    # Create heat with charge line but ZERO issue slips
    heat = HeatHeader(
        heat_number="H-ISO-0001",
        original_heat_number="H-ISO-0001",
        normalized_heat_number="H-ISO-0001",
        heat_date=date(2026, 10, 15),
        furnace_id="F-01",
        metal_tapped_weight=Decimal("1000.0000"),
        production_status="COMPLETED",
        created_by="test_user",
    )
    db_session.add(heat)
    db_session.flush()

    chg = HeatChargeLine(
        heat_id=heat.id,
        line_number=1,
        material_item_id=test_item.id,
        original_material_description="Isolated Pig Iron",
        charged_quantity=Decimal("1000.0000"),
        uom_id=uom_kg.id,
    )
    db_session.add(chg)
    db_session.commit()

    # Re-query heat with charge lines
    db_session.refresh(heat)

    # Cost the heat: costing succeeds or processes charge lines without checking issue slips
    cost_detail = calculate_heat_cost_detail(db_session, heat)
    assert cost_detail["heat_id"] == heat.id
    assert cost_detail["total_charged_quantity"] == Decimal("1000.0000")
    # Proves the gap: calculate_heat_cost_detail does NOT require or verify a linked Stores issue!

