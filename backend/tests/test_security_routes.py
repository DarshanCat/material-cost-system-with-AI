"""
TST-01 — Route-by-role security regression tests (Security Hardening Sprint 1).

Covers: unauthenticated requests (401), forged X-User-* headers, invalid/expired/tampered tokens and
unknown roles (401, never defaulting to Stores), the full route x role permission matrix, rejected
mutations leaving the database unchanged, actor attribution from the verified identity, and the
fail-closed provider configuration.

All tests run against isolated in-memory SQLite (see conftest.py). Passing them demonstrates the
authorization wiring only; it is not evidence of production readiness (no production auth exists).
"""

import base64
import json
import time
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core import auth as auth_module
from app.core.auth import DEV_USERS, issue_dev_token, validate_security_configuration
from app.core.config import settings, DEFAULT_SECRET_KEY
from app.core.security import AuthenticatedUser, Permission, ROLE_PERMISSIONS, UserRole
from app.db.base import Base
from app.main import app as fastapi_app
from app.models.department import Department
from app.models.grn import GRNHeader
from app.models.heat import HeatHeader
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.uom import UOM
from tests.auth_helpers import bearer

P = Permission

# Operations that are intentionally reachable without authentication.
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/auth/status"),
    ("POST", "/api/v1/auth/dev-login"),  # development provider only; loopback-restricted, 404 otherwise
    ("POST", "/api/v1/auth/login"),      # public sign-in endpoint; fails closed (501) until provider configured
}

# Any authenticated user (no specific permission).
ANY_AUTHENTICATED = None

