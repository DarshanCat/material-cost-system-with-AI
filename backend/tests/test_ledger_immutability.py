"""
Sprint 2 - append-only stock ledger integrity and reversal-control regression tests.

Layers verified here:
  1. ORM guard: unit-of-work UPDATE/DELETE and bulk ORM update()/delete() on StockLedgerEntry are refused.
  2. SQLite triggers (installed by create_all): raw SQL UPDATE/DELETE is refused by the database itself.
  3. Alembic revision 006 (PostgreSQL triggers) is structurally verified ONLY (single linear head, SQL
     identical to app.db.ledger_guard). It has NOT been executed on PostgreSQL; SQLite passing is not
     evidence of PostgreSQL behaviour.
  4. Static inventory of every code path that inserts into / could modify the ledger.
  5. Reversal controls: compensating entries only, original rows untouched, duplicate/invalid reversals
     rejected with balances unchanged.
"""

import importlib.util
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db import ledger_guard
from app.db.ledger_guard import LedgerImmutableError
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.ledger import StockLedgerEntry, MovementType, SourceDocumentType
from app.models.uom import UOM

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def entry(db_session: Session) -> StockLedgerEntry:
    dept = db_session.query(Department).filter_by(code="FDY").first()
    kg = db_session.query(UOM).filter_by(code="KG").first()
    item = MaterialItem(item_code="FDY-RM-888", name="Immutability Test Material", department_id=dept.id,
                        category="RAW_MATERIALS", base_uom_id=kg.id)
    db_session.add(item)
    db_session.commit()
    e = StockLedgerEntry(
        entry_number="STK-IMM-0001", posting_group_id="POST-IMM", material_item_id=item.id, uom_id=kg.id,
        transaction_date=date.today(), movement_type=MovementType.INWARD_RECEIPT.value,
        quantity_delta=Decimal("100.0000"), source_document_type=SourceDocumentType.GRN.value,
        source_document_id=1, source_line_id=1, source_document_number="GRN-IMM-1", posted_by="usr_seed",
    )
    db_session.add(e)
    db_session.commit()
    return e


def _snapshot(db: Session):
    db.expire_all()
    return [
        (r.id, r.entry_number, r.quantity_delta, r.movement_type, r.reason, r.posted_by, r.reversal_of_entry_id)
        for r in db.execute(select(StockLedgerEntry).order_by(StockLedgerEntry.id)).scalars()
    ]


# --- 1. ORM guard ---------------------------------------------------------------------------------

def test_orm_update_of_posted_entry_is_refused(db_session, entry):
    before = _snapshot(db_session)
    entry.quantity_delta = Decimal("1.0000")
    with pytest.raises(LedgerImmutableError):
        db_session.commit()
    db_session.rollback()
    assert _snapshot(db_session) == before


def test_orm_delete_of_posted_entry_is_refused(db_session, entry):
    before = _snapshot(db_session)
    db_session.delete(entry)
    with pytest.raises(LedgerImmutableError):
        db_session.commit()
    db_session.rollback()
    assert _snapshot(db_session) == before


def test_bulk_orm_update_and_delete_are_refused(db_session, entry):
    before = _snapshot(db_session)
    with pytest.raises(LedgerImmutableError):
        db_session.execute(update(StockLedgerEntry).values(quantity_delta=Decimal("0")))
    with pytest.raises(LedgerImmutableError):
        db_session.execute(delete(StockLedgerEntry))
    db_session.rollback()
    assert _snapshot(db_session) == before


def test_appending_new_entries_still_works(db_session, entry):
    dup_item = entry.material_item_id
    db_session.add(StockLedgerEntry(
        entry_number="STK-IMM-0002", posting_group_id="POST-IMM2", material_item_id=dup_item, uom_id=entry.uom_id,
        transaction_date=date.today(), movement_type=MovementType.INWARD_RECEIPT.value, quantity_delta=Decimal("5.0000"),
        source_document_type=SourceDocumentType.GRN.value, source_document_id=2, source_line_id=2,
        source_document_number="GRN-IMM-2", posted_by="usr_seed",
    ))
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(StockLedgerEntry)).scalar_one() == 2


# --- 2. database-level (SQLite triggers on the test database) -------------------------------------

