"""
Phase 1A: Authentication and RBAC Remediation Test Suite.

Verifies remediation of external review Observation 26:
1. Strict fail-closed authentication (401 on missing/invalid/forged tokens).
2. Elimination of unrestricted Admin operational superpowers:
   - Admin is restricted to system administration and audit/master-data inspection.
   - Admin is blocked (403) from creating or approving operational transactions
     (GRN, Issues, Waste, Stock Adjustments, Opening Balances, Costing runs).
3. Segregation of duties / Maker-Checker enforcement:
   - Document creator cannot approve their own document even if they possess approval permissions.
   - A different authorized approver is required.
4. Startup configuration enforcement:
   - Production mode strictly rejects development auth provider and default secret key.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import auth as auth_module
from app.core.auth import DEV_USERS, issue_dev_token, validate_security_configuration, NoAuthProvider, DevTokenProvider
from app.core.config import settings, DEFAULT_SECRET_KEY
from app.core.security import AuthenticatedUser, Permission, ROLE_PERMISSIONS, UserRole
from app.models.department import Department
from app.models.grn import GRNHeader
from app.models.issue import MaterialIssueHeader
from app.models.item import MaterialItem
from app.models.uom import UOM
from tests.auth_helpers import bearer


@pytest.fixture
def test_env(db_session: Session):
    fdy = db_session.query(Department).filter_by(code="FDY").first()
    msp = db_session.query(Department).filter_by(code="MSP").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(
        item_code="FDY-RM-SEC-01",
        name="Security Audit Ingot",
        department_id=fdy.id,
        category="RAW_MATERIALS",
        base_uom_id=kg.id,
    )
    db_session.add(item)
    db_session.commit()
    return {"fdy": fdy, "msp": msp, "kg": kg, "item": item}


def _grn_body(test_env):
    return {
        "receipt_date": str(date.today()),
        "source_type": "INTERNAL_VSPL",
        "lines": [{
            "line_number": 1,
            "material_item_id": test_env["item"].id,
            "uom_id": test_env["kg"].id,
            "quantity": "50.00",
            "remarks": "security test line",
        }],
    }


def _issue_body(test_env):
    return {
        "issue_date": str(date.today()),
        "issuing_department_id": test_env["fdy"].id,
        "receiving_department_id": test_env["msp"].id,
        "lines": [{
            "line_number": 1,
            "material_item_id": test_env["item"].id,
            "uom_id": test_env["kg"].id,
            "quantity": "10.00",
        }],
    }


# ==============================================================================================
# 1. Authentication & Fail-Closed Enforcement (401)
# ==============================================================================================

def test_unauthenticated_request_rejected_401(anon_client: TestClient):
    """Protected operational endpoints must reject callers without bearer credentials."""
    for path in ["/api/v1/grn/", "/api/v1/issues/", "/api/v1/waste/", "/api/v1/costing/runs"]:
        resp = anon_client.get(path)
        assert resp.status_code == 401, f"{path} did not reject unauthenticated caller: {resp.status_code}"
        assert resp.headers.get("www-authenticate") == "Bearer"


def test_forged_x_user_headers_fail_401(anon_client: TestClient):
    """Client cannot spoof identity via X-User-* headers."""
    headers = {
        "X-User-Id": "usr_admin_01",
        "X-User-Role": "Admin",
        "X-User-Department": "Admin",
    }
    resp = anon_client.get("/api/v1/items", headers=headers)
    assert resp.status_code == 401, "Server honored unverified X-User-* header"


def test_fail_closed_when_auth_provider_is_none(anon_client: TestClient, admin_headers, monkeypatch):
    """When AUTH_PROVIDER is 'none', all authenticated requests fail-closed with 401."""
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "none")
    assert isinstance(auth_module.get_auth_provider(), NoAuthProvider)
    resp = anon_client.get("/api/v1/items", headers=admin_headers)
    assert resp.status_code == 401


# ==============================================================================================
# 2. Admin Operational Restrictions (403)
# ==============================================================================================

def test_admin_cannot_create_operational_transactions_403(anon_client: TestClient, test_env, admin_headers):
    """Admin must NOT possess permissions to create domain operational transactions."""
    # GRN Create
    resp_grn = anon_client.post("/api/v1/grn/", json=_grn_body(test_env), headers=admin_headers)
    assert resp_grn.status_code == 403
    assert "lacks permission 'receipt:create'" in resp_grn.json()["detail"]

    # Issue Create
    resp_issue = anon_client.post("/api/v1/issues/", json=_issue_body(test_env), headers=admin_headers)
    assert resp_issue.status_code == 403
    assert "lacks permission 'issue:create'" in resp_issue.json()["detail"]

    # Opening Balance Post
    ob_rows = [{"item_code": test_env["item"].item_code, "quantity": "100.00", "uom_code": "KG", "baseline_date": "2026-10-12"}]
    resp_ob = anon_client.post(
        "/api/v1/opening-balances/post",
        json={"baseline_date": "2026-10-12", "audit_reference": "SEC-TEST", "rows": ob_rows},
        headers=admin_headers,
    )
    assert resp_ob.status_code == 403
    assert "lacks permission 'opening_balance:post'" in resp_ob.json()["detail"]

    # Costing Run
    resp_cost = anon_client.post("/api/v1/costing/runs", json={"period_start": "2026-10-12", "period_end": "2026-10-18"}, headers=admin_headers)
    assert resp_cost.status_code == 403
    assert "lacks permission 'costing:calculate'" in resp_cost.json()["detail"]


def test_admin_cannot_approve_operational_transactions_403(anon_client: TestClient, db_session: Session, test_env, stores_headers, admin_headers):
    """Admin must NOT possess permissions to approve operational documents."""
    # Stores creates and submits a GRN
    res = anon_client.post("/api/v1/grn/", json=_grn_body(test_env), headers=stores_headers)
    assert res.status_code == 201
    grn_id = res.json()["id"]
    anon_client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)

    # Admin attempts to approve -> 403 Forbidden (missing receipt:approve)
    resp_app = anon_client.post(f"/api/v1/grn/{grn_id}/approve", json={"comments": "Admin approval attempt"}, headers=admin_headers)
    assert resp_app.status_code == 403
    assert "lacks permission 'receipt:approve'" in resp_app.json()["detail"]


def test_admin_retains_system_administration_and_read_inspection(anon_client: TestClient, admin_headers):
    """Admin retains read-only audit and master data visibility and system management."""
    # System inspection & Master Data Read
    assert anon_client.get("/api/v1/departments", headers=admin_headers).status_code == 200
    assert anon_client.get("/api/v1/uoms", headers=admin_headers).status_code == 200
    assert anon_client.get("/api/v1/items", headers=admin_headers).status_code == 200
    assert anon_client.get("/api/v1/ledger/entries", headers=admin_headers).status_code == 200
    assert anon_client.get("/api/v1/health/db-check", headers=admin_headers).status_code not in {401, 403}


# ==============================================================================================
# 3. Maker-Checker Segregation Enforcement (403)
# ==============================================================================================

def test_maker_checker_creator_cannot_approve_own_document_403(
    anon_client: TestClient, db_session: Session, test_env, stores_headers, management_headers
):
    """
    Even when an actor holds approval permission (e.g. Management), if that actor created
    the document, approval MUST be refused under Maker-Checker governance.
    """
    # Stores creates and submits a GRN
    res = anon_client.post("/api/v1/grn/", json=_grn_body(test_env), headers=stores_headers)
    assert res.status_code == 201
    grn_id = res.json()["id"]
    anon_client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)

    # Simulate that the document was authored by usr_mgmt_01
    grn = db_session.get(GRNHeader, grn_id)
    grn.created_by = "usr_mgmt_01"
    db_session.commit()

    # usr_mgmt_01 attempts to approve their own document -> 403 Maker-checker violation
    resp = anon_client.post(f"/api/v1/grn/{grn_id}/approve", json={"comments": "Self approval"}, headers=management_headers)
    assert resp.status_code == 403
    assert "Maker-checker violation" in resp.json()["detail"]


def test_maker_checker_different_checker_succeeds(
    anon_client: TestClient, db_session: Session, test_env, stores_headers
):
    """When checker is distinct from creator, approval is accepted."""
    # Stores creates
    res = anon_client.post("/api/v1/grn/", json=_grn_body(test_env), headers=stores_headers)
    assert res.status_code == 201
    grn_id = res.json()["id"]
    anon_client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers)

    # Checker is a distinct management user
    checker = AuthenticatedUser(user_id="usr_mgmt_02", role=UserRole.MANAGEMENT, department="Management")
    checker_token = issue_dev_token(checker)
    checker_headers = {"Authorization": f"Bearer {checker_token}"}

    resp = anon_client.post(f"/api/v1/grn/{grn_id}/approve", json={"comments": "Independent checker approval"}, headers=checker_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


# ==============================================================================================
# 4. Production Startup Validation
# ==============================================================================================

def test_production_environment_refuses_dev_auth_provider(monkeypatch):
    """Application refuses to start if ENVIRONMENT=production and AUTH_PROVIDER=dev."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "dev")
    monkeypatch.setattr(settings, "SECRET_KEY", "real-strong-secret-key-12345678901234567890")
    with pytest.raises(RuntimeError, match="AUTH_PROVIDER=dev is not allowed in production"):
        validate_security_configuration()


def test_production_environment_refuses_default_secret_key(monkeypatch):
    """Application refuses to start if ENVIRONMENT=production and SECRET_KEY is default."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "none")
    monkeypatch.setattr(settings, "SECRET_KEY", DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="SECRET_KEY is the insecure default in production"):
        validate_security_configuration()