# Every protected operation -> the permission it must require. A new route that is missing here
# fails test_every_route_is_classified, forcing an explicit security decision.
ROUTE_PERMISSIONS: dict[tuple[str, str], Permission | None] = {
    ("GET", "/api/v1/auth/me"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/auth/logout"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/auth/password-changed"): ANY_AUTHENTICATED,
    # User administration (identity sign-in mode only; Admin holds user:manage)
    ("GET", "/api/v1/users"): P.USER_MANAGE,
    ("POST", "/api/v1/users"): P.USER_MANAGE,
    ("GET", "/api/v1/users/audit-log"): P.USER_MANAGE,
    ("PATCH", "/api/v1/users/{user_id}"): P.USER_MANAGE,
    ("POST", "/api/v1/users/{user_id}/approve"): P.USER_MANAGE,
    ("POST", "/api/v1/users/{user_id}/reject"): P.USER_MANAGE,
    ("POST", "/api/v1/users/{user_id}/disable"): P.USER_MANAGE,
    ("POST", "/api/v1/users/{user_id}/enable"): P.USER_MANAGE,
    ("POST", "/api/v1/users/{user_id}/reset-password"): P.USER_MANAGE,
    ("GET", "/api/v1/health/db-check"): P.AUDIT_READ,
    # Master data
    ("GET", "/api/v1/departments"): P.DEPARTMENT_READ,
    ("POST", "/api/v1/departments"): P.DEPARTMENT_MANAGE,
    ("GET", "/api/v1/departments/{department_id}"): P.DEPARTMENT_READ,
    ("GET", "/api/v1/uoms"): P.UOM_READ,
    ("POST", "/api/v1/uoms"): P.UOM_MANAGE,
    ("GET", "/api/v1/uoms/{uom_id}"): P.UOM_READ,
    ("GET", "/api/v1/items"): P.ITEM_READ,
    ("GET", "/api/v1/items/categories"): P.ITEM_READ,
    ("GET", "/api/v1/items/{item_id}"): P.ITEM_READ,
    ("PUT", "/api/v1/items/{item_id}"): P.ITEM_UPDATE,
    ("GET", "/api/v1/items/{item_id}/history"): P.ITEM_READ,
    # Item code generator (Nomenclature Standard v1.0)
    ("GET", "/api/v1/item-codes/rules"): P.ITEM_REQUEST_READ,
    ("POST", "/api/v1/item-codes/preview"): P.ITEM_REQUEST_READ,
    ("GET", "/api/v1/item-codes/compliance"): P.ITEM_READ,
    ("GET", "/api/v1/vendors"): P.VENDOR_READ,
    ("POST", "/api/v1/vendors"): P.VENDOR_MANAGE,
    ("GET", "/api/v1/vendors/{vendor_id}"): P.VENDOR_READ,
    ("PUT", "/api/v1/vendors/{vendor_id}"): P.VENDOR_MANAGE,
    # Item requests
    ("POST", "/api/v1/item-requests"): P.ITEM_REQUEST_CREATE,
    ("GET", "/api/v1/item-requests"): P.ITEM_REQUEST_READ,
    ("GET", "/api/v1/item-requests/pending"): P.ITEM_APPROVE,
    ("GET", "/api/v1/item-requests/{request_id}"): P.ITEM_REQUEST_READ,
    ("PUT", "/api/v1/item-requests/{request_id}"): P.ITEM_REQUEST_CREATE,
    ("POST", "/api/v1/item-requests/{request_id}/submit"): P.ITEM_REQUEST_SUBMIT,
    ("POST", "/api/v1/item-requests/{request_id}/cancel"): P.ITEM_REQUEST_CANCEL,
    ("POST", "/api/v1/item-requests/{request_id}/approve"): P.ITEM_APPROVE,
    ("POST", "/api/v1/item-requests/{request_id}/reject"): P.ITEM_REJECT,
    # GRN
    ("POST", "/api/v1/grn/"): P.RECEIPT_CREATE,
    ("GET", "/api/v1/grn/"): P.RECEIPT_READ,
    ("GET", "/api/v1/grn/{grn_id}"): P.RECEIPT_READ,
    ("POST", "/api/v1/grn/{grn_id}/submit"): P.RECEIPT_CREATE,
    ("POST", "/api/v1/grn/{grn_id}/approve"): P.RECEIPT_APPROVE,
    ("POST", "/api/v1/grn/{grn_id}/reject"): P.RECEIPT_APPROVE,
    ("POST", "/api/v1/grn/{grn_id}/quality"): P.RECEIPT_QUALITY,
    ("POST", "/api/v1/grn/{grn_id}/payment"): P.PAYMENT_RECORD,
    ("POST", "/api/v1/grn/{grn_id}/cancel"): P.RECEIPT_CREATE,
    ("POST", "/api/v1/grn/{grn_id}/reverse"): P.LEDGER_REVERSE,
    ("GET", "/api/v1/grn/{grn_id}/attachments"): P.RECEIPT_READ,
    ("POST", "/api/v1/grn/{grn_id}/attachments"): P.RECEIPT_CREATE,
    ("GET", "/api/v1/grn/{grn_id}/attachments/{attachment_id}/download"): P.RECEIPT_READ,
    ("DELETE", "/api/v1/grn/{grn_id}/attachments/{attachment_id}"): P.RECEIPT_CREATE,
    # Purchase Orders (P2P Procurement)
    ("GET", "/api/v1/purchase-requests/"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/purchase-requests/{pr_id}"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-requests/"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-requests/{pr_id}/approve"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-requests/{pr_id}/reject"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/purchase-orders/"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/purchase-orders/{po_id}"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/submit"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/approve-dept"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/approve-scm"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/approve-mgmt"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/order-placed"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/reject"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/purchase-orders/{po_id}/cancel"): ANY_AUTHENTICATED,
    # Issues
    ("POST", "/api/v1/issues/"): P.ISSUE_CREATE,
    ("GET", "/api/v1/issues/"): P.ISSUE_READ,
    ("GET", "/api/v1/issues/{issue_id}"): P.ISSUE_READ,
    ("POST", "/api/v1/issues/{issue_id}/submit"): P.ISSUE_CREATE,
    ("POST", "/api/v1/issues/{issue_id}/approve"): P.ISSUE_APPROVE,
    ("POST", "/api/v1/issues/{issue_id}/cancel"): P.ISSUE_CREATE,
    ("POST", "/api/v1/issues/{issue_id}/direct-issue"): P.ISSUE_CREATE,
    ("POST", "/api/v1/issues/{issue_id}/reverse"): P.LEDGER_REVERSE,
    # Return to Store (RTS)
    ("POST", "/api/v1/material-returns/"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/material-returns/"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/material-returns/{id}"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/material-returns/{id}/accept"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/material-returns/{id}/reject"): ANY_AUTHENTICATED,
    # Waste
    ("POST", "/api/v1/waste/"): P.WASTE_LOG,
    ("GET", "/api/v1/waste/"): P.WASTE_READ,
    ("GET", "/api/v1/waste/{waste_id}"): P.WASTE_READ,
    ("POST", "/api/v1/waste/{waste_id}/submit"): P.WASTE_LOG,
    ("POST", "/api/v1/waste/{waste_id}/approve"): P.WASTE_APPROVE,
    ("POST", "/api/v1/waste/{waste_id}/reverse"): P.LEDGER_REVERSE,
    # Excel import
    ("GET", "/api/v1/excel-import/template/{import_type}"): P.EXCEL_IMPORT,
    ("POST", "/api/v1/excel-import/validate"): P.EXCEL_IMPORT,
    ("POST", "/api/v1/excel-import/commit"): P.EXCEL_IMPORT,
    # Ledger
    ("GET", "/api/v1/ledger/balances"): P.LEDGER_READ,
    ("GET", "/api/v1/ledger/balances/{item_id}"): P.LEDGER_READ,
    ("GET", "/api/v1/ledger/entries"): P.LEDGER_READ,
    ("GET", "/api/v1/ledger/entries/{entry_id}"): P.LEDGER_READ,
    ("GET", "/api/v1/ledger/summary-by-uom"): P.LEDGER_READ,
    ("POST", "/api/v1/ledger/entries/{entry_id}/reverse"): P.LEDGER_REVERSE,
    # Opening balances
    ("GET", "/api/v1/opening-balances/template"): P.OPENING_BALANCE_POST,
    ("POST", "/api/v1/opening-balances/preview"): P.OPENING_BALANCE_POST,
    ("POST", "/api/v1/opening-balances/post"): P.OPENING_BALANCE_POST,
    # Physical audits
    ("POST", "/api/v1/physical-audits/"): P.STOCK_ADJUST,
    ("GET", "/api/v1/physical-audits/"): P.LEDGER_READ,
    ("GET", "/api/v1/physical-audits/{audit_id}"): P.LEDGER_READ,
    ("POST", "/api/v1/physical-audits/{audit_id}/submit"): P.STOCK_ADJUST,
    ("POST", "/api/v1/physical-audits/{audit_id}/approve"): P.STOCK_AUDIT_APPROVE,
    # Heats
    ("POST", "/api/v1/heats"): P.HEAT_LOG_CREATE,
    ("GET", "/api/v1/heats"): P.HEAT_LOG_READ,
    ("GET", "/api/v1/heats/active"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/heats/propose-carry-forward"): P.HEAT_LOG_READ,
    ("POST", "/api/v1/heats/{id}/verify-heel"): P.HEAT_LOG_CREATE,
    ("POST", "/api/v1/heats/{id}/close"): ANY_AUTHENTICATED,
    ("POST", "/api/v1/heats/{id}/reopen"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/heats/{id}/consumption-cost"): ANY_AUTHENTICATED,
    ("GET", "/api/v1/heats/{id}"): P.HEAT_LOG_READ,
    ("GET", "/api/v1/heats/number/{heat_number}"): P.HEAT_LOG_READ,
    ("POST", "/api/v1/heats/import/preview"): P.HEAT_LOG_CREATE,
    ("POST", "/api/v1/heats/import/upload"): P.HEAT_LOG_CREATE,
    ("POST", "/api/v1/heats/import/commit"): P.HEAT_LOG_CREATE,
    ("GET", "/api/v1/heats/import/template"): P.HEAT_LOG_READ,
    # Material aliases
    ("POST", "/api/v1/material-aliases"): P.ALIAS_CREATE,
    ("GET", "/api/v1/material-aliases"): P.ITEM_READ,
    ("POST", "/api/v1/material-aliases/{id}/approve"): P.ALIAS_APPROVE,
    ("POST", "/api/v1/material-aliases/{id}/reject"): P.ALIAS_APPROVE,
    ("POST", "/api/v1/material-aliases/{id}/deactivate"): P.ALIAS_DEACTIVATE,
    # Reconciliation
    ("POST", "/api/v1/reconciliation/run"): P.HEAT_RECONCILE,
    ("GET", "/api/v1/reconciliation/runs"): P.HEAT_LOG_READ,
    ("GET", "/api/v1/reconciliation/runs/{id}"): P.HEAT_LOG_READ,
    ("POST", "/api/v1/reconciliation/candidates/{id}/confirm"): P.HEAT_RECONCILE,
    ("POST", "/api/v1/reconciliation/candidates/{id}/reject"): P.HEAT_RECONCILE,
    ("POST", "/api/v1/reconciliation/exceptions/{id}/resolve"): P.HEAT_EXCEPTION_RESOLVE,
    # Costing
    ("GET", "/api/v1/costing/valuation/items/{material_item_id}"): P.COSTING_READ,
    ("GET", "/api/v1/costing/valuation/current"): P.COSTING_READ,
    ("GET", "/api/v1/costing/valuation/historical"): P.COSTING_READ,
    ("GET", "/api/v1/costing/rates/history/{material_item_id}"): P.COSTING_READ,
    ("GET", "/api/v1/costing/exceptions"): P.COSTING_READ,
    ("GET", "/api/v1/costing/heats"): P.COSTING_READ,
    ("GET", "/api/v1/costing/heats/{heat_id}"): P.COSTING_READ,
    ("GET", "/api/v1/costing/parts"): P.COSTING_READ,
    ("POST", "/api/v1/costing/runs"): P.COSTING_CALCULATE,
    ("GET", "/api/v1/costing/runs"): P.COSTING_READ,
    ("GET", "/api/v1/costing/runs/compare"): P.COSTING_READ,
    ("GET", "/api/v1/costing/runs/{run_id}"): P.COSTING_READ,
    ("POST", "/api/v1/costing/opening-valuations"): P.COSTING_CALCULATE,
    ("POST", "/api/v1/costing/opening-valuations/{valuation_id}/approve"): P.COSTING_CALCULATE,
    ("POST", "/api/v1/costing/opening-valuations/{valuation_id}/reject"): P.COSTING_CALCULATE,
    ("GET", "/api/v1/costing/opening-valuations"): P.COSTING_READ,
    ("GET", "/api/v1/costing/opening-valuations/{valuation_id}"): P.COSTING_READ,
}

STATUS_CODES_DENIED = {401, 403}


def _all_operations() -> set[tuple[str, str]]:
    ops = set()
    for path, methods in fastapi_app.openapi()["paths"].items():
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                ops.add((method.upper(), path))
    return ops


def _concrete(path: str) -> str:
    out = path
    while "{" in out:
        start, end = out.index("{"), out.index("}")
        name = out[start + 1:end]
        out = out[:start] + ("PIG" if name == "import_type" else "1") + out[end + 1:]
    return out


def _send(client: TestClient, method: str, path: str, headers: dict | None = None):
    return client.request(method, _concrete(path), headers=headers or {})


def _row_counts(db: Session) -> dict[str, int]:
    return {t.name: db.execute(select(func.count()).select_from(t)).scalar_one() for t in Base.metadata.sorted_tables}


# --------------------------------------------------------------------------------------------
# Coverage / classification
# --------------------------------------------------------------------------------------------

def test_every_route_is_classified():
    """No route may exist without an explicit public/permission classification in this file."""
    ops = _all_operations()
    classified = set(ROUTE_PERMISSIONS) | PUBLIC_ROUTES
    assert ops - classified == set(), f"Unclassified routes (add to ROUTE_PERMISSIONS): {sorted(ops - classified)}"
    assert classified - ops == set(), f"Stale entries for routes that no longer exist: {sorted(classified - ops)}"


# --------------------------------------------------------------------------------------------
# Authentication (401)
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", sorted(ROUTE_PERMISSIONS))
def test_unauthenticated_request_gets_401(anon_client: TestClient, method, path):
    resp = _send(anon_client, method, path)
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
    assert resp.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("method,path", sorted(ROUTE_PERMISSIONS))
def test_forged_identity_headers_never_authenticate(anon_client: TestClient, method, path):
    forged = {"X-User-Id": "usr_admin_01", "X-User-Role": "Admin", "X-User-Department": "Admin"}
    resp = _send(anon_client, method, path, headers=forged)
    assert resp.status_code == 401, f"{method} {path} accepted forged X-User-* headers"


def test_forged_headers_cannot_elevate_a_valid_low_privilege_token(anon_client: TestClient, stores_headers):
    headers = {**stores_headers, "X-User-Role": "Admin", "X-User-Id": "usr_admin_01"}
    me = anon_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "Stores" and me.json()["user_id"] == "usr_stores_01"
    assert anon_client.post("/api/v1/ledger/entries/1/reverse", headers=headers, json={"reason": "forged elevation"}).status_code == 403


def _token_with(payload_overrides: dict | None = None, tamper_signature: bool = False, role_value: str | None = None) -> str:
    user = DEV_USERS[UserRole.ADMIN]
    token = issue_dev_token(user)
    prefix, payload_b64, sig = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    if role_value is not None:
        payload["role"] = role_value
    payload.update(payload_overrides or {})
    new_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    if payload_overrides is None and role_value is None and not tamper_signature:
        return token
    # Re-sign with the real server key to prove that *unknown role / expiry* are rejected on their own,
    # unless tampering is requested (then keep the stale signature).
    signature = sig if tamper_signature else auth_module._sign(new_b64)
    return f"{prefix}.{new_b64}.{signature}"


@pytest.mark.parametrize(
    "label,token",
    [
        ("garbage", "not-a-token"),
        ("empty-parts", "a.b"),
        ("tampered-payload", _token_with(role_value="Admin", tamper_signature=True)),
        ("expired", _token_with({"exp": int(time.time()) - 5})),
        ("unknown-role-correctly-signed", _token_with(role_value="Superuser")),
        ("empty-role-correctly-signed", _token_with(role_value="")),
        ("missing-subject", _token_with({"sub": " "})),
    ],
)
def test_invalid_tokens_get_401_and_never_default_to_stores(anon_client: TestClient, label, token):
    resp = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, label
    # In particular a Stores-permitted route must not be reachable via a bad token.
    resp2 = anon_client.get("/api/v1/grn/", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 401, label


def test_wrong_auth_scheme_is_rejected(anon_client: TestClient):
    token = issue_dev_token(DEV_USERS[UserRole.ADMIN])
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Basic {token}"}).status_code == 401
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": token}).status_code == 401


def test_token_signed_with_a_different_key_is_rejected(anon_client: TestClient, monkeypatch):
    foreign = issue_dev_token(DEV_USERS[UserRole.ADMIN])
    monkeypatch.setattr(settings, "SECRET_KEY", "a-different-server-secret")
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {foreign}"}).status_code == 401


# --------------------------------------------------------------------------------------------
# Authorization matrix (403) — every route x every role
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", list(UserRole), ids=lambda r: r.value)
@pytest.mark.parametrize("method,path", sorted(ROUTE_PERMISSIONS))
def test_route_by_role_matrix(anon_client: TestClient, role_headers, method, path, role):
    required = ROUTE_PERMISSIONS[(method, path)]
    allowed = required is None or required in ROLE_PERMISSIONS[role]
    resp = _send(anon_client, method, path, headers=role_headers(role))
    if allowed:
        assert resp.status_code not in STATUS_CODES_DENIED, f"{role.value} wrongly denied {method} {path}: {resp.status_code}"
    else:
        assert resp.status_code == 403, f"{role.value} wrongly allowed {method} {path}: {resp.status_code}"


def test_every_permission_in_matrix_is_enforced_by_some_route():
    """Guards against the old defect (permissions defined but referenced by no endpoint)."""
    used = {p for p in ROUTE_PERMISSIONS.values() if p is not None}
    unused = set(Permission) - used
    # Not yet backed by routes (no such features exist): tracked, not silently ignored.
    known_unrouted = {P.ITEM_CREATE, P.ITEM_UPDATE}
    assert unused <= known_unrouted, f"Permissions defined but enforced nowhere: {sorted(p.value for p in unused - known_unrouted)}"


def test_admin_holds_administrative_permissions_only_and_no_role_defaults():
    assert set(ROLE_PERMISSIONS) == set(UserRole)
    # Admin is restricted: must NOT hold operational transaction permissions
    forbidden_operational = {
        P.RECEIPT_CREATE, P.RECEIPT_APPROVE,
        P.ISSUE_CREATE, P.ISSUE_APPROVE,
        P.WASTE_LOG, P.WASTE_APPROVE,
        P.STOCK_ADJUST, P.STOCK_AUDIT_APPROVE,
        P.OPENING_BALANCE_POST,
        P.HEAT_LOG_CREATE, P.HEAT_RECONCILE, P.HEAT_EXCEPTION_RESOLVE,
        P.COSTING_CALCULATE,
        P.LEDGER_REVERSE,
    }
    assert forbidden_operational.isdisjoint(ROLE_PERMISSIONS[UserRole.ADMIN])
    assert P.USER_MANAGE in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert P.AUDIT_READ in ROLE_PERMISSIONS[UserRole.ADMIN]


# --------------------------------------------------------------------------------------------
# Rejected mutations leave the database unchanged
# --------------------------------------------------------------------------------------------

@pytest.fixture
def seeded(db_session: Session):
    dept = db_session.query(Department).filter_by(code="FDY").first()
    uom = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(item_code="FDY-RM-901", name="Security Test Pig Iron", department_id=dept.id,
                        category="RAW_MATERIALS", base_uom_id=uom.id)
    db_session.add(item)
    db_session.commit()
    return {"item": item, "uom": uom, "dept": dept}


def _grn_payload(seeded) -> dict:
    return {
        "receipt_date": str(date.today()),
        "source_type": "INTERNAL_VSPL",
        "lines": [{
            "line_number": 1,
            "material_item_id": seeded["item"].id,
            "uom_id": seeded["uom"].id,
            "quantity": "100.00",
            "remarks": "security test",
        }],
    }


def _approved_ledger_entry(db_session: Session, seeded) -> StockLedgerEntry:
    entry = StockLedgerEntry(
        entry_number="STK-SEC-0001", posting_group_id="POST-SEC", material_item_id=seeded["item"].id,
        uom_id=seeded["uom"].id, transaction_date=date.today(), movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("100.0000"), source_document_type=SourceDocumentType.GRN.value,
        source_document_id=1, source_line_id=1, source_document_number="GRN-SEC-1", posted_by="usr_seed",
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def test_denied_and_unauthenticated_mutations_do_not_change_the_database(
    anon_client: TestClient, db_session: Session, seeded, stores_headers, purchase_headers,
    foundry_headers, management_headers, admin_headers,
):
    # Legitimately create + submit a GRN as Stores so approval/cancel paths have a target.
    created = anon_client.post("/api/v1/grn/", json=_grn_payload(seeded), headers=stores_headers)
    assert created.status_code == 201, created.text
    grn_id = created.json()["id"]
    assert anon_client.post(f"/api/v1/grn/{grn_id}/submit", json={}, headers=stores_headers).status_code == 200
    entry = _approved_ledger_entry(db_session, seeded)

    ob_rows = [{"item_code": "FDY-RM-901", "quantity": "5.00", "uom_code": "KG", "baseline_date": "2026-10-12"}]
    attempts = [
        # (method, url, headers, json)
        ("POST", "/api/v1/grn/", purchase_headers, _grn_payload(seeded)),
        ("POST", "/api/v1/grn/", None, _grn_payload(seeded)),
        ("POST", f"/api/v1/grn/{grn_id}/approve", stores_headers, {}),          # creator role cannot approve
        ("POST", f"/api/v1/grn/{grn_id}/approve", foundry_headers, {}),
        ("POST", f"/api/v1/grn/{grn_id}/approve", None, {}),
        ("POST", f"/api/v1/ledger/entries/{entry.id}/reverse", stores_headers, {"reason": "unauthorised reversal"}),
        ("POST", f"/api/v1/ledger/entries/{entry.id}/reverse", None, {"reason": "unauthenticated reversal"}),
        ("POST", "/api/v1/opening-balances/post", admin_headers,
         {"baseline_date": "2026-10-12", "audit_reference": "SEC-TEST", "rows": ob_rows, "approver_id": "x"}),
        ("POST", "/api/v1/opening-balances/post", stores_headers,
         {"baseline_date": "2026-10-12", "audit_reference": "SEC-TEST", "rows": ob_rows}),
        ("POST", "/api/v1/excel-import/commit", foundry_headers, {"import_type": "GRN", "rows": []}),
        ("POST", "/api/v1/heats", stores_headers, {"heat_number": "H-SEC-1", "heat_date": str(date.today())}),
        ("POST", "/api/v1/costing/opening-valuations", stores_headers,
         {"material_item_id": seeded["item"].id, "opening_rate_ex_gst": "10.00"}),
        ("POST", "/api/v1/costing/runs", foundry_headers, {}),
        ("POST", "/api/v1/physical-audits/", foundry_headers, {"audit_date": str(date.today()), "lines": []}),
    ]
    before = _row_counts(db_session)
    grn_status_before = db_session.get(GRNHeader, grn_id).status
    for method, url, hdrs, body in attempts:
        resp = anon_client.request(method, url, headers=hdrs or {}, json=body)
        assert resp.status_code in STATUS_CODES_DENIED, f"{method} {url} -> {resp.status_code}: {resp.text[:200]}"
    db_session.expire_all()
    assert _row_counts(db_session) == before
    assert db_session.get(GRNHeader, grn_id).status == grn_status_before


# --------------------------------------------------------------------------------------------
# Actor attribution comes from the verified identity only
# --------------------------------------------------------------------------------------------

def test_grn_actor_attribution_ignores_client_supplied_actor(
    anon_client: TestClient, db_session: Session, seeded, stores_headers, management_headers,
):
    created = anon_client.post("/api/v1/grn/?created_by=Admin", json=_grn_payload(seeded), headers=stores_headers)
    assert created.status_code == 201, created.text
    grn_id = created.json()["id"]
    assert created.json()["created_by"] == "usr_stores_01"

    anon_client.post(f"/api/v1/grn/{grn_id}/submit?actor_id=Admin", json={}, headers=stores_headers)
    approved = anon_client.post(f"/api/v1/grn/{grn_id}/approve?actor_id=SomeoneElse", json={}, headers=management_headers)
    assert approved.status_code == 200, approved.text

    actors = {(a["action"], a["actor_id"]) for a in approved.json()["audit_logs"]}
    assert ("CREATED", "usr_stores_01") in actors
    assert ("SUBMITTED", "usr_stores_01") in actors
    assert ("APPROVED", "usr_mgmt_01") in actors
    assert not any(a in {"Admin", "SomeoneElse"} for _, a in actors)
    # The ledger posting carries the approver, not a client-supplied name.
    posted = db_session.execute(select(StockLedgerEntry.posted_by).where(StockLedgerEntry.source_document_type == SourceDocumentType.GRN.value)).scalars().all()
    assert posted and set(posted) == {"usr_mgmt_01"}


def test_ledger_reversal_actor_is_verified_identity(anon_client: TestClient, db_session: Session, seeded, management_headers):
    entry = _approved_ledger_entry(db_session, seeded)
    resp = anon_client.post(
        f"/api/v1/ledger/entries/{entry.id}/reverse?actor_id=Admin",
        json={"reason": "weighbridge slip mismatch"}, headers=management_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["posted_by"] == "usr_mgmt_01"


def test_opening_balance_body_approver_is_overwritten(anon_client: TestClient, db_session: Session, seeded, management_headers):
    rows = [{"item_code": "FDY-RM-901", "quantity": "250.00", "uom_code": "KG", "baseline_date": "2026-10-12"}]
    resp = anon_client.post(
        "/api/v1/opening-balances/post", headers=management_headers,
        json={"baseline_date": "2026-10-12", "audit_reference": "SEC-ATTRIB", "rows": rows, "approver_id": "ForgedApprover"},
    )
    assert resp.status_code == 200, resp.text
    posted_by = db_session.execute(select(StockLedgerEntry.posted_by).where(StockLedgerEntry.movement_type == MovementType.OPENING_BALANCE.value)).scalars().all()
    assert posted_by == ["usr_mgmt_01"]


def test_opening_balance_post_works_without_client_supplied_approver(anon_client: TestClient, seeded, management_headers):
    rows = [{"item_code": "FDY-RM-901", "quantity": "10.00", "uom_code": "KG", "baseline_date": "2026-10-12"}]
    resp = anon_client.post(
        "/api/v1/opening-balances/post", headers=management_headers,
        json={"baseline_date": "2026-10-12", "audit_reference": "SEC-NOAPPR", "rows": rows},
    )
    assert resp.status_code == 200, resp.text


def test_heat_creator_is_verified_identity(anon_client: TestClient, db_session: Session, foundry_headers):
    resp = anon_client.post("/api/v1/heats", headers=foundry_headers, json={"heat_number": "H-102699-0001", "heat_date": str(date.today())})
    assert resp.status_code == 201, resp.text
    assert db_session.query(HeatHeader).one().created_by == "usr_foundry_01"


# --------------------------------------------------------------------------------------------
# Provider configuration: fail closed
# --------------------------------------------------------------------------------------------

def test_no_provider_configured_denies_even_a_validly_signed_token(anon_client: TestClient, monkeypatch):
    token = issue_dev_token(DEV_USERS[UserRole.ADMIN])
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "none")
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert anon_client.get("/api/v1/auth/status").json() == {"provider": "none", "login_available": False}
    assert anon_client.post("/api/v1/auth/dev-login", json={"role": "Admin"}).status_code == 404


def test_unknown_provider_name_fails_closed(anon_client: TestClient, monkeypatch):
    token = issue_dev_token(DEV_USERS[UserRole.ADMIN])
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "entra-id-not-implemented")
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_dev_provider_is_refused_outside_development(anon_client: TestClient, monkeypatch):
    token = issue_dev_token(DEV_USERS[UserRole.ADMIN])
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    with pytest.raises(RuntimeError):
        issue_dev_token(DEV_USERS[UserRole.ADMIN])


def test_startup_refuses_unsafe_production_configuration(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "dev")
    with pytest.raises(RuntimeError):
        validate_security_configuration()
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "none")
    monkeypatch.setattr(settings, "SECRET_KEY", DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError):
        validate_security_configuration()
    monkeypatch.setattr(settings, "SECRET_KEY", "a-real-random-production-secret-value")
    validate_security_configuration()  # fail-closed 'none' provider with a real secret may start


# --------------------------------------------------------------------------------------------
# Dev sign-in endpoint
# --------------------------------------------------------------------------------------------

def test_dev_login_issues_server_account_token(anon_client: TestClient):
    resp = anon_client.post("/api/v1/auth/dev-login", json={"role": "Management"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"] == {"user_id": "usr_mgmt_01", "role": "Management", "department": "Management"}
    me = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["user_id"] == "usr_mgmt_01"


@pytest.mark.parametrize("role", ["Superuser", "", "admin", "stores "])
def test_dev_login_rejects_unknown_roles(anon_client: TestClient, role):
    assert anon_client.post("/api/v1/auth/dev-login", json={"role": role}).status_code == 400


def test_dev_login_rejects_non_loopback_clients(anon_client: TestClient):
    resp = anon_client.post("/api/v1/auth/dev-login", json={"role": "Admin"}, headers={})
    assert resp.status_code == 200  # TestClient host is allowed only under ENVIRONMENT=test
    with TestClient(fastapi_app, client=("203.0.113.9", 50000)) as remote:
        assert remote.post("/api/v1/auth/dev-login", json={"role": "Admin"}).status_code == 403


def test_public_routes_stay_public(anon_client: TestClient):
    assert anon_client.get("/api/v1/health").status_code == 200
    assert anon_client.get("/api/v1/auth/status").status_code == 200


# --------------------------------------------------------------------------------------------
# QA-03 / QA-04 / QA-07 Remediation Regression Tests
# --------------------------------------------------------------------------------------------

def test_logout_revokes_bearer_token_and_blocks_replay(anon_client: TestClient):
    """QA-03: Server-side logout revokes the bearer token so subsequent requests return 401."""
    auth_module.clear_revoked_tokens()
    login_resp = anon_client.post("/api/v1/auth/dev-login", json={"role": "Stores"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Token initially valid
    assert anon_client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # Logout revokes the token
    logout_resp = anon_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["revoked"] is True

    # Replaying the revoked token must return 401 across auth and operational routes
    assert anon_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert anon_client.get("/api/v1/grn/", headers=headers).status_code == 401
    assert anon_client.post("/api/v1/auth/logout", headers=headers).status_code == 401
    auth_module.clear_revoked_tokens()


def test_credential_login_fails_closed_when_unconfigured(anon_client: TestClient):
    """QA-04: Credential login endpoint never simulates authentication; fails closed with 501."""
    resp = anon_client.post(
        "/api/v1/auth/login",
        json={"username": "stores@vspl.com", "password": "wrong-or-any-password"},
    )
    assert resp.status_code == 501
    assert "not configured" in resp.json()["detail"].lower()


def test_grn_reject_and_payment_missing_grn_return_404_not_nameerror(
    anon_client: TestClient, management_headers, stores_headers, role_headers
):
    """QA-07: Missing GRN on /reject and /payment raises clean HTTP 404 (not NameError)."""
    accounts_headers = role_headers(UserRole.ACCOUNTS)
    reject_resp = anon_client.post(
        "/api/v1/grn/999999/reject",
        json={"comments": "QA-07 regression"},
        headers=management_headers,
    )
    assert reject_resp.status_code == 404
    assert reject_resp.json()["detail"] == "GRN not found"

    payment_resp = anon_client.post(
        "/api/v1/grn/999999/payment",
        json={"amount_paid": "100.00", "payment_reference": "UTR-1"},
        headers=accounts_headers,
    )
    assert payment_resp.status_code == 404
    assert payment_resp.json()["detail"] == "GRN not found"

    # Permission gate remains enforced before lookup
    assert anon_client.post(
        "/api/v1/grn/999999/reject",
        json={"comments": "unauthorized"},
        headers=stores_headers,
    ).status_code == 403
    assert anon_client.post(
        "/api/v1/grn/999999/payment",
        json={"payment_status": "PAID"},
        headers=stores_headers,
    ).status_code == 403


def test_token_revocation_isolates_distinct_tokens_and_stays_rejected(anon_client: TestClient):
    """Phase 2: Revoking Token A leaves Token B valid while Token A stays rejected on repeat calls."""
    import time

    auth_module.clear_revoked_tokens()
    try:
        resp_a = anon_client.post("/api/v1/auth/dev-login", json={"role": "Stores"})
        assert resp_a.status_code == 200
        token_a = resp_a.json()["access_token"]

        # Distinct token for the same role AND token for another role
        resp_b_same = anon_client.post("/api/v1/auth/dev-login", json={"role": "Stores"})
        assert resp_b_same.status_code == 200
        token_b_same = resp_b_same.json()["access_token"]

        resp_b_other = anon_client.post("/api/v1/auth/dev-login", json={"role": "Management"})
        assert resp_b_other.status_code == 200
        token_b_other = resp_b_other.json()["access_token"]

        assert token_a != token_b_same

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b_same = {"Authorization": f"Bearer {token_b_same}"}
        headers_b_other = {"Authorization": f"Bearer {token_b_other}"}

        # Both tokens valid before logout
        assert anon_client.get("/api/v1/auth/me", headers=headers_a).status_code == 200
        assert anon_client.get("/api/v1/auth/me", headers=headers_b_same).status_code == 200
        assert anon_client.get("/api/v1/auth/me", headers=headers_b_other).status_code == 200

        # Logout Token A
        assert anon_client.post("/api/v1/auth/logout", headers=headers_a).status_code == 200

        # Token A stays rejected across repeated requests
        for _ in range(3):
            assert anon_client.get("/api/v1/auth/me", headers=headers_a).status_code == 401
            assert anon_client.get("/api/v1/grn/", headers=headers_a).status_code == 401

        # Token B (same role and other role) remains valid
        assert anon_client.get("/api/v1/auth/me", headers=headers_b_same).status_code == 200
        assert anon_client.get("/api/v1/auth/me", headers=headers_b_other).status_code == 200
    finally:
        auth_module.clear_revoked_tokens()


def test_revocation_registry_prunes_expired_entries_and_remains_bounded(monkeypatch):
    """Phase 2: Expired revocations are pruned and active registry never exceeds _MAX_REVOKED_TOKENS."""
    import time

    auth_module.clear_revoked_tokens()
    try:
        now = int(time.time())
        auth_module.revoke_token("dev1.expired.sig", exp=now - 60, jti="expired-jti")
        assert len(auth_module._REVOKED_JTIS) == 1
        assert len(auth_module._REVOKED_TOKEN_HASHES) == 1

        # Checking an unrelated token triggers pruning of expired entries
        assert auth_module.is_token_revoked("dev1.fresh.sig", jti="fresh-jti") is False
        assert "expired-jti" not in auth_module._REVOKED_JTIS
        assert len(auth_module._REVOKED_TOKEN_HASHES) == 0

        # Cap enforcement under repeated revocations
        monkeypatch.setattr(auth_module, "_MAX_REVOKED_TOKENS", 5)
        for idx in range(12):
            auth_module.revoke_token(f"dev1.tok{idx}.sig", exp=now + 300 + idx, jti=f"jti-{idx}")

        assert len(auth_module._REVOKED_JTIS) <= 6
        assert len(auth_module._REVOKED_TOKEN_HASHES) <= 6
        # Most recent revocation remains present; lookup prunes back to <= _MAX_REVOKED_TOKENS
        assert auth_module.is_token_revoked("dev1.tok11.sig", jti="jti-11") is True
        assert len(auth_module._REVOKED_JTIS) <= 5
        assert len(auth_module._REVOKED_TOKEN_HASHES) <= 5
    finally:
        auth_module.clear_revoked_tokens()


def test_grn_missing_record_permissions_and_404_responses(
    anon_client: TestClient,
    stores_headers: dict,
    foundry_headers: dict,
    management_headers: dict,
    role_headers,
):
    """Phase 2: Permission checks precede lookup (403); authorized missing-GRN calls return 404."""
    missing_id = 999999
    accounts_headers = role_headers(UserRole.ACCOUNTS)
    quality_headers = role_headers(UserRole.QUALITY)

    # 1. GET by ID (receipt:read -> Foundry 403, Stores 404)
    assert anon_client.get(f"/api/v1/grn/{missing_id}", headers=foundry_headers).status_code == 403
    get_res = anon_client.get(f"/api/v1/grn/{missing_id}", headers=stores_headers)
    assert get_res.status_code == 404
    assert "not found" in get_res.json()["detail"].lower()

    # 2. Submit & Cancel (receipt:create -> Management 403, Stores 404)
    for suffix in ("submit", "cancel"):
        assert (
            anon_client.post(
                f"/api/v1/grn/{missing_id}/{suffix}",
                json={"comments": "missing"},
                headers=management_headers,
            ).status_code
            == 403
        )
        res = anon_client.post(
            f"/api/v1/grn/{missing_id}/{suffix}",
            json={"comments": "missing"},
            headers=stores_headers,
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    # 3. Approve & Reject (receipt:approve -> Stores 403, Management 404)
    for suffix in ("approve", "reject"):
        assert (
            anon_client.post(
                f"/api/v1/grn/{missing_id}/{suffix}",
                json={"comments": "missing"},
                headers=stores_headers,
            ).status_code
            == 403
        )
        res = anon_client.post(
            f"/api/v1/grn/{missing_id}/{suffix}",
            json={"comments": "missing"},
            headers=management_headers,
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    # 4. Payment (payment:record -> Stores and Management 403, Accounts 404)
    pay_body = {"amount_paid": "10.00", "payment_reference": "UTR-1"}
    for forbidden in (stores_headers, management_headers):
        assert anon_client.post(f"/api/v1/grn/{missing_id}/payment", json=pay_body, headers=forbidden).status_code == 403
    pay_res = anon_client.post(f"/api/v1/grn/{missing_id}/payment", json=pay_body, headers=accounts_headers)
    assert pay_res.status_code == 404
    assert "not found" in pay_res.json()["detail"].lower()

    # 4b. Quality inspection (receipt:quality -> Stores and Management 403, Quality 404)
    qa_body = {"quality_inspection_status": "PASSED"}
    for forbidden in (stores_headers, management_headers):
        assert anon_client.post(f"/api/v1/grn/{missing_id}/quality", json=qa_body, headers=forbidden).status_code == 403
    qa_res = anon_client.post(f"/api/v1/grn/{missing_id}/quality", json=qa_body, headers=quality_headers)
    assert qa_res.status_code == 404

    # 5. Reverse (ledger:reverse -> Stores 403, Management 404)
    assert (
        anon_client.post(
            f"/api/v1/grn/{missing_id}/reverse",
            json={"reason": "Missing GRN reversal check"},
            headers=stores_headers,
        ).status_code
        == 403
    )
    rev_res = anon_client.post(
        f"/api/v1/grn/{missing_id}/reverse",
        json={"reason": "Missing GRN reversal check"},
        headers=management_headers,
    )
    assert rev_res.status_code == 404
    assert "not found" in rev_res.json()["detail"].lower()
