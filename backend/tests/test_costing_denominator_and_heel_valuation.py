"""
Unit tests for Foundry Heat Costing Denominators & Liquid Heel Valuation (Phase 2B-2B).
Tests:
1. Measure A: Cost per kg of Solid Charge (Net Material Cost / Total Solid Charge)
2. Measure B: Cost per kg of Metal Tapped accounting for Liquid Heel
3. Measure C: Raw Material Cost per kg of Good Casting
4. Liquid Heel Value and Mass Continuity across multi-heat sequences
5. Incomplete / unverified heel valuation handling (INCOMPLETE_HEEL_VALUATION)
6. Zero tapped weight and zero good casting weight division-by-zero guards
7. Incomplete Stores Issue backing gate (PROVISIONAL vs FINAL)
8. Exact mathematical reconstruction of historical H-20261022-0001 numbers
   (resolving the conflicting Rs 40.76 vs Rs 45.94 vs Rs 46.64 values)
"""

from decimal import Decimal
import pytest

from app.services.heat_calculations import (
    calculate_heat_costing_measures,
    HeatCostingMeasures,
    RATE_PRECISION,
    VALUE_PRECISION,
    WEIGHT_PRECISION,
)


def test_measure_a_solid_charge_cost_standard():
    """
    Measure A calculates net charged material cost / total solid charge weight.
    Charge: 7,155.0000 kg, Net Material Cost: Rs 3,05,703.06
    Expected Rate: 305703.06 / 7155 = Rs 42.7258 / kg
    """
    charged_kg = Decimal("7155.0000")
    charged_cost = Decimal("305703.06")
    tapped_kg = Decimal("7500.0000")
    good_kg = Decimal("6720.0000")

    result = calculate_heat_costing_measures(
        total_charged_kg=charged_kg,
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        is_charge_fully_backed_by_issues=True,
    )

    assert result.total_charged_kg == charged_kg
    assert result.total_charged_material_cost == charged_cost
    assert result.cost_per_kg_solid_charge == Decimal("42.7258")
    assert result.measure_a_status == "VALUED"


def test_measure_b_cold_start_no_heel():
    """
    Measure B on a cold start with zero closing heel:
    Rate = Total Material Cost / Metal Tapped
    Rs 305,703.06 / 7,500 kg = Rs 40.7604 / kg (exact costing engine value).
    """
    charged_kg = Decimal("7155.0000")
    charged_cost = Decimal("305703.06")
    tapped_kg = Decimal("7500.0000")
    good_kg = Decimal("6720.0000")

    result = calculate_heat_costing_measures(
        total_charged_kg=charged_kg,
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        is_charge_fully_backed_by_issues=True,
    )

    assert result.cost_per_kg_metal_tapped == Decimal("40.7604")
    assert result.measure_b_status == "VALUED"
    assert result.closing_liquid_heel_value == Decimal("0.00")


def test_measure_c_good_casting_cost_standard():
    """
    Measure C allocates net heat material cost to good castings produced.
    Good Castings = 6,720.0000 kg.
    Tapped Metal Value = 7,500 kg * 40.7604 = Rs 305,703.00
    Rate per Good kg = 305,703.00 / 6,720 = Rs 45.4915 / kg.
    """
    charged_kg = Decimal("7155.0000")
    charged_cost = Decimal("305703.06")
    tapped_kg = Decimal("7500.0000")
    good_kg = Decimal("6720.0000")

    result = calculate_heat_costing_measures(
        total_charged_kg=charged_kg,
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        is_charge_fully_backed_by_issues=True,
    )

    assert result.good_castings_kg == Decimal("6720.0000")
    assert result.raw_material_cost_per_kg_good_casting == Decimal("45.4915")
    assert result.measure_c_status == "VALUED"
    assert result.costing_status == "FINAL"


