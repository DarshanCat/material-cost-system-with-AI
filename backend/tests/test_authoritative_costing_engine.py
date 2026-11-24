"""
Authoritative Costing Engine Test Suite — Phase 2B-2C (FIN-DEC-01 to FIN-DEC-06).

Validates:
1. Three distinct, non-conflicting costing measures:
   - Measure A: Solid Material Charge Cost per kg (Net Charge Cost / Total Solid Charge)
   - Measure B: Molten Metal Tapped Cost per kg ((Opening Heel Val + Charge Cost) / Accounted Liquid)
   - Measure C: Good Casting Raw Material Cost per kg ((Allocated Liquid Value - Approved Scrap Credit) / Good Castings Weight)
2. Multi-heat campaign liquid heel value conservation (FIN-DEC-02).
3. Approved return-scrap credit policy (FIN-DEC-03: Option A standard return scrap WAC under item FDY-RM-003).
4. Melting loss threshold at 3.5% (FIN-DEC-04).
5. Strict raw material scope separation from conversion costs (FIN-DEC-05).
6. Historical unsupported heat classification as PROVISIONAL_HISTORICAL (FIN-DEC-06).
7. Primary database invariant: 43 ledger entries, 116,979.0000 delta, revision 007_opening_val_versioning.
"""

from decimal import Decimal
import pytest
from sqlalchemy import select, func, text

from app.db.session import SessionLocal
from app.models.ledger import StockLedgerEntry
from app.services.heat_calculations import (
    calculate_heat_costing_measures,
    HeatCostingMeasures,
    RATE_PRECISION,
    VALUE_PRECISION,
    WEIGHT_PRECISION,
)
from app.models.costing import CostScope, DenominatorPolicy


