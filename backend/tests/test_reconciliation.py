from tests.auth_helpers import bearer
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
        headers=bearer("Foundry"),
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
        headers=bearer("Foundry"),
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
        headers=bearer("Foundry"),
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
        headers=bearer("Foundry"),
    )
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["status"] == CandidateMatchStatus.CONFIRMED.value
    assert conf_data["reviewed_by"] == "usr_foundry_01"


def test_reconciliation_slax_override_segregated(client: TestClient, db_session: Session):
    """
    Verifies that Slax (FDY-RM-021) with an approved NON_HEAT_SPECIFIC override is
    segregated before Pass 1 with MatchMethod.CONSUMABLE_SEGREGATED, does not enter
    furnace bath comparison, and generates zero UNMATCHED_SLIP discrepancies.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    slax_item = MaterialItem(
        item_code="FDY-RM-021",
        name="Slax Slag Coagulant",
        department_id=dept_fdy.id,
        category="Raw Material",
        subcategory="Slag Coagulants",
        reconciliation_category="NON_HEAT_SPECIFIC",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(slax_item)
    db_session.commit()

    # Approved issue slip for Slax with blank heat reference (e.g. 50 kg bag)
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261021-0001",
        issue_date=date(2026, 10, 21),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number=None,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()

    line = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=slax_item.id,
        uom_id=uom_kg.id,
        quantity=Decimal("50.0000"),
    )
    db_session.add(line)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-21", "date_to": "2026-10-21"},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 201, resp.text
    run_data = resp.json()
    assert run_data["discrepancies_count"] == 0

    results = run_data["results"]
    assert len(results) == 1
    assert results[0]["match_method"] == MatchMethod.CONSUMABLE_SEGREGATED.value
    assert results[0]["variance_class"] == VarianceClass.OK.value
    assert results[0]["status"] == "SEGREGATED"
    assert "Floor consumable" in results[0]["notes"]


def test_reconciliation_moulding_consumables_nomenclature_default(client: TestClient, db_session: Session):
    """
    Verifies that moulding consumables (e.g. Bentonite FDY-MD-002) without explicit override
    dynamically default to NON_HEAT_SPECIFIC based on Nomenclature Standard v1.0,
    and are segregated with zero UNMATCHED_SLIP errors.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    bentonite = MaterialItem(
        item_code="FDY-MD-002",
        name="Foundry Bentonite Powder",
        department_id=dept_fdy.id,
        category="Moulding Material",
        subcategory="Binders",
        reconciliation_category=None,  # Null: uses nomenclature default
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(bentonite)
    db_session.commit()

    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261022-0001",
        issue_date=date(2026, 10, 22),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number=None,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()

    line = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=bentonite.id,
        uom_id=uom_kg.id,
        quantity=Decimal("500.0000"),
    )
    db_session.add(line)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-22", "date_to": "2026-10-22"},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 201, resp.text
    run_data = resp.json()
    assert run_data["discrepancies_count"] == 0
    assert run_data["results"][0]["match_method"] == MatchMethod.CONSUMABLE_SEGREGATED.value


def test_reconciliation_unreferenced_raw_material_anti_concealment(client: TestClient, db_session: Session):
    """
    Anti-concealment test: Verifies that a true melting raw material (Pig Iron FDY-RM-001)
    issued WITHOUT a heat reference is NEVER treated as a floor consumable.
    If unmatched in Pass 2, it is flagged as UNMATCHED_SLIP to ensure physical stock is tracked.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    pig_item = MaterialItem(
        item_code="FDY-RM-001",
        name="Pig Iron Foundry Grade 1",
        department_id=dept_fdy.id,
        category="Raw Material",
        subcategory="Ferrous Raw Material",
        reconciliation_category=None,  # Null: defaults to HEAT_TRACEABLE
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(pig_item)
    db_session.commit()

    # Issued 2500 kg of Pig Iron with NO heat reference on date 2026-10-23
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261023-0001",
        issue_date=date(2026, 10, 23),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number=None,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()

    line = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=pig_item.id,
        uom_id=uom_kg.id,
        quantity=Decimal("2500.0000"),
    )
    db_session.add(line)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-23", "date_to": "2026-10-23"},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 201, resp.text
    run_data = resp.json()

    # Must NOT be segregated! Must produce an UNMATCHED_SLIP discrepancy!
    assert run_data["discrepancies_count"] == 1
    assert run_data["results"][0]["match_method"] == MatchMethod.UNMATCHED_SLIP.value
    assert run_data["results"][0]["variance_class"] == VarianceClass.UNMATCHED_SLIP.value
    assert run_data["results"][0]["status"] == "FLAGGED"


def test_reconciliation_department_scope_exclusion(client: TestClient, db_session: Session):
    """
    Verifies that non-Foundry issues (e.g. Machine Shop inserts or Maintenance oils)
    are excluded from furnace melt reconciliation without modifying stock ledger entries.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_mcs = db_session.query(Department).filter_by(code="MSP").first()
    uom_nos = db_session.query(UOM).filter_by(code="NOS").first()

    tool_item = MaterialItem(
        item_code="MCS-IT-001",
        name="CNMG Turning Insert",
        department_id=dept_mcs.id,
        category="Inserts & Tools",
        subcategory="CNC Inserts",
        base_uom_id=uom_nos.id,
        is_active=True,
    )
    db_session.add(tool_item)
    db_session.commit()

    # Issue to Machine Shop
    issue_mcs = MaterialIssueHeader(
        issue_slip_number="ISS-20261024-0001",
        issue_date=date(2026, 10, 24),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_mcs.id,  # Machine Shop
        heat_reference_number=None,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue_mcs)
    db_session.flush()

    line = MaterialIssueLineItem(
        issue_id=issue_mcs.id,
        line_number=1,
        material_item_id=tool_item.id,
        uom_id=uom_nos.id,
        quantity=Decimal("10.0000"),
    )
    db_session.add(line)
    db_session.commit()

    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-24", "date_to": "2026-10-24"},
        headers=bearer("Foundry"),
    )
    assert resp.status_code == 201, resp.text
    run_data = resp.json()

    # Machine shop issue was excluded: total evaluated is 0
    assert run_data["total_evaluated_count"] == 0
    assert run_data["discrepancies_count"] == 0