def test_multi_heat_heel_value_continuity():
    """
    Validates complete financial and mass conservation across a 3-heat sequence:
    Heat 1: Cold start (0 heel) -> leaves 300 kg heel
    Heat 2: Inherits 300 kg heel -> leaves 350 kg heel
    Heat 3: Inherits 350 kg heel -> completely drained (0 heel)
    """
    # ------------------ HEAT 1 ------------------
    # Cold start: Charge 7,000 kg @ Rs 42.00 = Rs 294,000.00
    # Tapped: 6,500 kg, Closing heel: 300 kg -> Liquid accounted: 6,800 kg
    h1_charge_kg = Decimal("7000.0000")
    h1_charge_cost = Decimal("294000.00")
    h1_tapped_kg = Decimal("6500.0000")
    h1_cl_heel_kg = Decimal("300.0000")
    h1_good_kg = Decimal("6000.0000")

    h1 = calculate_heat_costing_measures(
        total_charged_kg=h1_charge_kg,
        total_charged_material_cost=h1_charge_cost,
        metal_tapped_kg=h1_tapped_kg,
        good_castings_kg=h1_good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=h1_cl_heel_kg,
    )

    # Bath rate = 294,000 / 6,800 = Rs 43.2353 / kg
    assert h1.cost_per_kg_metal_tapped == Decimal("43.2353")
    # Closing heel value = 300 * 43.2353 = Rs 12,970.59
    assert h1.closing_liquid_heel_value == Decimal("12970.59")
    # Tapped value = 6500 * 43.2353 = Rs 281,029.45
    # Total output accounted = 281,029.45 + 12,970.59 = Rs 294,000.04 (within 4 paise of 294,000.00)

    # ------------------ HEAT 2 ------------------
    # Inherits 300 kg @ Rs 12,970.59 from Heat 1
    # New Charge: 6,800 kg @ Rs 41.00 = Rs 278,800.00
    # Total Input Value = 12,970.59 + 278,800.00 = Rs 291,770.59
    # Tapped: 6,600 kg, Closing heel: 350 kg -> Liquid accounted: 6,950 kg
    h2_charge_kg = Decimal("6800.0000")
    h2_charge_cost = Decimal("278800.00")
    h2_tapped_kg = Decimal("6600.0000")
    h2_cl_heel_kg = Decimal("350.0000")
    h2_good_kg = Decimal("6100.0000")

    h2 = calculate_heat_costing_measures(
        total_charged_kg=h2_charge_kg,
        total_charged_material_cost=h2_charge_cost,
        metal_tapped_kg=h2_tapped_kg,
        good_castings_kg=h2_good_kg,
        opening_liquid_heel_kg=h1_cl_heel_kg,
        opening_liquid_heel_value=h1.closing_liquid_heel_value,
        closing_liquid_heel_kg=h2_cl_heel_kg,
    )

    # Bath rate = 291,770.59 / 6,950 = Rs 41.9814 / kg
    assert h2.cost_per_kg_metal_tapped == Decimal("41.9814")
    # Closing heel value = 350 * 41.9814 = Rs 14,693.49
    assert h2.closing_liquid_heel_value == Decimal("14693.49")

    # ------------------ HEAT 3 ------------------
    # Inherits 350 kg @ Rs 14,693.49 from Heat 2
    # New Charge: 6,700 kg @ Rs 40.00 = Rs 268,000.00
    # Total Input Value = 14,693.49 + 268,000.00 = Rs 282,693.49
    # Tapped: 6,850 kg, Closing heel: 0 kg (furnace empty)
    h3_charge_kg = Decimal("6700.0000")
    h3_charge_cost = Decimal("268000.00")
    h3_tapped_kg = Decimal("6850.0000")
    h3_cl_heel_kg = Decimal("0.0000")
    h3_good_kg = Decimal("6300.0000")

    h3 = calculate_heat_costing_measures(
        total_charged_kg=h3_charge_kg,
        total_charged_material_cost=h3_charge_cost,
        metal_tapped_kg=h3_tapped_kg,
        good_castings_kg=h3_good_kg,
        opening_liquid_heel_kg=h2_cl_heel_kg,
        opening_liquid_heel_value=h2.closing_liquid_heel_value,
        closing_liquid_heel_kg=h3_cl_heel_kg,
    )

    # Bath rate = 282,693.49 / 6,850 = Rs 41.2691 / kg
    assert h3.cost_per_kg_metal_tapped == Decimal("41.2691")
    assert h3.closing_liquid_heel_value == Decimal("0.00")


def test_unverified_prior_heel_status():
    """
    If a heat has carryover but the prior heat's closing heel valuation is unverified,
    costing status must be marked INCOMPLETE and anomaly flagged.
    """
    result = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7000.0000"),
        total_charged_material_cost=Decimal("294000.00"),
        metal_tapped_kg=Decimal("6500.0000"),
        good_castings_kg=Decimal("6000.0000"),
        opening_liquid_heel_kg=Decimal("300.0000"),
        opening_liquid_heel_value=Decimal("12970.59"),
        closing_liquid_heel_kg=Decimal("350.0000"),
        has_unverified_heel=True,
    )

    assert result.measure_b_status == "INCOMPLETE_HEEL_VALUATION"
    assert result.cost_per_kg_metal_tapped is None
    assert result.closing_liquid_heel_value is None
    assert result.costing_status == "INCOMPLETE"
    assert any("UNVERIFIED_HEEL_VALUATION" in a for a in result.anomalies)