def test_measure_a_solid_charge_cost():
    """Validates Measure A: Net Charged Material Cost / Total Solid Charge."""
    # 7,155 kg solid charge with total cost ₹305,703.06
    charged_kg = Decimal("7155.0000")
    charged_cost = Decimal("305703.06")

    measures = calculate_heat_costing_measures(
        total_charged_kg=charged_kg,
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=Decimal("7500.0000"),
        good_castings_kg=Decimal("5200.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )

    # Expected: 305703.06 / 7155 = 42.7258
    assert measures.cost_per_kg_solid_charge == Decimal("42.7258")
    assert measures.measure_a_status == "VALUED"


def test_measure_b_liquid_metal_cost_cold_start():
    """Validates Measure B under cold start: zero opening and closing heel."""
    charged_kg = Decimal("7500.0000")
    charged_cost = Decimal("305703.06")
    tapped_kg = Decimal("7200.0000")

    measures = calculate_heat_costing_measures(
        total_charged_kg=charged_kg,
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=Decimal("5000.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )

    # Accounted liquid = 7,200 kg. Total input = ₹305,703.06
    # Rate = 305703.06 / 7200 = 42.4588
    assert measures.cost_per_kg_metal_tapped == Decimal("42.4588")
    assert measures.measure_b_status == "VALUED"
    assert measures.closing_liquid_heel_value == Decimal("0.00")


def test_three_heat_campaign_heel_value_conservation():
    """
    Demonstrates physical mass and financial value conservation across a 3-heat campaign (FIN-DEC-02).
    
    Heat 1 (Cold Start):
      Opening Heel: 0 kg, ₹0.00
      Solid Charge: 10,000 kg @ ₹40.00 = ₹400,000.00
      Metal Tapped: 9,000 kg
      Closing Heel: 700 kg
      Accounted Liquid: 9,700 kg
      Melt Loss: 300 kg (3.0% - normal)
      Bath Rate (R_tap): 400,000 / 9,700 = 41.2371
      Closing Heel Value: 700 * 41.2371 = ₹28,865.97
      Tapped Value: 9,000 * 41.2371 = ₹371,133.90
      
    Heat 2:
      Opening Heel: 700 kg, ₹28,865.97 (inherited exactly)
      Solid Charge: 9,000 kg @ ₹42.00 = ₹378,000.00
      Total Liquid Available: 9,700 kg, Total Input Val: ₹406,865.97
      Metal Tapped: 9,200 kg
      Closing Heel: 400 kg
      Accounted Liquid: 9,600 kg
      Melt Loss: 100 kg (1.03% - normal)
      Bath Rate (R_tap): 406,865.97 / 9,600 = 42.3819
      Closing Heel Value: 400 * 42.3819 = ₹16,952.76
      Tapped Value: 9,200 * 42.3819 = ₹389,913.48
      
    Heat 3 (Campaign End / Furnace Empty):
      Opening Heel: 400 kg, ₹16,952.76 (inherited exactly)
      Solid Charge: 8,000 kg @ ₹41.00 = ₹328,000.00
      Total Liquid Available: 8,400 kg, Total Input Val: ₹344,952.76
      Metal Tapped: 8,200 kg
      Closing Heel: 0 kg (Furnace completely drained)
      Accounted Liquid: 8,200 kg
      Melt Loss: 200 kg (2.38% - normal)
      Bath Rate (R_tap): 344,952.76 / 8,200 = 42.0674
      Closing Heel Value: 0 kg, ₹0.00
      Tapped Value: 8,200 * 42.0674 = ₹344,952.68
      
    Campaign Conservation Reconciliation:
      Total Solid Charge Cost: 400,000 + 378,000 + 328,000 = ₹1,106,000.00
      Total Tapped Output Value: 371,133.90 + 389,913.48 + 344,952.68 = ₹1,106,000.06
      Difference: ₹0.06 (0.000005% due to unit rate 4-decimal rounding).
      Final Closing Heel: 0 kg, ₹0.00.
    """
    # Heat 1: Cold Start
    h1 = calculate_heat_costing_measures(
        total_charged_kg=Decimal("10000.0000"),
        total_charged_material_cost=Decimal("400000.00"),
        metal_tapped_kg=Decimal("9000.0000"),
        good_castings_kg=Decimal("6500.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        opening_liquid_heel_value=Decimal("0.00"),
        closing_liquid_heel_kg=Decimal("700.0000"),
    )
    assert h1.cost_per_kg_metal_tapped == Decimal("41.2371")
    assert h1.closing_liquid_heel_value == Decimal("28865.97")
    assert h1.true_melt_loss_kg == Decimal("300.0000")
    assert h1.true_melt_loss_pct == Decimal("3.0000")
    h1_tapped_val = (Decimal("9000.0000") * h1.cost_per_kg_metal_tapped).quantize(VALUE_PRECISION)

    # Heat 2: Carry-forward from Heat 1
    h2 = calculate_heat_costing_measures(
        total_charged_kg=Decimal("9000.0000"),
        total_charged_material_cost=Decimal("378000.00"),
        metal_tapped_kg=Decimal("9200.0000"),
        good_castings_kg=Decimal("6600.0000"),
        opening_liquid_heel_kg=h1.closing_liquid_heel_kg,
        opening_liquid_heel_value=h1.closing_liquid_heel_value,
        closing_liquid_heel_kg=Decimal("400.0000"),
    )
    assert h2.cost_per_kg_metal_tapped == Decimal("42.3819")
    assert h2.closing_liquid_heel_value == Decimal("16952.76")
    assert h2.true_melt_loss_kg == Decimal("100.0000")
    h2_tapped_val = (Decimal("9200.0000") * h2.cost_per_kg_metal_tapped).quantize(VALUE_PRECISION)

    # Heat 3: Drain furnace to 0 kg closing heel
    h3 = calculate_heat_costing_measures(
        total_charged_kg=Decimal("8000.0000"),
        total_charged_material_cost=Decimal("328000.00"),
        metal_tapped_kg=Decimal("8200.0000"),
        good_castings_kg=Decimal("5900.0000"),
        opening_liquid_heel_kg=h2.closing_liquid_heel_kg,
        opening_liquid_heel_value=h2.closing_liquid_heel_value,
        closing_liquid_heel_kg=Decimal("0.0000"),
    )
    assert h3.cost_per_kg_metal_tapped == Decimal("42.0674")
    assert h3.closing_liquid_heel_value == Decimal("0.00")
    assert h3.true_melt_loss_kg == Decimal("200.0000")
    h3_tapped_val = (Decimal("8200.0000") * h3.cost_per_kg_metal_tapped).quantize(VALUE_PRECISION)

    # Campaign Conservation Reconciliation
    total_solid_charge_incurred = Decimal("400000.00") + Decimal("378000.00") + Decimal("328000.00")
    total_tapped_metal_allocated = h1_tapped_val + h2_tapped_val + h3_tapped_val
    variance = abs(total_solid_charge_incurred - total_tapped_metal_allocated)

    assert total_solid_charge_incurred == Decimal("1106000.00")
    # Variance across 3 heats must be <= 10 paise due to 4-decimal rate rounding
    assert variance <= Decimal("0.10")


def test_measure_c_good_casting_with_scrap_credit():
    """
    Validates Measure C: Good Casting RM Cost per kg with approved scrap credit (FIN-DEC-03).
    Formula: (Allocated Liquid Tapped Value - Approved Scrap Credit) / Good Casting Weight.
    """
    # 7,500 kg tapped @ ₹40.7604 = ₹305,703.00 tapped liquid value
    # Good casting weight = 5,000 kg
    # Internal scrap returns (runners/gating): 1,500 kg @ ₹38.00 (Item FDY-RM-003 WAC) = ₹57,000.00
    tapped_kg = Decimal("7500.0000")
    good_kg = Decimal("5000.0000")
    charged_cost = Decimal("305703.00")
    scrap_credit = Decimal("57000.00")

    # Without scrap credit
    m_no_credit = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7500.0000"),
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        approved_scrap_credit=None,
    )
    # 305,703.00 / 5,000 = 61.1406
    assert m_no_credit.raw_material_cost_per_kg_good_casting == Decimal("61.1406")

    # With approved scrap credit
    m_with_credit = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7500.0000"),
        total_charged_material_cost=charged_cost,
        metal_tapped_kg=tapped_kg,
        good_castings_kg=good_kg,
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        approved_scrap_credit=scrap_credit,
    )
    # Net RM Cost = 305,703.00 - 57,000.00 = 248,703.00
    # Good Casting RM Cost = 248,703.00 / 5,000 = 49.7406
    assert m_with_credit.raw_material_cost_per_kg_good_casting == Decimal("49.7406")
    assert m_with_credit.approved_scrap_credit == Decimal("57000.00")


def test_melting_loss_threshold_anomaly_fin_dec_04():
    """Validates FIN-DEC-04: 3.5% normal melt loss threshold and anomaly flags."""
    # Case 1: Normal melt loss of 2.5% (<= 3.5%) -> No excessive loss anomaly
    m_normal = calculate_heat_costing_measures(
        total_charged_kg=Decimal("10000.0000"),
        total_charged_material_cost=Decimal("400000.00"),
        metal_tapped_kg=Decimal("9750.0000"),
        good_castings_kg=Decimal("7000.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        normal_melt_loss_threshold_pct=Decimal("3.5000"),
    )
    assert m_normal.true_melt_loss_pct == Decimal("2.5000")
    assert not any("EXCESSIVE_MELT_LOSS" in a for a in m_normal.anomalies)

    # Case 2: Excessive melt loss of 4.5% (> 3.5%) -> Triggers EXCESSIVE_MELT_LOSS
    m_excessive = calculate_heat_costing_measures(
        total_charged_kg=Decimal("10000.0000"),
        total_charged_material_cost=Decimal("400000.00"),
        metal_tapped_kg=Decimal("9550.0000"),
        good_castings_kg=Decimal("7000.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
        normal_melt_loss_threshold_pct=Decimal("3.5000"),
    )
    assert m_excessive.true_melt_loss_pct == Decimal("4.5000")
    assert any("EXCESSIVE_MELT_LOSS" in a for a in m_excessive.anomalies)

    # Case 3: Negative melt loss (accounted metal > available liquid metal) -> Triggers NEGATIVE_MELT_LOSS
    m_negative = calculate_heat_costing_measures(
        total_charged_kg=Decimal("10000.0000"),
        total_charged_material_cost=Decimal("400000.00"),
        metal_tapped_kg=Decimal("10300.0000"),
        good_castings_kg=Decimal("7000.0000"),
        opening_liquid_heel_kg=Decimal("0.0000"),
        closing_liquid_heel_kg=Decimal("0.0000"),
    )
    assert m_negative.true_melt_loss_kg < Decimal("0.0000")
    assert any("NEGATIVE_MELT_LOSS" in a for a in m_negative.anomalies)


def test_conversion_cost_separation_fin_dec_05():
    """Validates FIN-DEC-05: Raw material costing is strictly separated from conversion costs."""
    measures = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7500.0000"),
        total_charged_material_cost=Decimal("305703.06"),
        metal_tapped_kg=Decimal("7200.0000"),
        good_castings_kg=Decimal("5000.0000"),
    )
    # Must report conversion cost as NOT_AVAILABLE per policy
    assert measures.conversion_cost_status == "NOT_AVAILABLE"


def test_historical_unsupported_heats_status_fin_dec_06():
    """Validates FIN-DEC-06: Historical unbacked heats remain tagged as PROVISIONAL_HISTORICAL."""
    # Historical heat with unbacked issue slip
    measures = calculate_heat_costing_measures(
        total_charged_kg=Decimal("7155.0000"),
        total_charged_material_cost=Decimal("305703.06"),
        metal_tapped_kg=Decimal("7500.0000"),
        good_castings_kg=Decimal("5200.0000"),
        is_charge_fully_backed_by_issues=False,
        is_historical_exception=True,
    )
    assert measures.costing_status == "PROVISIONAL_HISTORICAL"
    assert any("HISTORICAL_EXCEPTION" in a for a in measures.anomalies)


def test_live_primary_database_ledger_invariants():
    """
    Guarantees the strict primary database preservation invariants:
    - Exactly 43 stock ledger entries.
    - Exactly 116,979.0000 delta across mixed UOMs (never reported as single-UOM kg).
    - Current alembic migration version is 007_opening_val_versioning.
    """
    db = SessionLocal()
    try:
        # 1. Verify ledger count
        total_count = db.execute(select(func.count(StockLedgerEntry.id))).scalar()
        assert total_count == 43, f"Expected exactly 43 ledger entries, got {total_count}"

        # 2. Verify numerical delta sum across entries
        delta_sum = db.execute(select(func.sum(StockLedgerEntry.quantity_delta))).scalar()
        assert delta_sum == Decimal("116979.0000"), f"Expected delta sum 116,979.0000, got {delta_sum}"

        # 3. Verify alembic version table
        version_num = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version_num == "007_opening_val_versioning", f"Expected revision 007_opening_val_versioning, got {version_num}"
    finally:
        db.close()
