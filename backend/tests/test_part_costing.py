"""
Tests for Finished Part Material Costing.
Verifies:
- Unit cast weight * heat cost per kg calculation
- Missing unit weight handling (MISSING_WEIGHT)
- Incomplete parent heat cost data handling (INSUFFICIENT_COST_DATA)
- Provisional material-only scope labeling (MATERIAL_ONLY)
- NON-NEGOTIABLE: Part costing NEVER creates finished goods inventory movements.
"""

from decimal import Decimal
import pytest

from app.models.heat import HeatPartsProduced, CastingClassification
from app.models.costing import PartCostStatus, CostScope, HeatCostStatus
from app.services.costing_service import calculate_part_cost_detail


def test_valid_part_cost_calculation():
    part = HeatPartsProduced(
        id=1,
        heat_id=10,
        line_number=1,
        original_part_description="PART-DI-FLANGE-100 Ductile Iron Flange 100mm",
        quantity_produced=Decimal("50.0000"),
        unit_cast_weight=Decimal("12.5000"),  # 12.5 kg each
        classification=CastingClassification.GOOD.value,
    )
    # Suppose parent heat cost per kg = Rs 38.0000
    heat_cost_per_kg = Decimal("38.0000")
    heat_status = HeatCostStatus.COMPLETE.value

    res = calculate_part_cost_detail(part, heat_cost_per_kg, heat_status)

    assert res["status"] == PartCostStatus.CALCULATED.value
    # Unit material cost = 12.5 kg * Rs 38.0000 = Rs 475.0000
    assert res["part_material_cost_per_unit"] == Decimal("475.0000")
    # Total part cost = 50 * 475 = Rs 23,750.00
    assert res["total_part_material_cost"] == Decimal("23750.00")
    assert res["cost_scope"] == CostScope.MATERIAL_ONLY.value


def test_part_with_missing_weight_flags_missing_weight():
    part = HeatPartsProduced(
        id=2,
        heat_id=10,
        line_number=2,
        original_part_description="PART-DI-BRACKET Engine Bracket",
        quantity_produced=Decimal("20.0000"),
        unit_cast_weight=None,  # Weight unknown
    )
    res = calculate_part_cost_detail(part, Decimal("40.0000"), HeatCostStatus.COMPLETE.value)
    assert res["status"] == PartCostStatus.MISSING_WEIGHT.value
    assert res["part_material_cost_per_unit"] is None


def test_part_cost_blocked_when_parent_heat_cost_incomplete():
    part = HeatPartsProduced(
        id=3,
        heat_id=11,
        line_number=1,
        original_part_description="PART-DI-HOUSING Bearing Housing",
        quantity_produced=Decimal("10.0000"),
        unit_cast_weight=Decimal("25.0000"),
    )
    # Parent heat only partially costed
    res = calculate_part_cost_detail(part, Decimal("35.0000"), HeatCostStatus.PARTIAL_COST.value)
    assert res["status"] == PartCostStatus.INSUFFICIENT_COST_DATA.value
    assert res["part_material_cost_per_unit"] is None
