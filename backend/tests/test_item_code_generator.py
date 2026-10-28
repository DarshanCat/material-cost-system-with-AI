"""
Item Code Generator (Nomenclature Standard v1.0) — database-backed behaviour.

Uses the in-memory SQLite fixtures from conftest.py (schema via create_all, so revision 008 tables exist).
The live PostgreSQL concurrency test is opt-in (TEST_POSTGRES_URL) and is skipped otherwise.

v1.0 departments other than FDY / MNT are not in app/db/seed.py (which carries pre-standard codes such as
MSP, GNS, QLT); tests create the ones they need. Names are suffixed because departments.name is unique and
the seed already uses e.g. 'Machine Shop' for MSP.
"""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db.item_code_guard import ItemHistoryImmutableError
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.item_code import ItemCodeRegistry, ItemCodeSequence, ItemMasterAuditLog
from app.models.item_request import ItemRequest, RequestStatus
from app.models.material_alias import MaterialAlias
from app.models.uom import UOM
from app.services.item_code_service import ItemCodeService


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------

def _dept(db: Session, code: str, name: str | None = None) -> Department:
    dept = db.scalar(select(Department).where(Department.code == code))
    if dept is None:
        dept = Department(code=code, name=name or f"{code} (v1.0 test)", is_active=True)
        db.add(dept)
        db.commit()
        db.refresh(dept)
    return dept


def _uom(db: Session, code: str) -> UOM:
    uom = db.scalar(select(UOM).where(UOM.code == code))
    if uom is None:
        uom = UOM(code=code, name=code.title(), decimal_precision=0, is_active=True)
        db.add(uom)
        db.commit()
        db.refresh(uom)
    return uom


def _item(db: Session, code: str, name: str, dept: Department, category: str, uom: UOM, active: bool = True) -> MaterialItem:
    item = MaterialItem(item_code=code, name=name, department_id=dept.id, category=category, base_uom_id=uom.id, is_active=active)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _request(client: TestClient, headers: dict, dept_id: int, category: str, name: str, uom_id: int):
    return client.post(
        "/api/v1/item-requests",
        json={
            "requested_name": name,
            "proposed_department_id": dept_id,
            "proposed_category": category,
            "proposed_uom_id": uom_id,
            "justification": "Required for maintenance stock.",
        },
        headers=headers,
    )