@pytest.mark.parametrize("sql", [
    "UPDATE stock_ledger_entries SET quantity_delta = 0",
    "UPDATE stock_ledger_entries SET reason = 'tampered' WHERE id = 1",
    "DELETE FROM stock_ledger_entries",
    "DELETE FROM stock_ledger_entries WHERE id = 1",
])
def test_raw_sql_modification_is_refused_by_the_database(db_session, entry, sql):
    before = _snapshot(db_session)
    with pytest.raises(DatabaseError, match="append-only"):
        db_session.execute(text(sql))
    db_session.rollback()
    assert _snapshot(db_session) == before


# --- 3. PostgreSQL migration: structural checks only ----------------------------------------------

def _migration_module():
    path = BACKEND / "migrations" / "versions" / "006_sprint2_ledger_immutability.py"
    spec = importlib.util.spec_from_file_location("rev006", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_chain_is_linear_with_single_head_006():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() in (["007_opening_val_versioning"], ["008_item_code_registry"])
    chain = [r.revision for r in script.walk_revisions()]
    assert chain in (
        [
            "008_item_code_registry", "007_opening_val_versioning", "006_sprint2_ledger_immutability", "005_phase6_costing_valuation",
            "004_phase5_heat_reconciliation", "003_phase4_stock_ledger", "002_phase3_material_entry", "001_phase2_master_data",
        ],
        [
            "007_opening_val_versioning", "006_sprint2_ledger_immutability", "005_phase6_costing_valuation",
            "004_phase5_heat_reconciliation", "003_phase4_stock_ledger", "002_phase3_material_entry", "001_phase2_master_data",
        ],
    )


def test_migration_006_is_frozen_copy_of_guard_sql_and_touches_no_data():
    mig = _migration_module()
    assert mig.PG_UPGRADE_SQL == ledger_guard.PG_UPGRADE_SQL
    assert mig.PG_DOWNGRADE_SQL == ledger_guard.PG_DOWNGRADE_SQL
    joined = " ".join(mig.PG_UPGRADE_SQL + mig.PG_DOWNGRADE_SQL).upper()
    for forbidden in ("INSERT ", "UPDATE STOCK", "DELETE FROM", "DROP TABLE", "ALTER TABLE", "TRUNCATE STOCK"):
        assert forbidden not in joined
    assert "BEFORE UPDATE OR DELETE" in joined and "BEFORE TRUNCATE" in joined
    source = (BACKEND / "migrations" / "versions" / "006_sprint2_ledger_immutability.py").read_text(encoding="utf-8")
    assert "dialect.name != 'postgresql'" in source  # no-op elsewhere


def test_older_migrations_were_not_modified():
    """Guards against rewriting applied revisions: 001-005 must not reference the new guard."""
    for path in (BACKEND / "migrations" / "versions").glob("00[1-5]_*.py"):
        assert "ledger_guard" not in path.read_text(encoding="utf-8")


# --- 4. static inventory of ledger write paths ----------------------------------------------------

def test_ledger_rows_are_only_constructed_by_the_two_posting_services():
    allowed = {"app/services/ledger_service.py", "app/services/opening_balance_service.py"}
    found = set()
    for path in (BACKEND / "app").rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith("app/models/") or rel.startswith("app/db/"):
            continue
        if re.search(r"\bStockLedgerEntry\(", path.read_text(encoding="utf-8")):
            found.add(rel)
    assert found == allowed


def test_no_application_code_updates_or_deletes_ledger_rows():
    pattern = re.compile(r"(update|delete)\(\s*StockLedgerEntry|session\.delete\(\s*\w*entry|db\.delete\(\s*\w*entry", re.I)
    offenders = []
    for path in (BACKEND / "app").rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel == "app/db/ledger_guard.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []


def test_ledger_routes_expose_no_update_or_delete_verbs():
    from app.main import app
    ops = {(m.upper(), p) for p, methods in app.openapi()["paths"].items() if "/ledger" in p for m in methods}
    assert not {o for o in ops if o[0] in {"PUT", "PATCH", "DELETE"}}
    assert {o for o in ops if o[0] == "POST"} == {("POST", "/api/v1/ledger/entries/{entry_id}/reverse")}


# --- 5. reversal controls --------------------------------------------------------------------------

def _count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(StockLedgerEntry)).scalar_one()


def _bal(client, headers, item_id):
    return Decimal(str(client.get(f"/api/v1/ledger/balances/{item_id}", headers=headers).json()["current_balance"]))