def test_missing_tapped_weight_zero_division():
    """
    Tests graceful handling when metal tapped weight is missing or zero.
    Must not crash with ZeroDivisionError; must report MISSING_TAPPED_WEIGHT.
    """
    result = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7000.0000"),
        total_charged_material_cost=Decimal("294000.00"),
        metal_tapped_kg=None,
        good_castings_kg=Decimal("6000.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )

    assert result.cost_per_kg_metal_tapped is None
    assert result.measure_b_status == "MISSING_TAPPED_WEIGHT"
    assert result.costing_status == "INCOMPLETE"


def test_zero_good_castings_handling():
    """
    Tests heat with zero good castings (e.g. test heat or 100% rejection).
    Measures A and B remain valid; Measure C reports ZERO_GOOD_CASTINGS without division error.
    """
    result = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7000.0000"),
        total_charged_material_cost=Decimal("294000.00"),
        metal_tapped_kg=Decimal("6500.0000"),
        good_castings_kg=Decimal("0.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )

    assert result.cost_per_kg_solid_charge is not None
    assert result.cost_per_kg_metal_tapped is not None
    assert result.raw_material_cost_per_kg_good_casting is None
    assert result.measure_c_status == "ZERO_GOOD_CASTINGS"


def test_missing_solid_charge_rate_handling():
    """
    If raw material prices are unavailable (unvalued items),
    Measure A reports MISSING_RATE and costing status is INCOMPLETE.
    """
    result = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7000.0000"),
        total_charged_material_cost=None,
        metal_tapped_kg=Decimal("6500.0000"),
        good_castings_kg=Decimal("6000.0000"),
    )

    assert result.cost_per_kg_solid_charge is None
    assert result.measure_a_status == "MISSING_RATE"
    assert result.cost_per_kg_metal_tapped is None
    assert result.measure_b_status == "MISSING_CHARGE_COST"
    assert result.costing_status == "INCOMPLETE"


def test_incomplete_stores_issue_backing_gate():
    """
    If solid materials were charged without approved Stores Issue Slips,
    the heat cost can be computed but MUST be flagged as PROVISIONAL, never FINAL.
    """
    result = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7155.0000"),
        total_charged_material_cost=Decimal("305703.06"),
        metal_tapped_kg=Decimal("7500.0000"),
        good_castings_kg=Decimal("6720.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        is_charge_fully_backed_by_issues=False,
    )

    assert result.costing_status == "PROVISIONAL"
    assert not result.is_charge_fully_backed_by_issues
    assert any("CHARGE_NOT_FULLY_BACKED_BY_STORES_ISSUES" in a for a in result.anomalies)


def test_historical_h20261022_0001_reconstruction():
    """
    Resolves the exact root causes of the 3 conflicting numbers for H-20261022-0001:
    - ₹40.76/kg: Pure raw material cost / Tapped weight (Costing Engine)
    - ₹45.94/kg: Synthetic rate Rs 42/kg material + Rs 35,062.50 power + Rs 9,000 overhead (Heat Log screen)
    - ₹46.64/kg: Real material cost Rs 305,703.06 + Rs 35,062.50 power + Rs 9,000 overhead (Costing Dashboard)
    """
    charged_kg = Decimal("7155.0000")
    tapped_kg = Decimal("7500.0000")
    good_kg = Decimal("6720.0000")
    actual_material_cost = Decimal("305703.06")

    # 1. Authoritative Measure A: Solid charge cost per kg
    rate_a = (actual_material_cost / charged_kg).quantize(RATE_PRECISION)
    assert rate_a == Decimal("42.7258")

    # 2. Authoritative Measure B: Pure material cost per kg tapped (Backend Costing Engine value)
    engine_cost_per_kg = (actual_material_cost / tapped_kg).quantize(RATE_PRECISION)
    assert engine_cost_per_kg == Decimal("40.7604")  # Displays as Rs 40.76 in engine

    # 3. Frontend synthetic formula from HeatLogManagementView (heatCalculations.ts:430-435)
    est_material_cost = charged_kg * Decimal("42.0")  # Arbitrary Rs 42.00/kg
    est_kwh = (tapped_kg / Decimal("1000")) * Decimal("550")
    power_cost = est_kwh * Decimal("8.50")
    overhead_cost = (tapped_kg / Decimal("1000")) * Decimal("1200")
    total_est_cost = est_material_cost + power_cost + overhead_cost
    heat_log_cost_per_kg = (total_est_cost / tapped_kg).quantize(Decimal("0.01"))
    assert heat_log_cost_per_kg == Decimal("45.94")  # Matches Rs 45.94 exactly!

    # 4. Frontend synthetic formula from CostingDashboard (CostingDashboard.tsx:714-720)
    dashboard_total_direct_cost = actual_material_cost + power_cost + overhead_cost
    dashboard_net_cost_per_kg = (dashboard_total_direct_cost / tapped_kg).quantize(Decimal("0.01"))
    assert dashboard_net_cost_per_kg == Decimal("46.64")  # Matches Rs 46.64 exactly!
