"""
Phase 1B: Audit Trail Integrity Remediation Test Suite.

Verifies remediation of external review Observation 27:
1. Viewing a transaction is strictly read-only: does not alter creation, approval,
   or posting timestamps, and does not alter audit logs.
2. Actor identity is authoritative and server-derived: client cannot forge or substitute
   creator, approver, or poster identity.
3. Audit timestamps are assigned server-side in UTC, not accepted from client.
4. Audit trail is append-only: reversals retain all historical audit log entries and
   append a new REVERSED entry with full audit justification.
5. No application routes exist to update or delete audit records (immutability).
6. Protected endpoints reject unauthenticated access (fail closed).
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import AuthenticatedUser, UserRole
from app.models.department import Department
from app.models.grn import GRNHeader, GRNAuditLog, GRNStatus
from app.models.issue import MaterialIssueHeader, IssueAuditLog, IssueStatus
from app.models.item import MaterialItem
from app.models.uom import UOM
from tests.auth_helpers import bearer


@pytest.fixture
def audit_test_env(db_session: Session):
    fdy = db_session.query(Department).filter_by(code="FDY").first()
    gns = db_session.query(Department).filter_by(code="GNS").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(
        item_code="AUDIT-RM-TEST-01",
        name="Audit Trail Test Ingot",
        department_id=fdy.id,
        category="RAW_MATERIALS",
        base_uom_id=kg.id,
    )
    db_session.add(item)
    db_session.commit()
    return {"fdy": fdy, "gns": gns, "kg": kg, "item": item}


def _grn_payload(env):
    return {
        "receipt_date": str(date.today()),
        "source_type": "INTERNAL_VSPL",
        "lines": [{
            "line_number": 1,
            "material_item_id": env["item"].id,
            "uom_id": env["kg"].id,
            "quantity": "100.00",
            "unit_cost": "50.00",
            "heat_number": "HEAT-AUDIT-001",
        }],
    }


def test_viewing_transaction_does_not_alter_timestamps_or_audit_logs(client: TestClient, db_session: Session, audit_test_env):
    """
    Observation 27: Viewing a transaction should not alter its creation, approval,
    or posting timestamps.
    """
    creator_headers = bearer(UserRole.STORES)
    approver_headers = bearer(UserRole.MANAGEMENT)

    # 1. Create and submit GRN
    create_resp = client.post("/api/v1/grn", json=_grn_payload(audit_test_env), headers=creator_headers)
    assert create_resp.status_code == 201, create_resp.text
    grn_id = create_resp.json()["id"]

    submit_resp = client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=creator_headers)
    assert submit_resp.status_code == 200, submit_resp.text

    # 2. Approve GRN
    approve_resp = client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=approver_headers)
    assert approve_resp.status_code == 200, approve_resp.text

    # Record baseline state directly from database
    db_session.expire_all()
    grn_before = db_session.query(GRNHeader).filter_by(id=grn_id).first()
    created_at_before = grn_before.created_at
    updated_at_before = grn_before.updated_at
    audit_count_before = db_session.query(GRNAuditLog).filter_by(grn_id=grn_id).count()
    audit_logs_before = [
        (log.id, log.action, log.actor_id, log.timestamp)
        for log in db_session.query(GRNAuditLog).filter_by(grn_id=grn_id).order_by(GRNAuditLog.id).all()
    ]

    assert created_at_before is not None
    assert updated_at_before is not None
    assert audit_count_before >= 3  # CREATED, SUBMITTED, APPROVED

    # 3. Perform repeated GET reads (by various authenticated roles)
    for role in [UserRole.STORES, UserRole.MANAGEMENT, UserRole.PURCHASE]:
        get_resp = client.get(f"/api/v1/grn/{grn_id}", headers=bearer(role))
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == grn_id

    # 4. Verify baseline state in database is strictly unchanged
    db_session.expire_all()
    grn_after = db_session.query(GRNHeader).filter_by(id=grn_id).first()
    assert grn_after.created_at == created_at_before
    assert grn_after.updated_at == updated_at_before

    audit_count_after = db_session.query(GRNAuditLog).filter_by(grn_id=grn_id).count()
    assert audit_count_after == audit_count_before

    audit_logs_after = [
        (log.id, log.action, log.actor_id, log.timestamp)
        for log in db_session.query(GRNAuditLog).filter_by(grn_id=grn_id).order_by(GRNAuditLog.id).all()
    ]
    assert audit_logs_after == audit_logs_before


def test_client_cannot_forge_creator_or_approver_identity(client: TestClient, db_session: Session, audit_test_env):
    """
    Observation 27: Verify that client-supplied creator/approver fields in the request
    body or query are ignored and the authenticated token identity is authoritatively stamped.
    """
    creator_headers = bearer(UserRole.STORES)
    payload = _grn_payload(audit_test_env)
    # Attempt to forge creator as an executive
    payload["created_by"] = "usr_managing_director"
    payload["creator_id"] = "forged_executive_id"

    create_resp = client.post("/api/v1/grn", json=payload, headers=creator_headers)
    assert create_resp.status_code == 201
    grn_id = create_resp.json()["id"]

    db_session.expire_all()
    grn = db_session.query(GRNHeader).filter_by(id=grn_id).first()
    # Must be stores_clerk (usr_stores_01), NOT the forged executive
    assert grn.created_by == "usr_stores_01"
    assert grn.created_by != "usr_managing_director"

    # Verify creation audit log has authoritative actor
    creation_log = (
        db_session.query(GRNAuditLog)
        .filter_by(grn_id=grn_id, action="CREATED")
        .first()
    )
    assert creation_log is not None
    assert creation_log.actor_id == "usr_stores_01"

    # Submit
    sub_resp = client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=creator_headers)
    assert sub_resp.status_code == 200

    # Attempt to forge approver identity
    approver_headers = bearer(UserRole.MANAGEMENT)
    approve_resp = client.post(
        f"/api/v1/grn/{grn_id}/approve",
        json={"approved_by": "usr_chairman", "approver_id": "forged_approver", "comments": "Approved"},
        headers=approver_headers,
    )
    assert approve_resp.status_code == 200

    db_session.expire_all()
    approval_log = (
        db_session.query(GRNAuditLog)
        .filter_by(grn_id=grn_id, action="APPROVED")
        .first()
    )
    assert approval_log is not None
    assert approval_log.actor_id == "usr_mgmt_01"
    assert approval_log.actor_id != "usr_chairman"


def test_audit_timestamps_are_server_side_utc(client: TestClient, db_session: Session, audit_test_env):
    """
    Observation 27: Audit timestamps must be assigned by the server in UTC,
    falling within the test execution time window.
    """
    before_creation = datetime.now(timezone.utc) - timedelta(seconds=2)
    resp = client.post(
        "/api/v1/grn",
        json=_grn_payload(audit_test_env),
        headers=bearer(UserRole.STORES),
    )
    after_creation = datetime.now(timezone.utc) + timedelta(seconds=2)
    assert resp.status_code == 201
    grn_id = resp.json()["id"]

    db_session.expire_all()
    creation_log = (
        db_session.query(GRNAuditLog)
        .filter_by(grn_id=grn_id, action="CREATED")
        .first()
    )
    assert creation_log is not None
    ts = creation_log.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    assert before_creation <= ts <= after_creation


def test_audit_history_preserved_after_document_reversal(client: TestClient, db_session: Session, audit_test_env):
    """
    Observation 27: Reversal workflows must preserve existing audit logs and append
    compensating audit entries with justification.
    """
    # 1. Create, Submit, and Approve GRN
    create_resp = client.post(
        "/api/v1/grn",
        json=_grn_payload(audit_test_env),
        headers=bearer(UserRole.STORES),
    )
    assert create_resp.status_code == 201
    grn_id = create_resp.json()["id"]

    sub_resp = client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=bearer(UserRole.STORES))
    assert sub_resp.status_code == 200

    app_resp = client.post(f"/api/v1/grn/{grn_id}/approve", json={}, headers=bearer(UserRole.MANAGEMENT))
    assert app_resp.status_code == 200

    # Capture audit log state prior to reversal
    db_session.expire_all()
    prior_logs = (
        db_session.query(GRNAuditLog)
        .filter_by(grn_id=grn_id)
        .order_by(GRNAuditLog.id)
        .all()
    )
    prior_ids = [log.id for log in prior_logs]
    prior_actions = [log.action for log in prior_logs]
    assert "CREATED" in prior_actions
    assert "APPROVED" in prior_actions

    # 2. Reverse GRN (requires MANAGEMENT role with LEDGER_REVERSE)
    rev_resp = client.post(
        f"/api/v1/grn/{grn_id}/reverse",
        json={"reason": "Audited delivery cancellation by vendor"},
        headers=bearer(UserRole.MANAGEMENT),
    )
    assert rev_resp.status_code == 200, rev_resp.text

    # 3. Verify audit trail integrity post-reversal
    db_session.expire_all()
    all_logs = (
        db_session.query(GRNAuditLog)
        .filter_by(grn_id=grn_id)
        .order_by(GRNAuditLog.id)
        .all()
    )

    # Every prior log must still exist with unchanged properties
    for prior_log in prior_logs:
        matching = [l for l in all_logs if l.id == prior_log.id]
        assert len(matching) == 1
        assert matching[0].action == prior_log.action
        assert matching[0].actor_id == prior_log.actor_id
        assert matching[0].timestamp == prior_log.timestamp

    # An additional REVERSED audit entry must have been appended
    reversed_logs = [l for l in all_logs if l.action == "REVERSED"]
    assert len(reversed_logs) == 1
    assert reversed_logs[0].actor_id == "usr_mgmt_01"
    assert "Audited delivery cancellation by vendor" in (reversed_logs[0].comments or "")


def test_no_update_or_delete_routes_for_audit_logs(client: TestClient):
    """
    Observation 27: Verify that the application surface exposes zero PUT, PATCH,
    or DELETE endpoints for audit records.
    """
    app = client.app
    audit_mutation_routes = []

    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if "audit" in path.lower():
            for m in methods:
                if m in ("PUT", "PATCH", "DELETE"):
                    audit_mutation_routes.append(f"{m} {path}")

    assert audit_mutation_routes == [], (
        f"Found forbidden mutating audit routes: {audit_mutation_routes}"
    )


def test_unauthenticated_requests_cannot_read_or_mutate_audit_logs(client: TestClient):
    """
    Observation 27: Protected document endpoints containing audit trails must reject
    unauthenticated requests with 401.
    """
    # Unauthenticated GET on GRN document with audit logs
    resp_grn = client.get("/api/v1/grn/1")
    assert resp_grn.status_code == 401

    # Unauthenticated GET on Issue document with audit logs
    resp_issue = client.get("/api/v1/issues/1")
    assert resp_issue.status_code == 401

    # Unauthenticated GET on Waste document with audit logs
    resp_waste = client.get("/api/v1/waste/1")
    assert resp_waste.status_code == 401

    # Unauthenticated GET on Item master history
    resp_item_history = client.get("/api/v1/items/1/history")
    assert resp_item_history.status_code == 401