def test_reversal_appends_compensating_entry_and_never_touches_the_original(anon_client, db_session, entry, management_headers):
    original_before = _snapshot(db_session)[0]
    resp = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json={"reason": "Weighbridge slip mismatch"}, headers=management_headers)
    assert resp.status_code == 200, resp.text
    rev = resp.json()
    assert rev["movement_type"] == "REVERSAL"
    assert Decimal(str(rev["quantity_delta"])) == Decimal("-100.0000")
    assert rev["reversal_of_entry_id"] == entry.id
    assert rev["posted_by"] == "usr_mgmt_01"
    assert rev["reason"] == "Weighbridge slip mismatch"
    snap = _snapshot(db_session)
    assert snap[0] == original_before and len(snap) == 2
    assert _bal(anon_client, management_headers, entry.material_item_id) == Decimal("0.0000")


def test_duplicate_and_reversal_of_reversal_are_rejected_with_state_unchanged(anon_client, db_session, entry, management_headers):
    rev = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json={"reason": "First correction"}, headers=management_headers).json()
    before = _snapshot(db_session)
    dup = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json={"reason": "Second attempt"}, headers=management_headers)
    assert dup.status_code == 409
    rr = anon_client.post(f"/api/v1/ledger/entries/{rev['id']}/reverse", json={"reason": "Reverse the reversal"}, headers=management_headers)
    assert rr.status_code == 400
    assert _snapshot(db_session) == before


def test_database_enforces_one_reversal_per_original(db_session, entry):
    """Even if the service check were bypassed, UNIQUE(source_document_type, source_line_id) stops a 2nd reversal."""
    from sqlalchemy.exc import IntegrityError

    def reversal(number):
        return StockLedgerEntry(
            entry_number=number, posting_group_id="REV", material_item_id=entry.material_item_id, uom_id=entry.uom_id,
            transaction_date=date.today(), movement_type=MovementType.REVERSAL.value, quantity_delta=Decimal("-100.0000"),
            source_document_type=SourceDocumentType.MANUAL_REVERSAL.value, source_document_id=entry.id,
            source_line_id=entry.id, source_document_number=entry.entry_number, posted_by="x",
            reversal_of_entry_id=entry.id, reason="manual",
        )

    db_session.add(reversal("STK-REV-1"))
    db_session.commit()
    db_session.add(reversal("STK-REV-2"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_reversal_that_would_cause_negative_stock_is_rejected(anon_client, db_session, entry, management_headers):
    # Consume 60 of the 100 kg directly in the ledger (an issue posted earlier); reversing the 100 kg receipt would go negative.
    db_session.add(StockLedgerEntry(
        entry_number="STK-IMM-ISS", posting_group_id="POST-ISS", material_item_id=entry.material_item_id, uom_id=entry.uom_id,
        transaction_date=date.today(), movement_type=MovementType.OUTWARD_ISSUE.value, quantity_delta=Decimal("-60.0000"),
        source_document_type=SourceDocumentType.ISSUE.value, source_document_id=1, source_line_id=1,
        source_document_number="ISS-1", posted_by="usr_seed",
    ))
    db_session.commit()
    before = _snapshot(db_session)
    resp = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json={"reason": "Receipt entered twice"}, headers=management_headers)
    assert resp.status_code == 409
    assert _snapshot(db_session) == before
    assert _bal(anon_client, management_headers, entry.material_item_id) == Decimal("40.0000")


@pytest.mark.parametrize("who,expected", [("stores_headers", 403), ("foundry_headers", 403), ("purchase_headers", 403), (None, 401)])
def test_reversal_denied_for_unauthorized_callers_and_changes_nothing(anon_client, db_session, entry, request, who, expected):
    headers = request.getfixturevalue(who) if who else {}
    before = _snapshot(db_session)
    resp = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json={"reason": "Not allowed to do this"}, headers=headers)
    assert resp.status_code == expected
    assert _snapshot(db_session) == before


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "abc"}, {"reason": None}])
def test_reversal_requires_a_meaningful_reason(anon_client, db_session, entry, management_headers, body):
    before = _snapshot(db_session)
    resp = anon_client.post(f"/api/v1/ledger/entries/{entry.id}/reverse", json=body, headers=management_headers)
    assert resp.status_code == 422
    assert _snapshot(db_session) == before


def test_reversal_of_unknown_entry_is_404(anon_client, db_session, management_headers):
    assert anon_client.post("/api/v1/ledger/entries/999999/reverse", json={"reason": "No such entry"}, headers=management_headers).status_code == 404
