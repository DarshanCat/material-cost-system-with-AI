from tests.auth_helpers import bearer
"""
Tests for Costing Run Auditability, Recalculation Integrity, and Comparison.
Verifies:
- Costing run history is versioned and permanently preserved
- Recalculation never erases or modifies prior runs
- Side-by-side run comparison highlights valuation and rate deltas
- Role-based authorization controls access to costing endpoints
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.grn import GRNHeader, GRNLineItem, GRNStatus, GRNSourceType
from app.models.heat import HeatHeader, HeatChargeLine
from app.models.costing import CostingRun, CostingRunStatus
from app.services.ledger_service import post_grn_to_ledger
from app.services.costing_service import execute_costing_run, compare_costing_runs


@pytest.fixture
def run_fixtures(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-001", name="Pig Iron Grade 1", department_id=dept.id,
        category="RAW_MATERIAL", base_uom_id=uom.id, is_active=True,
    )
    db_session.add(item)
    db_session.flush()

    # Initial GRN: 1000 kg @ Rs 40.00
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
    db_session.commit()

    # Heat on 13-Oct: 500 kg Pig Iron, 480 kg tapped
    heat = HeatHeader(
        heat_number="H-102603-0001", original_heat_number="102603-0001", normalized_heat_number="102603-0001",
        heat_date=date(2026, 10, 13), furnace_id="F-1", metal_tapped_weight=Decimal("480.0000"),
        created_by="usr_foundry_01",
    )
    db_session.add(heat)
    db_session.flush()
    db_session.add(HeatChargeLine(
        heat_id=heat.id, line_number=1, material_item_id=item.id,
        original_material_description="Pig Iron Grade 1", charged_quantity=Decimal("500.0000"),
        uom_id=uom.id,
    ))

    db_session.commit()
    return {"item": item, "uom": uom, "heat": heat}


def test_costing_run_versioning_and_recalculation_preservation(db_session: Session, run_fixtures):
    # 1. Execute Run 1 as of 14-Oct
    run1 = execute_costing_run(
        db=db_session,
        period_start=date(2026, 10, 12),
        period_end=date(2026, 10, 14),
        as_of_date=date(2026, 10, 14),
        actor_id="usr_mgmt_01",
        notes="Baseline calculation run 1",
    )
    assert run1.status == CostingRunStatus.COMPLETED.value
    assert run1.total_inventory_valuation == Decimal("40000.00")
    run1_id = run1.id

    # 2. Add another receipt at Rs 60.00 on 15-Oct
    item = run_fixtures["item"]
    uom = run_fixtures["uom"]
    grn2 = GRNHeader(
        grn_number="GRN-20261015-0001", receipt_date=date(2026, 10, 15),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("60.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")
    db_session.commit()

    # 3. Execute Run 2 as of 16-Oct
    run2 = execute_costing_run(
        db=db_session,
        period_start=date(2026, 10, 12),
        period_end=date(2026, 10, 16),
        as_of_date=date(2026, 10, 16),
        actor_id="usr_mgmt_01",
        notes="Recalculation run 2 with second receipt",
    )
    assert run2.status == CostingRunStatus.COMPLETED.value
    # Run 2 valuation: 2000 kg @ Rs 50.00 = Rs 100,000.00
    assert run2.total_inventory_valuation == Decimal("100000.00")

    # Assert Run 1 is completely preserved and untouched
    db_session.refresh(run1)
    assert run1.id == run1_id
    assert run1.total_inventory_valuation == Decimal("40000.00")
    assert run1.run_number != run2.run_number


def test_compare_two_costing_runs(db_session: Session, run_fixtures):
    # Run 1
    run1 = execute_costing_run(
        db=db_session, period_start=date(2026, 10, 12), period_end=date(2026, 10, 14),
        as_of_date=date(2026, 10, 14), actor_id="usr_mgmt_01",
    )

    # Receipt addition
    item = run_fixtures["item"]
    uom = run_fixtures["uom"]
    grn2 = GRNHeader(
        grn_number="GRN-20261015-0001", receipt_date=date(2026, 10, 15),
        source_type=GRNSourceType.EXTERNAL_VENDOR.value, status=GRNStatus.APPROVED.value,
        created_by="usr_stores_01",
    )
    db_session.add(grn2)
    db_session.flush()
    db_session.add(GRNLineItem(grn_id=grn2.id, line_number=1, material_item_id=item.id, uom_id=uom.id,
                               quantity=Decimal("1000.0000"), rate_ex_gst=Decimal("60.00")))
    db_session.commit()
    post_grn_to_ledger(db_session, grn2, "usr_stores_01")
    db_session.commit()

    # Run 2
    run2 = execute_costing_run(
        db=db_session, period_start=date(2026, 10, 12), period_end=date(2026, 10, 16),
        as_of_date=date(2026, 10, 16), actor_id="usr_mgmt_01",
    )

    comp = compare_costing_runs(db_session, run1.id, run2.id)

    assert comp["summary"]["valuation_run_1"] == 40000.0
    assert comp["summary"]["valuation_run_2"] == 100000.0
    assert comp["summary"]["valuation_delta"] == 60000.0

    assert len(comp["item_differences"]) == 1
    diff = comp["item_differences"][0]
    assert diff["run_1_rate"] == 40.0
    assert diff["run_2_rate"] == 50.0
    assert diff["rate_delta"] == 10.0


def test_costing_api_permissions(client: TestClient, run_fixtures):
    # Stores role has no costing calculate permission -> 403 Forbidden
    resp = client.post(
        "/api/v1/costing/runs",
        json={
            "period_start": "2026-10-12",
            "period_end": "2026-10-14",
            "as_of_date": "2026-10-14",
            "denominator_policy": "METAL_TAPPED",
        },
        headers=bearer("Stores"),
    )
    assert resp.status_code == 403

    # Management role has costing calculate permission -> 200 OK
    resp_mgmt = client.post(
        "/api/v1/costing/runs",
        json={
            "period_start": "2026-10-12",
            "period_end": "2026-10-14",
            "as_of_date": "2026-10-14",
            "denominator_policy": "METAL_TAPPED",
        },
        headers=bearer("Management"),
    )
    assert resp_mgmt.status_code == 200
    data = resp_mgmt.json()
    assert data["status"] == "COMPLETED"
    assert data["run_number"].startswith("CRUN-20261014-")
