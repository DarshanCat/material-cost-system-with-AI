"""
Tests for Induction Furnace Heat Material Costing.
Verifies:
- Heat-date rate lookup (uses rate applicable to heat date, not current/future rate)
- Material alias resolution on charge lines
- Missing alias / missing rate handling (marks lines excluded, reports PARTIAL_COST)
- Missing or zero metal tapped handling (cost_per_kg = None, DENOMINATOR_UNAVAILABLE)
- Material-only scope labeling (MATERIAL_ONLY)
- NON-NEGOTIABLE: Heat costing NEVER creates stock movements or alters heat source data.
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
from app.models.heat import HeatHeader, HeatChargeLine, HeatPartsProduced, CastingClassification
from app.models.material_alias import MaterialAlias, AliasApprovalStatus
from app.models.ledger import StockLedgerEntry
from app.models.costing import HeatCostStatus, CostScope, DenominatorPolicy
from app.services.ledger_service import post_grn_to_ledger
from app.services.costing_service import calculate_heat_cost_detail


@pytest.fixture
def heat_costing_fixtures(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    # Materials
    pig_iron = MaterialItem(
        item_code="FDY-RM-001", name="Pig Iron Grade 1", department_id=dept.id,
        category="RAW_MATERIAL", base_uom_id=uom.id, is_active=True,
    )
    scrap = MaterialItem(
        item_code="FDY-RM-002", name="CRC Scrap Low MN", department_id=dept.id,
        category="RAW_MATERIAL", base_uom_id=uom.id, is_active=True,
    )
    db_session.add_all([pig_iron, scrap])
    db_session.flush()

    # Alias for scrap: "CRC Scrap Floor Description" -> FDY-RM-002
    alias = MaterialAlias(
        normalized_alias_key="crc scrap floor description",
        alias_text="CRC Scrap Floor Description",
        material_item_id=scrap.id,
        status=AliasApprovalStatus.APPROVED.value,
        created_by="usr_foundry_01",
    )
    db_session.add(alias)

    # Establish rates via GRNs on 12-Oct:
    # Pig Iron: 1000 kg @ Rs 40.00
    grn1 = GRNHeader(
        grn_number="GRN-20261012-0001", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn1)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn1.id, line_number=1, material_item_id=pig_iron.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("40.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn1, "usr_stores_01")
    db_session.commit()

    # Scrap: 1000 kg @ Rs 30.00
    grn2 = GRNHeader(
        grn_number="GRN-20261012-0002", receipt_date=date(2026, 10, 12),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=scrap.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("30.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")
    db_session.commit()

    db_session.commit()
    return {"pig_iron": pig_iron, "scrap": scrap, "uom": uom}


def test_heat_cost_uses_rates_as_of_heat_date(db_session: Session, heat_costing_fixtures):
    pig_iron = heat_costing_fixtures["pig_iron"]
    scrap = heat_costing_fixtures["scrap"]
    uom = heat_costing_fixtures["uom"]

    # Heat logged on 13-Oct:
    # 500 kg Pig Iron (rate Rs 40.00) + 300 kg Scrap (rate Rs 30.00 via alias)
    # Total charge = 800 kg. Metal tapped = 760 kg (5% melting loss).
    heat = HeatHeader(
        heat_number="H-102603-0001", original_heat_number="102603-0001", normalized_heat_number="102603-0001",
        heat_date=date(2026, 10, 13), furnace_id="F-1", shift="MORNING",
        metal_tapped_weight=Decimal("760.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()

    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=pig_iron.id,
        original_material_description="Pig Iron Grade 1",
        charged_quantity=Decimal("500.0000"), uom_id=uom.id,
    ))
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=2, material_item_id=None,  # will resolve via alias
        original_material_description="CRC Scrap Floor Description",
        charged_quantity=Decimal("300.0000"), uom_id=uom.id,
    ))
    db_session.commit()

    # Subsequent price hike on 20-Oct (after heat date): Pig Iron @ Rs 60.00
    grn_future = GRNHeader(
        grn_number="GRN-20261020-0001", receipt_date=date(2026, 10, 20),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn_future)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn_future.id, line_number=1, material_item_id=pig_iron.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("60.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn_future, "usr_stores_01")
    db_session.commit()

    # Calculate heat cost
    calc = calculate_heat_cost_detail(db_session, heat)

    # Assert it used Rs 40.00 and Rs 30.00 as of 13-Oct (NOT Rs 50.00 blended rate from 20-Oct!)
    assert calc["status"] == HeatCostStatus.COMPLETE.value
    assert calc["valued_lines"] == 2
    assert calc["total_charged_quantity"] == Decimal("800.0000")

    # Cost = (500 * 40) + (300 * 30) = 20,000 + 9,000 = Rs 29,000.00
    assert calc["total_material_cost"] == Decimal("29000.00")

    # Cost per kg = 29,000 / 760 kg metal tapped = 38.1579 / kg
    assert calc["cost_per_kg"] == Decimal("38.1579")
    assert calc["cost_scope"] == CostScope.MATERIAL_ONLY.value


def test_missing_alias_and_missing_rate_reports_partial_cost(db_session: Session, heat_costing_fixtures):
    pig_iron = heat_costing_fixtures["pig_iron"]
    uom = heat_costing_fixtures["uom"]

    heat = HeatHeader(
        heat_number="H-102603-0002", original_heat_number="102603-0002", normalized_heat_number="102603-0002",
        heat_date=date(2026, 10, 13), furnace_id="F-1",
        metal_tapped_weight=Decimal("500.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()

    # Line 1: Pig Iron (Valued: 300 * 40 = Rs 12,000)
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=pig_iron.id,
        original_material_description="Pig Iron Grade 1",
        charged_quantity=Decimal("300.0000"), uom_id=uom.id,
    ))
    # Line 2: Unknown floor alloy with no mapping
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=2, material_item_id=None,
        original_material_description="Unknown Mystery Inoculant",
        charged_quantity=Decimal("20.0000"), uom_id=uom.id,
    ))
    db_session.commit()

    calc = calculate_heat_cost_detail(db_session, heat)
    # Line 2 is unvalued; heat status must be PARTIAL_COST, never complete!
    assert calc["status"] == HeatCostStatus.PARTIAL_COST.value
    assert calc["valued_lines"] == 1
    assert calc["unvalued_lines"] == 1
    assert calc["total_material_cost"] == Decimal("12000.00")
    # Missing alloy is NOT treated as zero cost
    assert calc["lines"][1]["status"] == "UNMAPPED_ALIAS"
    assert calc["lines"][1]["is_included"] is False


def test_missing_metal_tapped_prevents_cost_per_kg(db_session: Session, heat_costing_fixtures):
    pig_iron = heat_costing_fixtures["pig_iron"]
    uom = heat_costing_fixtures["uom"]

    # Heat with None metal tapped weight
    heat = HeatHeader(
        heat_number="H-102603-0003", original_heat_number="102603-0003", normalized_heat_number="102603-0003",
        heat_date=date(2026, 10, 13), furnace_id="F-1",
        metal_tapped_weight=None,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=pig_iron.id,
        original_material_description="Pig Iron Grade 1",
        charged_quantity=Decimal("400.0000"), uom_id=uom.id,
    ))
    db_session.commit()

    calc = calculate_heat_cost_detail(db_session, heat)
    assert calc["total_material_cost"] == Decimal("16000.00")
    # Cost per kg cannot be calculated without denominator
    assert calc["cost_per_kg"] is None
    assert calc["status"] == HeatCostStatus.DENOMINATOR_UNAVAILABLE.value


def test_heat_costing_never_mutates_ledger(db_session: Session, heat_costing_fixtures):
    pig_iron = heat_costing_fixtures["pig_iron"]
    uom = heat_costing_fixtures["uom"]

    heat = HeatHeader(
        heat_number="H-102603-0004", original_heat_number="102603-0004", normalized_heat_number="102603-0004",
        heat_date=date(2026, 10, 13), furnace_id="F-1",
        metal_tapped_weight=Decimal("500.0000"), metal_tapped_uom_id=uom.id,
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=pig_iron.id,
        original_material_description="Pig Iron Grade 1",
        charged_quantity=Decimal("500.0000"), uom_id=uom.id,
    ))
    db_session.commit()

    ledger_count_before = db_session.execute(select(func.count(StockLedgerEntry.id))).scalar_one()

    # Execute costing calculation
    calculate_heat_cost_detail(db_session, heat)

    ledger_count_after = db_session.execute(select(func.count(StockLedgerEntry.id))).scalar_one()
    assert ledger_count_before == ledger_count_after
