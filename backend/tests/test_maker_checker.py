"""
Sprint 2 - maker-checker (separation of duties) regression tests.

Creator approval is refused server-side for documents that post to the stock ledger (GRN, issue slip,
waste disposition, physical audit). The check uses the authenticated actor from Sprint 1; request-body or
query-string user ids cannot influence it. Rejected attempts must leave documents, audit logs and the
ledger unchanged.

Role assignments for who may approve each document type are NOT defined in the business rules; these
tests only use the provisional permission matrix and make no claim about the correct assignment.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.department import Department
from app.models.grn import GRNHeader
from app.models.issue import MaterialIssueHeader
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.material_alias import MaterialAlias
from app.models.physical_audit import PhysicalAuditHeader
from app.models.uom import UOM
from app.models.waste import WasteDispositionHeader
from app.services.maker_checker import enforce_maker_checker, enforced_document_types


@pytest.fixture
def world(db_session: Session):
    fdy = db_session.query(Department).filter_by(code="FDY").first()
    msp = db_session.query(Department).filter_by(code="MSP").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(item_code="FDY-RM-777", name="Maker Checker Test Material", department_id=fdy.id,
                        category="RAW_MATERIALS", base_uom_id=kg.id)
    db_session.add(item)
    db_session.commit()
    db_session.add(StockLedgerEntry(
        entry_number="STK-MC-OB", posting_group_id="POST-MC-OB", material_item_id=item.id, uom_id=kg.id,
        transaction_date=date(2026, 10, 12), movement_type=MovementType.OPENING_BALANCE.value,
        quantity_delta=Decimal("1000.0000"), source_document_type=SourceDocumentType.OPENING_BALANCE.value,
        source_document_id=0, source_line_id=item.id, source_document_number="OB-MC", posted_by="usr_seed",
    ))
    db_session.commit()
    return {"fdy": fdy, "msp": msp, "kg": kg, "item": item}


def _payloads(w):
    line = {"line_number": 1, "material_item_id": w["item"].id, "uom_id": w["kg"].id, "quantity": "10.00"}
    return {
        "grn": ("/api/v1/grn/", {"receipt_date": str(date.today()), "source_type": "INTERNAL_VSPL", "lines": [line]}),
        "issue": ("/api/v1/issues/", {"issue_date": str(date.today()), "issuing_department_id": w["fdy"].id,
                                      "receiving_department_id": w["msp"].id, "lines": [line]}),
        "waste": ("/api/v1/waste/", {"disposition_date": str(date.today()), "waste_type": "BORINGS",
                                     "disposition_type": "INTERNAL_RECOVERY", "source_department_id": w["msp"].id,
                                     "destination_notes": "remelt", "lines": [{**line, "reason": "generation"}]}),
        "audit": ("/api/v1/physical-audits/", {"audit_date": str(date.today()), "lines": [
            {"material_item_id": w["item"].id, "uom_id": w["kg"].id, "physical_quantity": "990.00", "reason": "count"}]}),
    }


DOCS = {
    # name: (collection url, model)
    "grn": ("/api/v1/grn", GRNHeader),
    "issue": ("/api/v1/issues", MaterialIssueHeader),
    "waste": ("/api/v1/waste", WasteDispositionHeader),
    "audit": ("/api/v1/physical-audits", PhysicalAuditHeader),
}


def _create_submitted(client: TestClient, w, kind: str, creator_headers: dict) -> int:
    url, body = _payloads(w)[kind]
    created = client.post(url, json=body, headers=creator_headers)
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    sub = client.post(f"{DOCS[kind][0]}/{doc_id}/submit", json={}, headers=creator_headers)
    assert sub.status_code == 200, sub.text
    return doc_id


def _ledger_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(StockLedgerEntry)).scalar_one()


def _balance(client: TestClient, item_id: int, headers: dict) -> Decimal:
    return Decimal(str(client.get(f"/api/v1/ledger/balances/{item_id}", headers=headers).json()["current_balance"]))


@pytest.mark.parametrize("kind", list(DOCS))
def test_creator_cannot_approve_own_document(anon_client, db_session, world, admin_headers, kind):
    doc_id = _create_submitted(anon_client, world, kind, admin_headers)  # Admin holds every permission
    before_ledger, before_bal = _ledger_count(db_session), _balance(anon_client, world["item"].id, admin_headers)

    resp = anon_client.post(f"{DOCS[kind][0]}/{doc_id}/approve", json={"comments": "self approval"}, headers=admin_headers)

    assert resp.status_code == 403, resp.text
    assert "Maker-checker" in resp.json()["detail"]
    db_session.expire_all()
    assert db_session.get(DOCS[kind][1], doc_id).status == "SUBMITTED"
    assert _ledger_count(db_session) == before_ledger
    assert _balance(anon_client, world["item"].id, admin_headers) == before_bal


@pytest.mark.parametrize("kind", list(DOCS))
def test_spoofed_request_user_ids_cannot_bypass_maker_checker(anon_client, db_session, world, admin_headers, kind):
    doc_id = _create_submitted(anon_client, world, kind, admin_headers)
    resp = anon_client.post(
        f"{DOCS[kind][0]}/{doc_id}/approve?actor_id=someone_else&approver_id=someone_else&created_by=x",
        json={"comments": "x", "actor_id": "someone_else", "approver_id": "someone_else", "created_by": "x"},
        headers={**admin_headers, "X-User-Id": "someone_else", "X-User-Role": "Management"},
    )
    assert resp.status_code == 403
    db_session.expire_all()
    assert db_session.get(DOCS[kind][1], doc_id).status == "SUBMITTED"


@pytest.mark.parametrize("kind", list(DOCS))
def test_different_authorized_approver_can_approve_and_is_recorded(anon_client, db_session, world, stores_headers, management_headers, kind):
    # Stores creates (all four types are creatable by Stores in the provisional matrix); Management approves.
    doc_id = _create_submitted(anon_client, world, kind, stores_headers)
    before = _ledger_count(db_session)
    resp = anon_client.post(f"{DOCS[kind][0]}/{doc_id}/approve", json={}, headers=management_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "APPROVED"
    entries = db_session.execute(select(StockLedgerEntry).where(
        StockLedgerEntry.source_document_type != SourceDocumentType.OPENING_BALANCE.value)).scalars().all()
    assert entries and _ledger_count(db_session) > before
    assert {e.posted_by for e in entries} == {"usr_mgmt_01"}
    logs = resp.json()["audit_logs"]
    assert {(a["action"], a["actor_id"]) for a in logs} >= {("CREATED", "usr_stores_01"), ("APPROVED", "usr_mgmt_01")}


@pytest.mark.parametrize("kind", list(DOCS))
def test_unauthorized_roles_cannot_approve_and_nothing_changes(anon_client, db_session, world, stores_headers, foundry_headers, purchase_headers, kind):
    doc_id = _create_submitted(anon_client, world, kind, stores_headers)
    before = _ledger_count(db_session)
    for headers in (stores_headers, foundry_headers, purchase_headers, {}):
        resp = anon_client.post(f"{DOCS[kind][0]}/{doc_id}/approve", json={}, headers=headers)
        assert resp.status_code in (401, 403), resp.text
    db_session.expire_all()
    assert db_session.get(DOCS[kind][1], doc_id).status == "SUBMITTED"
    assert _ledger_count(db_session) == before


@pytest.mark.parametrize("kind", list(DOCS))
def test_repeated_approval_is_rejected_and_posts_once(anon_client, db_session, world, stores_headers, management_headers, admin_headers, kind):
    doc_id = _create_submitted(anon_client, world, kind, stores_headers)
    assert anon_client.post(f"{DOCS[kind][0]}/{doc_id}/approve", json={}, headers=management_headers).status_code == 200
    after_first = _ledger_count(db_session)
    bal = _balance(anon_client, world["item"].id, admin_headers)
    for headers in (management_headers, admin_headers):
        again = anon_client.post(f"{DOCS[kind][0]}/{doc_id}/approve", json={}, headers=headers)
        assert again.status_code == 400, again.text
    assert _ledger_count(db_session) == after_first
    assert _balance(anon_client, world["item"].id, admin_headers) == bal


def test_failed_posting_rolls_back_status_audit_and_ledger(anon_client, db_session, world, stores_headers, management_headers):
    """Issue approval that fails stock validation must leave the slip SUBMITTED with no new audit/ledger rows."""
    url, body = _payloads(world)["issue"]
    body["lines"][0]["quantity"] = "5000.00"  # exceeds the 1000 kg opening balance
    doc_id = anon_client.post(url, json=body, headers=stores_headers).json()["id"]
    anon_client.post(f"/api/v1/issues/{doc_id}/submit", json={}, headers=stores_headers)
    before = _ledger_count(db_session)
    resp = anon_client.post(f"/api/v1/issues/{doc_id}/approve", json={}, headers=management_headers)
    assert resp.status_code == 409
    db_session.expire_all()
    issue = db_session.get(MaterialIssueHeader, doc_id)
    assert issue.status == "SUBMITTED"
    assert [a.action for a in issue.audit_logs] == ["CREATED", "SUBMITTED"]
    assert _ledger_count(db_session) == before


def test_concurrent_approval_conflict_is_reported_as_409_and_posts_nothing(anon_client, db_session, world, stores_headers, management_headers, monkeypatch):
    """
    Simulates the losing side of a concurrent approval: the database rejects the duplicate posting
    (UNIQUE(source_document_type, source_line_id) / unique entry_number). The API must answer 409,
    roll everything back and leave the document SUBMITTED. Real multi-session concurrency is NOT
    exercised here (SQLite, single connection) and must be verified on PostgreSQL.
    """
    doc_id = _create_submitted(anon_client, world, "grn", stores_headers)
    from app.services import ledger_service

    def boom(db, grn, actor_id):
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: uq_source_doc_line_posting"))

    monkeypatch.setattr(ledger_service, "post_grn_to_ledger", boom)
    before = _ledger_count(db_session)
    resp = anon_client.post(f"/api/v1/grn/{doc_id}/approve", json={}, headers=management_headers)
    assert resp.status_code == 409
    db_session.expire_all()
    assert db_session.get(GRNHeader, doc_id).status == "SUBMITTED"
    assert _ledger_count(db_session) == before
    monkeypatch.undo()
    assert anon_client.post(f"/api/v1/grn/{doc_id}/approve", json={}, headers=management_headers).status_code == 200


def test_database_rejects_a_second_posting_of_the_same_source_line(anon_client, db_session, world, stores_headers, management_headers):
    doc_id = _create_submitted(anon_client, world, "grn", stores_headers)
    anon_client.post(f"/api/v1/grn/{doc_id}/approve", json={}, headers=management_headers)
    posted = db_session.execute(select(StockLedgerEntry).where(StockLedgerEntry.source_document_type == "GRN")).scalars().first()
    dup = StockLedgerEntry(
        entry_number="STK-DUP-0001", posting_group_id="DUP", material_item_id=posted.material_item_id, uom_id=posted.uom_id,
        transaction_date=posted.transaction_date, movement_type=posted.movement_type, quantity_delta=posted.quantity_delta,
        source_document_type="GRN", source_document_id=posted.source_document_id, source_line_id=posted.source_line_id,
        source_document_number=posted.source_document_number, posted_by="x",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---- configuration / service-level behaviour ----------------------------------------------------

def test_default_policy_covers_ledger_posting_documents_only():
    assert enforced_document_types() == {"GRN", "ISSUE", "WASTE", "PHYSICAL_AUDIT"}


def test_service_layer_enforces_regardless_of_the_endpoint():
    # Same person, different casing / whitespace, is still the same person.
    with pytest.raises(Exception) as exc:
        enforce_maker_checker("GRN", "usr_admin_01", "  USR_ADMIN_01 ", "GRN-X")
    assert getattr(exc.value, "status_code", None) == 403
    enforce_maker_checker("GRN", "usr_stores_01", "usr_mgmt_01", "GRN-X")  # different person passes


def test_policy_is_configurable_without_code_change(anon_client, db_session, world, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAKER_CHECKER_DOCUMENTS", "")
    doc_id = _create_submitted(anon_client, world, "grn", admin_headers)
    assert anon_client.post(f"/api/v1/grn/{doc_id}/approve", json={}, headers=admin_headers).status_code == 200


def test_alias_maker_checker_is_available_but_off_by_default(anon_client, db_session, world, management_headers, monkeypatch):
    def new_alias(text):
        r = anon_client.post("/api/v1/material-aliases", json={"alias_text": text, "material_item_id": world["item"].id, "status": "PENDING"}, headers=management_headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    a1 = new_alias("MC alias one")
    assert anon_client.post(f"/api/v1/material-aliases/{a1}/approve", json={}, headers=management_headers).status_code == 200  # off by default

    monkeypatch.setattr(settings, "MAKER_CHECKER_DOCUMENTS", "ALIAS")
    a2 = new_alias("MC alias two")
    resp = anon_client.post(f"/api/v1/material-aliases/{a2}/approve", json={}, headers=management_headers)
    assert resp.status_code == 403
    db_session.expire_all()
    assert db_session.get(MaterialAlias, a2).status == "PENDING"
