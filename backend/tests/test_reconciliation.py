"""
Tests for Induction Furnace Issue-to-Heat Three-Pass Reconciliation Engine.
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.issue import MaterialIssueHeader, MaterialIssueLineItem, IssueStatus
from app.models.heat import HeatHeader, HeatChargeLine, ProductionStatus
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationResult,
    VarianceClass,
    MatchMethod,
    CandidateMatchStatus,
)


def test_reconciliation_pass1_exact_match_and_tolerance(client: TestClient, db_session: Session):
    """
    Tests Pass 1 exact heat-slip matching, tolerance precedence (max(0.5 kg, 2%)),
    and signed variance (Issued - Charged).
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item_pig = MaterialItem(
        item_code="FDY-RM-010",
        name="Pig Iron Foundry Grade",
        department_id=dept_fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    item_inoc = MaterialItem(
        item_code="FDY-RM-011",
        name="FeSi Inoculant Special",
        department_id=dept_fdy.id,
        category="ALLOY",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add_all([item_pig, item_inoc])
    db_session.commit()

    # Create approved Issue Slip with heat reference H-102603-3721
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261016-0001",
        issue_date=date(2026, 10, 16),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number="H-102603-3721",
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()

    line_pig = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=item_pig.id,
        uom_id=uom_kg.id,
        quantity=Decimal("1000.0000"),  # 2% tol = 20 kg
    )
    line_inoc = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=2,
        material_item_id=item_inoc.id,
        uom_id=uom_kg.id,
        quantity=Decimal("10.0000"),    # 2% tol = 0.2 kg, absolute tol = 0.5 kg -> 0.5 kg applies!
    )
    db_session.add_all([line_pig, line_inoc])

    # Create Heat with raw number 102603-3721 (resolves to H-102603-3721)
    heat = HeatHeader(
        heat_number="102603-3721",
        original_heat_number="102603-3721",
        normalized_heat_number="H-102603-3721",
        heat_date=date(2026, 10, 16),
        furnace_id="F-01",
        production_status=ProductionStatus.COMPLETED.value,
        created_by="usr_fdy",
    )
    db_session.add(heat)
    db_session.flush()

    charge_pig = HeatChargeLine(
        heat_id=heat.id,
        line_number=1,
        material_item_id=item_pig.id,
        original_material_description="Pig Iron Foundry Grade",
        charged_quantity=Decimal("990.0000"),  # Diff = +10 kg (within 20 kg tol -> OK)
        uom_id=uom_kg.id,
    )
    charge_inoc = HeatChargeLine(
        heat_id=heat.id,
        line_number=2,
        material_item_id=item_inoc.id,
        original_material_description="FeSi Inoculant Special",
        charged_quantity=Decimal("9.6000"),   # Diff = +0.4 kg (within 0.5 kg abs tol -> OK)
        uom_id=uom_kg.id,
    )
    db_session.add_all([charge_pig, charge_inoc])
    db_session.commit()

    # Trigger reconciliation
    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-16", "date_to": "2026-10-16"},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert resp.status_code == 201, resp.text
    run_data = resp.json()
    assert run_data["exact_matches_count"] == 2
    assert run_data["discrepancies_count"] == 0

    results = run_data["results"]
    assert len(results) == 2
    for r in results:
        assert r["match_method"] == MatchMethod.EXACT_HEAT_SLIP.value
        assert r["variance_class"] == VarianceClass.OK.value