def _preview(client: TestClient, headers: dict, **body) -> dict:
    res = client.post("/api/v1/item-codes/preview", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _row_counts(db: Session) -> tuple[int, int, int, int]:
    return (
        db.query(MaterialItem).count(),
        db.query(ItemCodeSequence).count(),
        db.query(ItemCodeRegistry).count(),
        db.query(ItemMasterAuditLog).count(),
    )


# ----------------------------------------------------------------------------------------------
# Preview and rules
# ----------------------------------------------------------------------------------------------

def test_preview_is_non_reserving(client: TestClient, db_session: Session, stores_headers):
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    before = _row_counts(db_session)
    body = dict(department_id=fdy.id, category="RM", description="Pig Iron", uom_id=kg.id)
    first = _preview(client, stores_headers, **body)
    second = _preview(client, stores_headers, **body)
    assert first["valid"] is True
    assert first["provisional"] is True
    assert first["proposed_code"] == second["proposed_code"] == "FDY-RM-001"
    assert first["cost_head"] == "Material Cost"
    assert first["serials_remaining"] == 999
    db_session.expire_all()
    assert _row_counts(db_session) == before


def test_preview_reports_errors_warnings_and_cost_head(client: TestClient, db_session: Session, stores_headers):
    fdy, mnt, nos = _dept(db_session, "FDY"), _dept(db_session, "MNT"), _uom(db_session, "NOS")

    wrong_owner = _preview(client, stores_headers, department_id=fdy.id, category="BN", description="Hex Bolt M12x50 MS", uom_id=nos.id)
    assert wrong_owner["valid"] is False
    assert wrong_owner["proposed_code"] is None
    assert "department_mismatch" in {e["code"] for e in wrong_owner["errors"]}

    advisory = _preview(client, stores_headers, department_id=mnt.id, category="Bolts & Nuts", description="hex bolt m12x50", uom_id=nos.id)
    assert advisory["valid"] is True
    assert advisory["proposed_code"] == "MNT-BN-001"
    assert advisory["cost_head"] == "Maintenance Cost"
    assert "all_lower" in {w["code"] for w in advisory["warnings"]}

    incomplete = _preview(client, stores_headers, description="Hex Bolt M12x50 MS")
    assert {e["field"] for e in incomplete["errors"]} >= {"department", "category", "uom"}


def test_rules_endpoint_reports_provisioning(client: TestClient, db_session: Session, stores_headers):
    rules = client.get("/api/v1/item-codes/rules", headers=stores_headers).json()
    assert rules["version"] == "1.0"
    assert rules["registry_installed"] is True
    depts = {d["code"]: d for d in rules["departments"]}
    assert depts["FDY"]["provisioned"] is True and depts["FDY"]["department_id"] is not None
    # The seed carries MSP/GNS/QLT/PKG rather than the v1.0 codes; they are reported, not invented.
    assert {"MCS", "QLY", "PKD", "UTL", "GEN"} <= set(rules["unprovisioned_departments"])
    assert {"Pack", "Roll"} <= set(rules["unprovisioned_uoms"])


# ----------------------------------------------------------------------------------------------
# Strict validation of new requests
# ----------------------------------------------------------------------------------------------

def test_non_standard_department_uom_and_category_are_rejected(client: TestClient, db_session: Session, stores_headers):
    msp = db_session.scalar(select(Department).where(Department.code == "MSP"))  # seeded, pre-standard
    fdy, kg, mt = _dept(db_session, "FDY"), _uom(db_session, "KG"), _uom(db_session, "MT")

    res = _request(client, stores_headers, msp.id, "CB", "Band Saw Blade 3/4 3505", kg.id)
    assert res.status_code == 422
    assert {(e["field"], e["code"]) for e in res.json()["detail"]["errors"]} >= {("department", "not_in_standard")}

    res = _request(client, stores_headers, fdy.id, "RM", "Pig Iron", mt.id)
    assert res.status_code == 422
    assert ("uom", "not_in_standard") in {(e["field"], e["code"]) for e in res.json()["detail"]["errors"]}

    for legacy in ("RAW_MATERIAL", "CONSUMABLE", "GC", "SP"):
        res = _request(client, stores_headers, fdy.id, legacy, "Pig Iron", kg.id)
        assert res.status_code == 422, legacy
    assert db_session.query(ItemRequest).count() == 0


def test_legacy_submitted_request_cannot_be_approved(client: TestClient, db_session: Session, management_headers):
    """A request submitted before v1.0 enforcement fails strict re-validation at approval; nothing is created."""
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    legacy = ItemRequest(
        request_number="REQ-LEGACY-0001",
        requested_name="Inoculant FeSi-75 Premium",
        proposed_department_id=fdy.id,
        proposed_category="ALLOY",
        proposed_uom_id=kg.id,
        justification="Created before the standard was enforced.",
        requester_id="usr_legacy",
        requester_role="Stores",
        requester_department="Stores",
        status=RequestStatus.SUBMITTED.value,
    )
    db_session.add(legacy)
    db_session.commit()
    before = _row_counts(db_session)

    res = client.post(f"/api/v1/item-requests/{legacy.id}/approve", json={}, headers=management_headers)
    assert res.status_code == 422
    assert res.json()["detail"]["errors"][0]["field"] == "category"
    db_session.expire_all()
    assert _row_counts(db_session) == before
    assert db_session.get(ItemRequest, legacy.id).status == RequestStatus.SUBMITTED.value

    rejected = client.post(
        f"/api/v1/item-requests/{legacy.id}/reject",
        json={"comments": "Category ALLOY is not in Nomenclature Standard v1.0; raise a new request."},
        headers=management_headers,
    )
    assert rejected.status_code == 200


# ----------------------------------------------------------------------------------------------
# Serial allocation
# ----------------------------------------------------------------------------------------------

def test_allocation_uses_highest_issued_serial_and_never_fills_gaps(db_session: Session):
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    _item(db_session, "FDY-RM-001", "Bial", fdy, "Raw Material", kg)
    _item(db_session, "FDY-RM-004", "Borings 500", fdy, "Raw Material", kg)
    _item(db_session, "FDY-RM-007", "CRC Scrap", fdy, "Raw Material", kg, active=False)  # retired, still counted

    code, serial = ItemCodeService(db_session).allocate_code("FDY", "RM")
    assert (code, serial) == ("FDY-RM-008", 8)
    db_session.commit()
    assert db_session.get(ItemCodeSequence, ("FDY", "RM")).last_serial == 8


def test_sequence_floor_prevents_reuse_of_codes_no_longer_in_the_master(db_session: Session):
    """Codes once issued stay consumed even if their item rows are no longer present."""
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    db_session.add(ItemCodeSequence(department_code="FDY", category_code="RM", last_serial=12))
    db_session.commit()
    _item(db_session, "FDY-RM-003", "Pig Iron", fdy, "Raw Material", kg)

    code, _ = ItemCodeService(db_session).allocate_code("FDY", "RM")
    assert code == "FDY-RM-013"
    db_session.rollback()


def test_serial_exhaustion_is_rejected(client: TestClient, db_session: Session, stores_headers):
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    _item(db_session, "FDY-RM-999", "Last Raw Material", fdy, "Raw Material", kg)

    with pytest.raises(Exception) as exc:
        ItemCodeService(db_session).allocate_code("FDY", "RM")
    assert getattr(exc.value, "status_code", None) == 409
    assert "exhausted" in exc.value.detail
    db_session.rollback()

    preview = _preview(client, stores_headers, department_id=fdy.id, category="RM", description="Pig Iron", uom_id=kg.id)
    assert preview["valid"] is False
    assert preview["proposed_code"] is None
    assert "serial_exhausted" in {e["code"] for e in preview["errors"]}


def test_approval_registers_code_history_and_sequence(
    client: TestClient, db_session: Session, stores_headers, management_headers
):
    mnt, nos = _dept(db_session, "MNT"), _uom(db_session, "NOS")
    _item(db_session, "MNT-BN-136", "Hex Nut M24", mnt, "Bolts & Nuts", nos)  # existing legacy highest serial

    created = _request(client, stores_headers, mnt.id, "BN", "Hex Bolt M12x50 MS", nos.id)
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    assert client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers).status_code == 200
    approved = client.post(f"/api/v1/item-requests/{req_id}/approve", json={}, headers=management_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["linked_item_code"] == "MNT-BN-137"

    db_session.expire_all()
    registry = db_session.scalar(select(ItemCodeRegistry).where(ItemCodeRegistry.item_code == "MNT-BN-137"))
    assert registry.serial == 137
    assert registry.item_request_id == req_id
    assert registry.standard_version == "1.0"
    assert registry.issued_by != created.json()["requester_id"]  # issued by the approver
    item = db_session.get(MaterialItem, registry.material_item_id)
    assert (item.category, item.is_active) == ("Bolts & Nuts", True)
    assert db_session.get(ItemCodeSequence, ("MNT", "BN")).last_serial == 137
    events = db_session.scalars(select(ItemMasterAuditLog).where(ItemMasterAuditLog.material_item_id == item.id)).all()
    assert [e.action for e in events] == ["REGISTERED"]


# ----------------------------------------------------------------------------------------------
# Duplicate detection
# ----------------------------------------------------------------------------------------------

def test_duplicates_include_retired_items_other_departments_and_aliases(
    client: TestClient, db_session: Session, stores_headers
):
    fdy, mnt, msp = _dept(db_session, "FDY"), _dept(db_session, "MNT"), db_session.scalar(select(Department).where(Department.code == "MSP"))
    mcs, nos = _dept(db_session, "MCS", "Machine Shop (v1.0 test)"), _uom(db_session, "NOS")

    _item(db_session, "MNT-BN-010", "Hex Bolt M12x50 MS", mnt, "Bolts & Nuts", nos, active=False)
    res = _request(client, stores_headers, mnt.id, "BN", "Hex Bolt M12X50 MS", nos.id)
    assert res.status_code == 409
    assert "inactive (retired)" in res.json()["detail"]["message"]

    _item(db_session, "MSP-CB-001", "Band Saw Blade 3/4 3505", msp, "Cutting Blades", nos)  # legacy department
    res = _request(client, stores_headers, mcs.id, "CB", "Band Saw Blade 3/4 3505", nos.id)
    assert res.status_code == 409
    assert res.json()["detail"]["duplicates"][0]["item_code"] == "MSP-CB-001"

    flap = _item(db_session, "FDY-CN-016", "Flap Disk 5 Inch", fdy, "Consumables", nos)
    db_session.add(MaterialAlias(alias_text="Flop Disk 5 Inch", normalized_alias_key="flop disk 5 inch", material_item_id=flap.id, created_by="usr_seed"))
    db_session.commit()
    res = _request(client, stores_headers, fdy.id, "CN", "Flop Disk 5 Inch", nos.id)
    assert res.status_code == 409
    assert res.json()["detail"]["duplicates"][0]["source"] == "ALIAS"


def test_open_request_duplicates(client: TestClient, db_session: Session, stores_headers, purchase_headers):
    fdy, nos = _dept(db_session, "FDY"), _uom(db_session, "NOS")
    first = _request(client, stores_headers, fdy.id, "CN", "Mould Sealing Rope", nos.id)
    assert first.status_code == 201

    # A similar DRAFT is a warning only; the second request may be drafted and submitted.
    second = _request(client, purchase_headers, fdy.id, "CN", "Mould-Sealing Rope", nos.id)
    assert second.status_code == 201, second.text
    preview = _preview(
        client, stores_headers, department_id=fdy.id, category="CN", description="Mould Sealing Rope", uom_id=nos.id,
        exclude_request_id=first.json()["id"],
    )
    assert "possible_duplicate" in {w["code"] for w in preview["warnings"]}
    assert client.post(f"/api/v1/item-requests/{second.json()['id']}/submit", headers=purchase_headers).status_code == 200

    # Once one is SUBMITTED, the other cannot be submitted and new duplicates cannot be drafted.
    blocked = client.post(f"/api/v1/item-requests/{first.json()['id']}/submit", headers=stores_headers)
    assert blocked.status_code == 409
    assert _request(client, stores_headers, fdy.id, "CN", "Mould Sealing Rope", nos.id).status_code == 409


# ----------------------------------------------------------------------------------------------
# Legacy compatibility, history and immutability
# ----------------------------------------------------------------------------------------------

def test_compliance_report_lists_legacy_codes_without_modifying_them(client: TestClient, db_session: Session, stores_headers):
    gns = db_session.scalar(select(Department).where(Department.code == "GNS"))
    mnt, nos = _dept(db_session, "MNT"), _uom(db_session, "NOS")
    legacy = [
        _item(db_session, "GNS-GC-001", "Cotton Waste", gns, "General Consumables", nos),
        _item(db_session, "MCS-IT-TNMG160408", "TNMG160408", mnt, "Inserts & Tools", nos),
    ]
    ok = _item(db_session, "MNT-BN-001", "Nut M12", mnt, "Bolts & Nuts", nos)
    snapshot = {i.id: (i.item_code, i.name, i.category, i.is_active, i.updated_at) for i in legacy + [ok]}

    report = client.get("/api/v1/item-codes/compliance", headers=stores_headers).json()
    flagged = {row["item_code"]: row for row in report["items"]}
    assert set(flagged) == {"GNS-GC-001", "MCS-IT-TNMG160408"}
    assert flagged["GNS-GC-001"]["item_id"] == legacy[0].id
    assert any("not a v1.0 department" in r for r in flagged["GNS-GC-001"]["reasons"])
    assert "Grandfathered" in report["policy"]

    db_session.expire_all()
    for item_id, before in snapshot.items():
        i = db_session.get(MaterialItem, item_id)
        assert (i.item_code, i.name, i.category, i.is_active, i.updated_at) == before

    # Legacy items stay readable and usable in the item master.
    assert client.get(f"/api/v1/items/{legacy[0].id}", headers=stores_headers).status_code == 200


def test_rename_requires_reason_and_cannot_create_a_duplicate(client: TestClient, db_session: Session, management_headers):
    fdy, mnt, nos = _dept(db_session, "FDY"), _dept(db_session, "MNT"), _uom(db_session, "NOS")
    target = _item(db_session, "FDY-PT-001", "Paint Red Oil", fdy, "Paints & Coatings", nos)
    _item(db_session, "MNT-OL-001", "Rust Preventive Oil RPL-120", mnt, "Oils & Lubricants", nos)

    no_reason = client.put(f"/api/v1/items/{target.id}", json={"name": "Paint Red Oil Based"}, headers=management_headers)
    assert no_reason.status_code == 400

    duplicate = client.put(
        f"/api/v1/items/{target.id}",
        json={"name": "Rust Preventive Oil RPL 120", "change_reason": "Correction"},
        headers=management_headers,
    )
    assert duplicate.status_code == 409

    ok = client.put(
        f"/api/v1/items/{target.id}",
        json={"name": "Paint Red Oil Based", "change_reason": "Spelling correction approved by Stores."},
        headers=management_headers,
    )
    assert ok.status_code == 200
    events = client.get(f"/api/v1/items/{target.id}/history", headers=management_headers).json()["events"]
    assert [(e["action"], e["old_value"], e["new_value"]) for e in events] == [("RENAMED", "Paint Red Oil", "Paint Red Oil Based")]


def test_registry_and_item_history_are_append_only(
    client: TestClient, db_session: Session, stores_headers, management_headers
):
    fdy, kg = _dept(db_session, "FDY"), _uom(db_session, "KG")
    req_id = _request(client, stores_headers, fdy.id, "RM", "Pig Iron", kg.id).json()["id"]
    client.post(f"/api/v1/item-requests/{req_id}/submit", headers=stores_headers)
    assert client.post(f"/api/v1/item-requests/{req_id}/approve", json={}, headers=management_headers).status_code == 200

    db_session.expire_all()
    registry = db_session.scalar(select(ItemCodeRegistry))
    registry.item_code = "FDY-RM-002"
    with pytest.raises(ItemHistoryImmutableError):
        db_session.flush()
    db_session.rollback()

    event = db_session.scalar(select(ItemMasterAuditLog))
    db_session.delete(event)
    with pytest.raises(ItemHistoryImmutableError):
        db_session.flush()
    db_session.rollback()

    for statement in ("UPDATE item_code_registry SET serial = 2", "DELETE FROM item_master_audit_logs"):
        with pytest.raises(DatabaseError):
            db_session.execute(text(statement))
        db_session.rollback()


def test_approval_refused_when_registry_schema_missing(db_session: Session, monkeypatch):
    """Deployment guard: without revision 008 the generator refuses to allocate rather than allocating unsafely."""
    service = ItemCodeService(db_session)
    monkeypatch.setattr(ItemCodeService, "registry_installed", lambda self: False)
    with pytest.raises(Exception) as exc:
        service.allocate_code("FDY", "RM")
    assert getattr(exc.value, "status_code", None) == 503


# ----------------------------------------------------------------------------------------------
# Live PostgreSQL concurrency (opt-in)
# ----------------------------------------------------------------------------------------------

def test_postgres_concurrent_allocation_never_duplicates(pg_session_factory):
    """Four sessions allocate for the same pair at once; SELECT ... FOR UPDATE yields distinct serials."""
    with pg_session_factory() as probe:
        if not all(inspect(probe.get_bind()).has_table(t) for t in ("item_code_sequences", "item_code_registry")):
            pytest.skip("Revision 008_item_code_registry is not applied to the PostgreSQL test database.")
        original = probe.get(ItemCodeSequence, ("UTL", "FU"))
        original_serial = original.last_serial if original else None

    workers = 4
    barrier = threading.Barrier(workers)
    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _worker():
        try:
            with pg_session_factory() as db:
                barrier.wait()
                code, _ = ItemCodeService(db).allocate_code("UTL", "FU")
                db.commit()
                with lock:
                    results.append(code)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(workers)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors, errors
        assert len(results) == workers
        assert len(set(results)) == workers
        serials = sorted(int(c.rsplit("-", 1)[1]) for c in results)
        assert serials == list(range(serials[0], serials[0] + workers))
    finally:
        # Restore the test sequence row (sequences are not append-only).
        with pg_session_factory() as db:
            row = db.get(ItemCodeSequence, ("UTL", "FU"))
            if original_serial is None and row is not None:
                db.delete(row)
            elif row is not None:
                row.last_serial = original_serial
            db.commit()
