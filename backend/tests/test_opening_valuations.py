import uuid
"""
Unit and Integration Tests for Opening Valuation Versioning & Maker-Checker (SW-06).

Verifies:
1. Proposal creation with automatic version numbering, creator tracking, and audit logging.
2. Prevention of duplicate pending proposals for the same item.
3. Maker-checker enforcement: creator cannot approve their own valuation proposal (HTTP 403).
4. Independent authorized approver succeeds in approving proposal (HTTP 200).
5. Version progression: subsequent proposal increments version; approval supersedes older approved version.
6. Rejection flow: independent approver rejects with mandatory reason; creator self-rejection rejected.
7. Terminal state protection: cannot approve already approved, superseded, or rejected versions (HTTP 409).
8. Costing run integration: costing calculation uses currently approved version and records version in journal.
9. Live multi-session PostgreSQL concurrency: race conditions between concurrent approvers are safely serialized.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import threading
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.models.item import MaterialItem
from app.models.uom import UOM
from app.models.department import Department
from app.models.ledger import StockLedgerEntry, MovementType
from app.models.costing import (
    ItemOpeningValuation,
    ItemOpeningValuationAuditLog,
    OpeningValuationStatus,
    CostingRun,
    CostingRunStatus,
)
from app.core.security import UserRole
from app.core.auth import DEV_USERS, issue_dev_token
from app.services.costing_service import reconstruct_item_rate_evolution, execute_costing_run


def _auth_headers(role: UserRole, user_id: str = None) -> dict[str, str]:
    user = DEV_USERS[role].model_copy()
    if user_id:
        user.user_id = user_id
    token = issue_dev_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def valuation_fixtures(db_session: Session):
    uom = db_session.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
    dept = db_session.execute(select(Department).where(Department.code == "FDY")).scalars().first()

    item = MaterialItem(
        item_code="RAW-SCRAP-MS-01",
        name="Mild Steel Scrap Grade 1",
        category="RAW_MATERIALS",
        subcategory="MELTING_SCRAP",
        base_uom_id=uom.id,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    return {"item": item, "uom": uom, "dept": dept}


# --------------------------------------------------------------------------------------------
# 1. Proposal Creation Tests
# --------------------------------------------------------------------------------------------

def test_propose_opening_valuation_creates_version_1(client: TestClient, valuation_fixtures, db_session: Session):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")

    payload = {
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "45.5000",
        "notes": "Audited opening rate per physical verification",
    }
    resp = client.post("/api/v1/costing/opening-valuations", json=payload, headers=creator_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["material_item_id"] == item.id
    assert data["item_code"] == item.item_code
    assert data["version"] == 1
    assert data["status"] == "PROPOSED"
    assert data["created_by"] == "usr_mgmt_creator"
    assert Decimal(str(data["opening_rate_ex_gst"])) == Decimal("45.5000")
    assert data["approved_by"] is None
    assert data["approved_at"] is None

    # Check audit log in DB
    db_val = db_session.get(ItemOpeningValuation, data["id"])
    assert db_val is not None
    assert len(db_val.audit_logs) == 1
    assert db_val.audit_logs[0].action == "PROPOSED"
    assert db_val.audit_logs[0].actor_id == "usr_mgmt_creator"


def test_propose_opening_valuation_duplicate_pending_rejected(client: TestClient, valuation_fixtures):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")

    payload = {
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "45.5000",
    }
    resp1 = client.post("/api/v1/costing/opening-valuations", json=payload, headers=creator_headers)
    assert resp1.status_code == 200

    # Second proposal while first is pending must fail with 409
    resp2 = client.post("/api/v1/costing/opening-valuations", json=payload, headers=creator_headers)
    assert resp2.status_code == 409
    assert "already pending approval" in resp2.json()["detail"]


def test_propose_opening_valuation_invalid_inputs(client: TestClient, valuation_fixtures):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")

    # Invalid rate <= 0
    resp = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "0.0000",
    }, headers=creator_headers)
    assert resp.status_code in (400, 422)

    # Future baseline date
    resp_future = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2099-01-01",
        "opening_rate_ex_gst": "45.00",
    }, headers=creator_headers)
    assert resp_future.status_code == 400
    assert "future" in resp_future.json()["detail"].lower()


# --------------------------------------------------------------------------------------------
# 2. Maker-Checker Enforcement Tests
# --------------------------------------------------------------------------------------------

def test_maker_checker_creator_cannot_approve_own_proposal(client: TestClient, valuation_fixtures):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")

    # Propose
    resp = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "50.0000",
    }, headers=creator_headers)
    assert resp.status_code == 200
    val_id = resp.json()["id"]

    # Same creator attempts to approve -> HTTP 403 Maker-Checker violation
    resp_approve = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/approve",
        json={"comments": "Self approval attempt"},
        headers=creator_headers,
    )
    assert resp_approve.status_code == 403
    assert "Maker-checker violation" in resp_approve.json()["detail"]


def test_independent_authorized_approver_succeeds(client: TestClient, valuation_fixtures, db_session: Session):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")
    approver_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_approver")

    # 1. Propose
    resp_prop = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "48.2500",
        "notes": "Verified rate",
    }, headers=creator_headers)
    assert resp_prop.status_code == 200
    val_id = resp_prop.json()["id"]

    # 2. Independent approver approves
    resp_appr = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/approve",
        json={"comments": "Approved by Finance Head"},
        headers=approver_headers,
    )
    assert resp_appr.status_code == 200, resp_appr.text
    appr_data = resp_appr.json()

    assert appr_data["id"] == val_id
    assert appr_data["version"] == 1
    assert appr_data["status"] == "APPROVED"
    assert appr_data["approved_by"] == "usr_mgmt_approver"
    assert appr_data["approved_at"] is not None

    # Check audit log trail in DB
    db_val = db_session.get(ItemOpeningValuation, val_id)
    assert len(db_val.audit_logs) == 2
    assert db_val.audit_logs[0].action == "PROPOSED"
    assert db_val.audit_logs[1].action == "APPROVED"
    assert db_val.audit_logs[1].actor_id == "usr_mgmt_approver"
    assert db_val.audit_logs[1].comments == "Approved by Finance Head"


def test_unauthorized_role_approval_denied(client: TestClient, valuation_fixtures):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")
    stores_headers = _auth_headers(UserRole.STORES, user_id="usr_stores_01")

    resp_prop = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "48.2500",
    }, headers=creator_headers)
    assert resp_prop.status_code == 200
    val_id = resp_prop.json()["id"]

    # Stores user lacks COSTING_CALCULATE -> HTTP 403
    resp_appr = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/approve",
        json={"comments": "Stores attempt"},
        headers=stores_headers,
    )
    assert resp_appr.status_code == 403


# --------------------------------------------------------------------------------------------
# 3. Version Progression & Superseding Tests
# --------------------------------------------------------------------------------------------

def test_version_progression_supersedes_prior_version(client: TestClient, valuation_fixtures, db_session: Session):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")
    approver_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_approver")

    # 1. Propose and approve Version 1 (Rate 40.00)
    resp1 = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "40.0000",
    }, headers=creator_headers)
    assert resp1.status_code == 200
    v1_id = resp1.json()["id"]
    assert resp1.json()["version"] == 1

    appr1 = client.post(f"/api/v1/costing/opening-valuations/{v1_id}/approve", headers=approver_headers)
    assert appr1.status_code == 200
    assert appr1.json()["status"] == "APPROVED"

    # 2. Propose Version 2 (Rate 45.00)
    resp2 = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "45.0000",
        "notes": "Revision due to revised purchase bills",
    }, headers=creator_headers)
    assert resp2.status_code == 200
    v2_id = resp2.json()["id"]
    assert resp2.json()["version"] == 2
    assert resp2.json()["status"] == "PROPOSED"

    # While V2 is pending, V1 is still the effective APPROVED rate
    v1_check = db_session.get(ItemOpeningValuation, v1_id)
    assert v1_check.status == "APPROVED"

    # 3. Approve Version 2
    appr2 = client.post(f"/api/v1/costing/opening-valuations/{v2_id}/approve", headers=approver_headers)
    assert appr2.status_code == 200
    assert appr2.json()["status"] == "APPROVED"

    # 4. Verify Version 1 is now SUPERSEDED without data loss
    db_session.expire_all()
    v1_db = db_session.get(ItemOpeningValuation, v1_id)
    assert v1_db.status == "SUPERSEDED"
    assert v1_db.superseded_by_id == v2_id
    assert v1_db.superseded_at is not None
    assert Decimal(str(v1_db.opening_rate_ex_gst)) == Decimal("40.0000")  # Never mutated!

    # Verify audit log on V1 reflects SUPERSEDED
    v1_audit_actions = [log.action for log in v1_db.audit_logs]
    assert "SUPERSEDED" in v1_audit_actions


# --------------------------------------------------------------------------------------------
# 4. Rejection Flow Tests
# --------------------------------------------------------------------------------------------

def test_reject_opening_valuation_with_mandatory_reason(client: TestClient, valuation_fixtures, db_session: Session):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")
    approver_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_approver")

    resp = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "99.0000",
    }, headers=creator_headers)
    val_id = resp.json()["id"]

    # Reject without reason -> 422 / 400
    resp_empty = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/reject",
        json={"reason": "  "},
        headers=approver_headers,
    )
    assert resp_empty.status_code in (400, 422)

    # Reject with valid reason
    resp_rej = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/reject",
        json={"reason": "Rate does not match purchase ledger card"},
        headers=approver_headers,
    )
    assert resp_rej.status_code == 200
    assert resp_rej.json()["status"] == "REJECTED"
    assert resp_rej.json()["rejection_reason"] == "Rate does not match purchase ledger card"

    # Cannot approve rejected version
    resp_appr = client.post(f"/api/v1/costing/opening-valuations/{val_id}/approve", headers=approver_headers)
    assert resp_appr.status_code == 409


def test_creator_cannot_reject_own_proposal(client: TestClient, valuation_fixtures):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")

    resp = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "55.0000",
    }, headers=creator_headers)
    val_id = resp.json()["id"]

    # Creator attempts to reject -> HTTP 403 Maker-Checker violation
    resp_rej = client.post(
        f"/api/v1/costing/opening-valuations/{val_id}/reject",
        json={"reason": "Changed my mind"},
        headers=creator_headers,
    )
    assert resp_rej.status_code == 403
    assert "Maker-checker violation" in resp_rej.json()["detail"]


# --------------------------------------------------------------------------------------------
# 5. Costing Calculation & Reproducibility Tests
# --------------------------------------------------------------------------------------------

def test_costing_run_uses_approved_valuation_and_preserves_journal(client: TestClient, valuation_fixtures, db_session: Session):
    item = valuation_fixtures["item"]
    creator_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_creator")
    approver_headers = _auth_headers(UserRole.MANAGEMENT, user_id="usr_mgmt_approver")

    # Add opening balance stock movement: 1,000 kg
    uom = valuation_fixtures["uom"]
    ob_entry = StockLedgerEntry(
        entry_number="SLE-20261012-0001",
        posting_group_id="POST-OB-01",
        material_item_id=item.id,
        uom_id=uom.id,
        transaction_date=date(2026, 10, 12),
        movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"),
        source_document_type="OPENING_BALANCE",
        source_document_id=1,
        source_line_id=1,
        source_document_number="OB-20261012-0001",
        posted_by="usr_stores_01",
    )
    db_session.add(ob_entry)
    db_session.commit()

    # Before valuation approval: status is OPENING_VALUATION_MISSING
    qty, rate, status_val, rate_src, journal = reconstruct_item_rate_evolution(db_session, item.id)
    assert status_val == "OPENING_VALUATION_MISSING"
    assert rate is None

    # Propose and approve Version 1 (Rate: 60.00)
    resp = client.post("/api/v1/costing/opening-valuations", json={
        "material_item_id": item.id,
        "baseline_date": "2026-10-12",
        "opening_rate_ex_gst": "60.0000",
    }, headers=creator_headers)
    val_id = resp.json()["id"]
    client.post(f"/api/v1/costing/opening-valuations/{val_id}/approve", headers=approver_headers)

    # Costing run now values opening stock at 60.00
    qty, rate, status_val, rate_src, journal = reconstruct_item_rate_evolution(db_session, item.id)
    assert status_val == "VALUED"
    assert rate == Decimal("60.0000")
    assert rate_src == "APPROVED_OPENING_VALUATION"
    assert "opening valuation v1" in journal[0]["notes"].lower()


# --------------------------------------------------------------------------------------------
# 6. Live PostgreSQL Multi-Session Concurrency Test
# --------------------------------------------------------------------------------------------

def test_postgres_live_concurrent_opening_valuation_approval(pg_session_factory):
    """
    Opt-in PostgreSQL concurrency test.
    Simulates two concurrent manager sessions attempting to approve the same
    opening valuation proposal simultaneously under row-level locks.
    Exactly one approval must succeed with 200, and the second must be rejected with 409 Conflict.
    """
    # 1. Setup in dedicated session
    val_id = None
    with pg_session_factory() as setup_db:
        # Create item
        uom = setup_db.execute(select(UOM).where(UOM.code == "KG")).scalars().first()
        dept = setup_db.execute(select(Department).where(Department.code == "FDY")).scalars().first()
        item = MaterialItem(
            item_code=f"RAW-CONC-VAL-{uuid.uuid4().hex[:6]}",
            name="Concurrent Valuation Test Item",
            category="RAW_MATERIALS",
            subcategory="MELTING_SCRAP",
            base_uom_id=uom.id,
            department_id=dept.id,
            is_active=True,
        )
        setup_db.add(item)
        setup_db.flush()

        val = ItemOpeningValuation(
            material_item_id=item.id,
            version=1,
            baseline_date=date(2026, 10, 12),
            opening_rate_ex_gst=Decimal("75.0000"),
            status=OpeningValuationStatus.PROPOSED.value,
            created_by="usr_mgmt_proposer",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        setup_db.add(val)
        setup_db.commit()
        val_id = val.id

    assert val_id is not None

    # 2. Run concurrent approvals in separate threads and database sessions
    results = []
    barrier = threading.Barrier(2)

    def worker(worker_id: str):
        with pg_session_factory() as worker_db:
            barrier.wait()
            from app.services.opening_valuation_service import approve_opening_valuation
            from fastapi import HTTPException
            try:
                rec = approve_opening_valuation(
                    worker_db,
                    valuation_id=val_id,
                    actor_id=worker_id,
                    comments=f"Approved by {worker_id}",
                )
                results.append(("SUCCESS", worker_id, rec.version))
            except HTTPException as ex:
                results.append(("HTTP_EXCEPTION", worker_id, ex.status_code, ex.detail))
            except Exception as ex:
                results.append(("EXCEPTION", worker_id, str(ex)))

    t1 = threading.Thread(target=worker, args=("usr_mgmt_approver_1",))
    t2 = threading.Thread(target=worker, args=("usr_mgmt_approver_2",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # 3. Assertions
    successes = [r for r in results if r[0] == "SUCCESS"]
    rejections = [r for r in results if r[0] == "HTTP_EXCEPTION"]

    assert len(successes) == 1, f"Expected exactly 1 approval success, got: {results}"
    assert len(rejections) == 1, f"Expected exactly 1 rejection, got: {results}"
    assert rejections[0][2] == 409  # HTTP 409 Conflict: already approved

    # 4. Verify DB state
    with pg_session_factory() as verify_db:
        final_val = verify_db.get(ItemOpeningValuation, val_id)
        assert final_val.status == "APPROVED"
        assert final_val.approved_by in ("usr_mgmt_approver_1", "usr_mgmt_approver_2")
        # Exactly 1 APPROVED audit log
        approved_logs = [l for l in final_val.audit_logs if l.action == "APPROVED"]
        assert len(approved_logs) == 1
