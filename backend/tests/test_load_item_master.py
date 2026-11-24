"""The item master loader: counts, registry and audit rows, idempotence, conflicts abort, dry run writes nothing."""

import copy

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.maintenance.load_item_master import load_plan, run
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.item_code import ItemCodeRegistry, ItemMasterAuditLog
from app.models.uom import UOM
from app.services import item_nomenclature as nom

PLAN = load_plan()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # columns added by migrations 009 and 010 (not mapped on the model)
        conn.execute(text("ALTER TABLE material_items ADD COLUMN cost_head VARCHAR(50)"))
        conn.execute(text("ALTER TABLE material_items ADD COLUMN reconciliation_category VARCHAR(30)"))
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _count(db, model):
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def test_plan_is_internally_consistent():
    codes = [i["item_code"] for i in PLAN["items"]]
    assert len(codes) == len(set(codes)) == 731
    assert all(nom.parse_item_code(c) for c in codes)
    depts = {d["code"] for d in PLAN["departments"]}
    assert depts == {"FDY", "MCS", "MNT", "QLY", "PKD", "UTL", "GEN"}
    assert {i["department_code"] for i in PLAN["items"]} <= depts
    assert all(i["item_code"].startswith(i["department_code"] + "-") for i in PLAN["items"])
    uoms = {u["code"] for u in PLAN["uoms"]}
    assert {i["uom_code"] for i in PLAN["items"]} <= uoms


def test_dry_run_applies_checks_and_writes_nothing(db):
    out = []
    assert run(db, PLAN, commit=False, out=out.append) == 0
    assert any("DRY RUN" in line for line in out)
    assert _count(db, MaterialItem) == _count(db, Department) == _count(db, ItemCodeRegistry) == 0


def test_commit_loads_items_registry_and_audit_rows(db):
    assert run(db, PLAN, commit=True, out=lambda *_: None) == 0
    n = len(PLAN["items"])
    assert _count(db, MaterialItem) == n and _count(db, ItemCodeRegistry) == n and _count(db, ItemMasterAuditLog) == n
    assert _count(db, Department) == 7 and _count(db, UOM) == len(PLAN["uoms"])
    reg = db.execute(select(ItemCodeRegistry).where(ItemCodeRegistry.item_code == "QLY-QC-028")).scalar_one()
    assert (reg.department_code, reg.category_code, reg.serial, reg.standard_version) == ("QLY", "QC", 28, "1.0")
    item = db.execute(select(MaterialItem).where(MaterialItem.item_code == "QLY-QC-028")).scalar_one()
    assert "Legacy code: VSPL-DV-72" in item.description
    row = db.execute(text("SELECT cost_head, reconciliation_category FROM material_items WHERE item_code='FDY-RM-001'")).one()
    assert row[0] == "Material Cost" and row[1] == "HEAT_TRACEABLE"
    audit = db.execute(select(ItemMasterAuditLog).limit(1)).scalar_one()
    assert audit.action == "REGISTERED" and audit.actor_id == "item-master-import"


def test_second_run_is_a_no_op(db):
    run(db, PLAN, commit=True, out=lambda *_: None)
    out = []
    assert run(db, PLAN, commit=True, out=out.append) == 0
    assert "items_new=0" in " ".join(out) and "items_existing=731" in " ".join(out)
    assert _count(db, MaterialItem) == 731 and _count(db, ItemMasterAuditLog) == 731


def test_a_conflicting_existing_item_aborts_everything(db):
    run(db, PLAN, commit=True, out=lambda *_: None)
    changed = copy.deepcopy(PLAN)
    changed["items"][0]["name"] = "Something else"
    changed["items"].append({**PLAN["items"][1], "item_code": "FDY-RM-999", "name": "New one"})
    out = []
    assert run(db, changed, commit=True, out=out.append) == 6
    assert "ABORTED" in out[0]
    assert _count(db, MaterialItem) == 731  # the new item was not added either


def test_department_name_conflict_aborts(db):
    db.add(Department(code="FDY", name="Different Name", is_active=True))
    db.commit()
    assert run(db, PLAN, commit=True, out=lambda *_: None) == 6
    assert _count(db, MaterialItem) == 0