def test_reconciliation_pass2_batch_and_no_double_counting(client: TestClient, db_session: Session):
    """
    Tests Pass 2 same-day batch aggregation for slips without heat reference,
    and verifies that lines already allocated in Pass 1 are NOT double-counted in Pass 2.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-012",
        name="Steel Scrap Turning",
        department_id=dept_fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    # 1. Exact match pair
    issue_exact = MaterialIssueHeader(
        issue_slip_number="ISS-20261017-0001",
        issue_date=date(2026, 10, 17),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number="H-102603-3730",
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue_exact)
    db_session.flush()
    line_exact = MaterialIssueLineItem(
        issue_id=issue_exact.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom_kg.id,
        quantity=Decimal("500.0000"),
    )
    db_session.add(line_exact)

    heat_exact = HeatHeader(
        heat_number="H-102603-3730",
        original_heat_number="H-102603-3730",
        normalized_heat_number="H-102603-3730",
        heat_date=date(2026, 10, 17),
        furnace_id="F-01",
        production_status=ProductionStatus.COMPLETED.value,
        created_by="usr_fdy",
    )
    db_session.add(heat_exact)
    db_session.flush()
    charge_exact = HeatChargeLine(
        heat_id=heat_exact.id,
        line_number=1,
        material_item_id=item.id,
        original_material_description="Steel Scrap Turning",
        charged_quantity=Decimal("500.0000"),
        uom_id=uom_kg.id,
    )
    db_session.add(charge_exact)

    # 2. Batch pair on same day (without heat reference on slip)
    issue_batch = MaterialIssueHeader(
        issue_slip_number="ISS-20261017-0002",
        issue_date=date(2026, 10, 17),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number=None,  # No heat reference
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue_batch)
    db_session.flush()
    line_batch = MaterialIssueLineItem(
        issue_id=issue_batch.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom_kg.id,
        quantity=Decimal("300.0000"),
    )
    db_session.add(line_batch)

    heat_batch = HeatHeader(
        heat_number="H-102603-3731",
        original_heat_number="H-102603-3731",
        normalized_heat_number="H-102603-3731",
        heat_date=date(2026, 10, 17),
        furnace_id="F-02",
        production_status=ProductionStatus.COMPLETED.value,
        created_by="usr_fdy",
    )
    db_session.add(heat_batch)
    db_session.flush()
    charge_batch = HeatChargeLine(
        heat_id=heat_batch.id,
        line_number=1,
        material_item_id=item.id,
        original_material_description="Steel Scrap Turning",
        charged_quantity=Decimal("300.0000"),
        uom_id=uom_kg.id,
    )
    db_session.add(charge_batch)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-17", "date_to": "2026-10-17"},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert resp.status_code == 201
    run_data = resp.json()
    assert run_data["exact_matches_count"] == 1
    assert run_data["batch_matches_count"] == 1

    # Exact match: 500 vs 500
    exact_res = [r for r in run_data["results"] if r["match_method"] == MatchMethod.EXACT_HEAT_SLIP.value][0]
    assert Decimal(str(exact_res["issued_quantity"])) == Decimal("500.0000")

    # Batch match: exactly 300 vs 300 (line_exact was NOT double counted!)
    batch_res = [r for r in run_data["results"] if r["match_method"] == MatchMethod.SAME_DAY_BATCH.value][0]
    assert Decimal(str(batch_res["issued_quantity"])) == Decimal("300.0000")
    assert Decimal(str(batch_res["charged_quantity"])) == Decimal("300.0000")
    assert batch_res["variance_class"] == VarianceClass.OK.value


def test_reconciliation_pass3_fuzzy_candidate_and_human_confirmation(client: TestClient, db_session: Session):
    """
    Tests Pass 3 advisory fuzzy suggestion for adjacent day / similar reference,
    and human confirmation workflow.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    item = MaterialItem(
        item_code="FDY-RM-013",
        name="Magnesium FeSi Alloy",
        department_id=dept_fdy.id,
        category="ALLOY",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    # Issue on 2026-10-18 with slightly mistyped heat reference '102603-3750-X'
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261018-0001",
        issue_date=date(2026, 10, 18),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number="102603-3750-X",
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()
    line_issue = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=item.id,
        uom_id=uom_kg.id,
        quantity=Decimal("50.0000"),
    )
    db_session.add(line_issue)

    # Heat on next day 2026-10-19 with heat number 'H-102603-3750'
    heat = HeatHeader(
        heat_number="H-102603-3750",
        original_heat_number="H-102603-3750",
        normalized_heat_number="H-102603-3750",
        heat_date=date(2026, 10, 19),
        furnace_id="F-01",
        production_status=ProductionStatus.COMPLETED.value,
        created_by="usr_fdy",
    )
    db_session.add(heat)
    db_session.flush()
    charge = HeatChargeLine(
        heat_id=heat.id,
        line_number=1,
        material_item_id=item.id,
        original_material_description="Magnesium FeSi Alloy",
        charged_quantity=Decimal("50.0000"),
        uom_id=uom_kg.id,
    )
    db_session.add(charge)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-18", "date_to": "2026-10-19"},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert resp.status_code == 201
    run_data = resp.json()
    assert run_data["fuzzy_candidates_count"] >= 1

    candidate = run_data["candidate_matches"][0]
    assert candidate["status"] == CandidateMatchStatus.SUGGESTED.value
    assert "Heat ref similarity" in candidate["suggestion_reason"] or "Date delta" in candidate["suggestion_reason"]

    # Explicit human confirmation
    conf_resp = client.post(
        f"/api/v1/reconciliation/candidates/{candidate['id']}/confirm",
        json={"comments": "Confirmed night shift crossover to furnace 1"},
        headers={"X-User-Role": "Foundry", "X-User-Id": "usr_fdy"},
    )
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["status"] == CandidateMatchStatus.CONFIRMED.value
    assert conf_data["reviewed_by"] == "usr_fdy"