def test_reconciliation_item_override_management_api(client: TestClient, db_session: Session):
    """
    Verifies that Management users can update reconciliation_category via the items API,
    requiring change_reason and creating an immutable entry in ItemMasterAuditLog.
    """
    from app.models.item_code import ItemMasterAuditLog

    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    test_item = MaterialItem(
        item_code="FDY-RM-099",
        name="Experimental Slag Binder",
        department_id=dept_fdy.id,
        category="Raw Material",
        reconciliation_category=None,
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(test_item)
    db_session.commit()

    # Attempt without reason -> fails with 400
    fail_resp = client.put(
        f"/api/v1/items/{test_item.id}",
        json={"reconciliation_category": "NON_HEAT_SPECIFIC"},
        headers=bearer("Management"),
    )
    assert fail_resp.status_code == 400

    # With valid reason -> succeeds
    succ_resp = client.put(
        f"/api/v1/items/{test_item.id}",
        json={
            "reconciliation_category": "NON_HEAT_SPECIFIC",
            "change_reason": "Approved slag binder as non-heat floor consumable after plant review.",
        },
        headers=bearer("Management"),
    )
    assert succ_resp.status_code == 200
    data = succ_resp.json()
    assert data["reconciliation_category"] == "NON_HEAT_SPECIFIC"

    # Audit log check
    audit = db_session.query(ItemMasterAuditLog).filter_by(
        material_item_id=test_item.id, field_name="reconciliation_category"
    ).first()
    assert audit is not None
    assert audit.new_value == "NON_HEAT_SPECIFIC"
    assert "Approved slag binder" in audit.reason


def test_reconciliation_segregated_consumables_metrics_and_serialization(client: TestClient, db_session: Session):
    """
    Tests that Pass 0 segregates floor consumables, records correct match_method and status,
    and returns derived segregated_consumables_count, segregated_consumables_quantity,
    and nested material_item in the API run detail and list endpoints.
    """
    dept_stores = db_session.query(Department).filter_by(code="GNS").first()
    dept_fdy = db_session.query(Department).filter_by(code="FDY").first()
    uom_kg = db_session.query(UOM).filter_by(code="KG").first()

    # Create Slax item (classified as non-heat-specific floor consumable)
    item_slax = MaterialItem(
        item_code="FDY-RM-021",
        name="Slax Slag Coagulant",
        department_id=dept_fdy.id,
        category="RAW_MATERIAL",
        base_uom_id=uom_kg.id,
        is_active=True,
    )
    db_session.add(item_slax)
    db_session.commit()

    # Create approved Issue Slip issued to Foundry without heat reference
    issue = MaterialIssueHeader(
        issue_slip_number="ISS-20261016-0099",
        issue_date=date(2026, 10, 16),
        issuing_department_id=dept_stores.id,
        receiving_department_id=dept_fdy.id,
        heat_reference_number=None,
        status=IssueStatus.APPROVED.value,
        created_by="usr_stores",
    )
    db_session.add(issue)
    db_session.flush()

    line_slax = MaterialIssueLineItem(
        issue_id=issue.id,
        line_number=1,
        material_item_id=item_slax.id,
        uom_id=uom_kg.id,
        quantity=Decimal("50.0000"),
    )
    db_session.add(line_slax)
    db_session.commit()

    # Trigger reconciliation run via API
    resp = client.post(
        "/api/v1/reconciliation/run",
        json={"date_from": "2026-10-16", "date_to": "2026-10-16"},
        headers=bearer("Management"),
    )
    assert resp.status_code == 201
    run_data = resp.json()
    run_id = run_data["id"]
    assert run_data["segregated_consumables_count"] >= 1
    assert Decimal(str(run_data["segregated_consumables_quantity"])) >= Decimal("50.0000")

    # Fetch run detail
    detail_resp = client.get(f"/api/v1/reconciliation/runs/{run_id}", headers=bearer("Management"))
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["segregated_consumables_count"] >= 1
    assert Decimal(str(detail["segregated_consumables_quantity"])) >= Decimal("50.0000")

    # Inspect results inside detail
    seg_results = [r for r in detail["results"] if r["match_method"] == "CONSUMABLE_SEGREGATED"]
    assert len(seg_results) >= 1
    target = next((r for r in seg_results if r["material_item_id"] == item_slax.id), None)
    assert target is not None
    assert target["material_item"] is not None
    assert target["material_item"]["item_code"] == "FDY-RM-021"
    assert target["material_item"]["name"] == "Slax Slag Coagulant"
    assert "ISS-20261016-0099" in target["notes"]
    assert target["status"] == "SEGREGATED"

    # List runs endpoint
    list_resp = client.get("/api/v1/reconciliation/runs?limit=10", headers=bearer("Management"))
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    items = list_data if isinstance(list_data, list) else list_data.get("items", [])
    run_in_list = next((r for r in items if r["id"] == run_id), None)
    assert run_in_list is not None
    assert run_in_list["segregated_consumables_count"] >= 1

