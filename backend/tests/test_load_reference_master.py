"""
Tests for scripts/load_reference_master.py.

Every database test uses its own in-memory SQLite engine and stub server guards; nothing here connects
to PostgreSQL. Workbooks are generated in tmp_path, except the read-only check of the approved file.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest
from sqlalchemy import create_engine, event, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]
LOADER_PATH = BACKEND_DIR / "scripts" / "load_reference_master.py"

spec = importlib.util.spec_from_file_location("load_reference_master", LOADER_PATH)
loader = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = loader  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(loader)

APPROVED_URL = "postgresql+psycopg://uat_user:secretpw@127.0.0.1:5439/vspl_material_management"

DEPARTMENTS = [
    ("FDY", "Foundry"),
    ("MCS", "Machine Shop"),
    ("MNT", "Maintenance"),
    ("QLY", "Quality"),
    ("PKD", "Packing/Dispatch"),
    ("UTL", "Utilities"),
    ("GEN", "General/Stores"),
]
UOMS = [("Kg", "Kilogram"), ("Nos", "Numbers/Pieces"), ("Ltr", "Litre"), ("Pack", "Pack"), ("Roll", "Roll"), ("Mtr", "Metre")]
CATEGORIES = [("Foundry", "Raw Material", 2), ("Maintenance", "Bearings", 1)]
ITEMS = [
    ("FDY-RM-001", "Bial", "Raw Material", "Foundry", "Kg", "Active"),
    ("FDY-RM-002", "Borings-450/10", "Raw Material", "Foundry", "Kg", "Active"),
    ("MNT-BR-001", "Bearing 6205", "Bearings", "Maintenance", "Nos", "Active"),
]


# ---------------------------------------------------------------------------------------------- helpers
def make_workbook(path: Path, *, departments=DEPARTMENTS, uoms=UOMS, categories=CATEGORIES, items=ITEMS,
                  item_header=("Item Code", "Item Description", "Item Category", "Department", "UOM", "Status")) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Item Master"
    ws.append(list(item_header))
    for row in items:
        ws.append(list(row))
    ws = wb.create_sheet("Departments")
    ws.append(["Code", "Department"])
    for row in departments:
        ws.append(list(row))
    ws = wb.create_sheet("Categories")
    ws.append(["Department", "Cat", "Category", "Cost Head", "Default UOM", "Item Count"])
    for dept, cat, count in categories:
        ws.append([dept, "XX", cat, "Cost", "Kg", count])
    ws = wb.create_sheet("UOM")
    ws.append(["UOM", "Meaning"])
    for row in uoms:
        ws.append(list(row))
    wb.save(path)
    return path


def read(path: Path, expected_item_count: int = len(ITEMS)):
    return loader.read_workbook(
        path,
        expected_sha256=loader.sha256_of(path),
        approved_department_codes=loader.APPROVED_DEPARTMENT_CODES,
        expected_item_count=expected_item_count,
    )


def settings(**overrides):
    values = {"ENVIRONMENT": "development", "DATABASE_URL": None, "sync_database_url": APPROVED_URL}
    values.update(overrides)
    return SimpleNamespace(**values)


class StubGuards:
    """Stands in for PostgresGuards on SQLite and records which guards ran."""

    def __init__(self):
        self.calls = []

    def begin_read_only(self, conn):
        self.calls.append("read_only")

    def verify_server(self, conn, target):
        self.calls.append("verify_server")

    def lock_for_write(self, conn):
        self.calls.append("lock")


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    eng.dispose = lambda: None  # run() disposes its engine; keep the in-memory database for assertions
    yield eng


@pytest.fixture
def workbook(tmp_path):
    return make_workbook(tmp_path / "item_master.xlsx")


def run_loader(engine, workbook, *args, guards=None, item_count=len(ITEMS), cfg=None):
    lines = []
    code = loader.run(
        ["--workbook", str(workbook), *args],
        settings=cfg or settings(),
        engine_factory=lambda _s: engine,
        guards=guards or StubGuards(),
        expected_sha256=loader.sha256_of(workbook),
        expected_item_count=item_count,
        environ={},
        out=lines.append,
    )
    return code, "\n".join(lines)


def table_counts(engine):
    with engine.connect() as conn:
        return {
            t: conn.execute(select(func.count()).select_from(Base.metadata.tables[t])).scalar_one()
            for t in Base.metadata.tables
        }


def add_department(engine, code, name, is_active=True):
    with engine.begin() as conn:
        conn.execute(insert(Base.metadata.tables["departments"]).values(code=code, name=name, is_active=is_active,
                                                                        created_at=func.now(), updated_at=func.now()))


# ---------------------------------------------------------------------------------------------- target
def test_approved_target_is_accepted():
    target = loader.verify_target(settings())
    assert target.describe() == "127.0.0.1:5439/vspl_material_management"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"sync_database_url": APPROVED_URL.replace("127.0.0.1", "localhost")}, "host"),
        ({"sync_database_url": APPROVED_URL.replace(":5439", ":5432")}, "port"),
        ({"sync_database_url": APPROVED_URL.replace(":5439", ":55432")}, "port"),
        ({"sync_database_url": APPROVED_URL.replace("vspl_material_management", "vspl_mm_test")}, "database"),
        ({"sync_database_url": APPROVED_URL.replace("postgresql+psycopg", "sqlite")}, "driver"),
        ({"ENVIRONMENT": "production"}, "ENVIRONMENT"),
        ({"ENVIRONMENT": "test"}, "ENVIRONMENT"),
        ({"DATABASE_URL": APPROVED_URL}, "DATABASE_URL override"),
    ],
)
def test_target_mismatch_is_rejected_without_leaking_credentials(overrides, expected):
    with pytest.raises(loader.TargetRejected) as exc:
        loader.verify_target(settings(**overrides))
    message = str(exc.value)
    assert expected in message
    assert "secretpw" not in message and "uat_user" not in message


@pytest.mark.parametrize("var", loader.LIBPQ_TARGET_ENV_VARS)
def test_libpq_environment_override_is_rejected(var):
    """libpq would apply these after the URL check (e.g. PGHOSTADDR redirects the actual connection)."""
    with pytest.raises(loader.TargetRejected) as exc:
        loader.verify_target(settings(), environ={var: "10.0.0.99"})
    assert var in str(exc.value)
    assert "10.0.0.99" not in str(exc.value)


def test_empty_libpq_variables_are_ignored():
    assert loader.verify_target(settings(), environ={"PGHOSTADDR": ""}).port == 5439


def test_libpq_override_never_builds_an_engine(workbook):
    def must_not_connect(_settings):
        raise AssertionError("engine factory called despite a libpq override")

    code = loader.run(
        ["--workbook", str(workbook)],
        settings=settings(),
        engine_factory=must_not_connect,
        guards=StubGuards(),
        expected_sha256=loader.sha256_of(workbook),
        expected_item_count=len(ITEMS),
        environ={"PGHOSTADDR": "10.0.0.99"},
        out=lambda _line: None,
    )
    assert code == loader.EXIT_TARGET_REJECTED


def test_rejected_target_never_builds_an_engine(workbook):
    def must_not_connect(_settings):
        raise AssertionError("engine factory called for a rejected target")

    lines = []
    code = loader.run(
        ["--workbook", str(workbook), "--commit"],
        settings=settings(sync_database_url=APPROVED_URL.replace(":5439", ":5432")),
        engine_factory=must_not_connect,
        guards=StubGuards(),
        expected_sha256=loader.sha256_of(workbook),
        expected_item_count=len(ITEMS),
        out=lines.append,
    )
    assert code == loader.EXIT_TARGET_REJECTED
    assert "secretpw" not in "\n".join(lines)


def test_invalid_source_is_rejected_before_connecting(workbook):
    def must_not_connect(_settings):
        raise AssertionError("engine factory called for an invalid workbook")

    code = loader.run(
        ["--workbook", str(workbook)],
        settings=settings(),
        engine_factory=must_not_connect,
        guards=StubGuards(),
        expected_sha256="0" * 64,
        expected_item_count=len(ITEMS),
        out=lambda _line: None,
    )
    assert code == loader.EXIT_SOURCE_INVALID


# ---------------------------------------------------------------------------------------------- source validation
def test_valid_workbook_is_parsed_with_text_preserved(workbook):
    source = read(workbook)
    assert {d.code for d in source.departments} == loader.APPROVED_DEPARTMENT_CODES
    assert [u.code for u in source.uoms] == ["KG", "NOS", "LTR", "PACK", "ROLL", "MTR"]
    assert {u.code: u.decimal_precision for u in source.uoms} == {"KG": 4, "NOS": 0, "LTR": 3, "PACK": 0, "ROLL": 0, "MTR": 2}
    assert [(i.item_code, i.category, i.department_code, i.uom_code) for i in source.items] == [
        ("FDY-RM-001", "Raw Material", "FDY", "KG"),
        ("FDY-RM-002", "Raw Material", "FDY", "KG"),
        ("MNT-BR-001", "Bearings", "MNT", "NOS"),
    ]


def test_sha256_mismatch_is_rejected(workbook):
    with pytest.raises(loader.SourceInvalid) as exc:
        loader.read_workbook(workbook, expected_sha256="0" * 64,
                             approved_department_codes=loader.APPROVED_DEPARTMENT_CODES, expected_item_count=3)
    assert "does not match approved" in exc.value.errors[0]


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"items": ITEMS + [("fdy-rm-001", "Dup", "Raw Material", "Foundry", "Kg", "Active")]}, "item code"),
        ({"items": ITEMS + [("FDY-RM-001", "Dup", "Raw Material", "Foundry", "Kg", "Active")]}, "duplicate item code"),
        ({"departments": DEPARTMENTS + [("FDY", "Foundry Two")]}, "duplicate department code"),
        ({"departments": DEPARTMENTS + [("XYZ", "Foundry")]}, "duplicate department name"),
        ({"departments": DEPARTMENTS[:-1]}, "approved set"),
        ({"uoms": UOMS + [("KG", "Kilo again")]}, "duplicate UOM"),
        ({"uoms": UOMS + [("Bag", "Bag"), ("Drum", "Drum")]}, "no approved decimal precision"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", "Bearing", "Bearings", "Nowhere", "Nos", "Active")]}, "unknown department"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", "Bearing", "Bearings", "Maintenance", "Box", "Active")]}, "unknown UOM"),
        ({"items": [ITEMS[0], ITEMS[1], ("FDY-BR-001", "Bearing", "Bearings", "Maintenance", "Nos", "Active")]}, "department code"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", "Bearing", "Bearings", "Maintenance", "Nos", "Inactive")]}, "not 'Active'"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", "Bearing", "Bearings ", "Maintenance", "Nos", "Active")]}, "whitespace"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", None, "Bearings", "Maintenance", "Nos", "Active")]}, "is required"),
        ({"items": [ITEMS[0], ITEMS[1], ("MNT-BR-001", "Bearing", "Belts", "Maintenance", "Nos", "Active")]}, "not declared"),
        ({"items": ITEMS[:2]}, "declares 1 items"),
        ({"item_header": ("Item Code", "Item Description", "Item Category", "Department", "UOM")}, "missing column"),
    ],
)
def test_invalid_source_rows_are_rejected(tmp_path, change, expected):
    path = make_workbook(tmp_path / "bad.xlsx", **change)
    with pytest.raises(loader.SourceInvalid) as exc:
        read(path)
    assert any(expected in e for e in exc.value.errors), exc.value.errors


def test_item_count_must_match_expectation(workbook):
    with pytest.raises(loader.SourceInvalid) as exc:
        read(workbook, expected_item_count=391)
    assert exc.value.errors == ["Item Master has 3 valid items, expected 391"]


def test_approved_workbook_still_validates():
    """Read-only check of the real approved file; no database involved."""
    if not loader.DEFAULT_WORKBOOK.is_file():
        pytest.skip("approved workbook not present on this machine")
    source = loader.read_workbook(
        loader.DEFAULT_WORKBOOK,
        expected_sha256=loader.APPROVED_WORKBOOK_SHA256,
        approved_department_codes=loader.APPROVED_DEPARTMENT_CODES,
        expected_item_count=loader.APPROVED_ITEM_COUNT,
    )
    assert len(source.departments) == 7
    assert sorted(u.code for u in source.uoms) == ["KG", "LTR", "MTR", "NOS", "PACK", "ROLL"]
    assert len(source.items) == 391
    per_dept = {}
    for item in source.items:
        per_dept[item.department_code] = per_dept.get(item.department_code, 0) + 1
    assert per_dept == {"FDY": 87, "GEN": 23, "MCS": 50, "MNT": 217, "PKD": 8, "QLY": 5, "UTL": 1}


# ---------------------------------------------------------------------------------------------- dry run / commit
def test_dry_run_performs_no_writes(engine, workbook):
    statements = []
    event.listen(engine, "before_cursor_execute", lambda *a: statements.append(a[2]))
    guards = StubGuards()
    before = table_counts(engine)

    code, output = run_loader(engine, workbook, guards=guards)

    assert code == loader.EXIT_OK
    assert guards.calls == ["read_only", "verify_server"]
    assert not [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert table_counts(engine) == before
    assert "[departments] insert=7" in output and "[uoms] insert=6" in output and "[material_items] insert=3" in output
    assert "does not prove --commit will succeed" in output


def test_commit_inserts_reference_rows_only(engine, workbook):
    before = table_counts(engine)
    guards = StubGuards()

    code, _ = run_loader(engine, workbook, "--commit", guards=guards)

    assert code == loader.EXIT_OK
    assert guards.calls == ["verify_server", "lock"]
    after = table_counts(engine)
    assert {t: after[t] - before[t] for t in after if after[t] != before[t]} == {
        "departments": 7, "uoms": 6, "material_items": 3,
    }
    with engine.connect() as conn:
        items = Base.metadata.tables["material_items"]
        rows = conn.execute(select(items.c.item_code, items.c.category, items.c.is_active).order_by(items.c.item_code)).all()
    assert rows == [("FDY-RM-001", "Raw Material", True), ("FDY-RM-002", "Raw Material", True), ("MNT-BR-001", "Bearings", True)]


def test_existing_exact_matches_are_skipped(engine, workbook):
    assert run_loader(engine, workbook, "--commit")[0] == loader.EXIT_OK
    counts = table_counts(engine)

    code, output = run_loader(engine, workbook, "--commit")

    assert code == loader.EXIT_OK
    assert table_counts(engine) == counts
    assert "[departments] insert=0 existing_exact_match=7 conflicts=0" in output
    assert "[material_items] insert=0 existing_exact_match=3 conflicts=0" in output


def test_partial_existing_data_inserts_only_missing_rows(engine, workbook):
    add_department(engine, "FDY", "Foundry")
    code, output = run_loader(engine, workbook, "--commit")
    assert code == loader.EXIT_OK
    assert "[departments] insert=6 existing_exact_match=1 conflicts=0" in output
    assert table_counts(engine)["departments"] == 7


@pytest.mark.parametrize(
    "existing, expected",
    [
        (("MCS", "Machine Shop Old", True), "name: database='Machine Shop Old'"),
        (("MSP", "Machine Shop", True), "already belongs to department 'MSP'"),
        (("FDY", "Foundry", False), "is_active: database=False"),
        (("fdy", "Foundry Lower", True), "differs only in case"),
    ],
)
def test_conflicting_existing_rows_abort_without_writing(engine, workbook, existing, expected):
    add_department(engine, *existing)
    before = table_counts(engine)

    code, output = run_loader(engine, workbook, "--commit")

    assert code == loader.EXIT_CONFLICTS
    assert expected in output
    assert table_counts(engine) == before


def test_conflicting_existing_uom_aborts(engine, workbook):
    with engine.begin() as conn:
        conn.execute(insert(Base.metadata.tables["uoms"]).values(code="LTR", name="Liter", decimal_precision=3,
                                                                 is_active=True, created_at=func.now(), updated_at=func.now()))
    before = table_counts(engine)
    code, output = run_loader(engine, workbook, "--commit")
    assert code == loader.EXIT_CONFLICTS
    assert "LTR: name: database='Liter' workbook='Litre'" in output
    assert table_counts(engine) == before


def test_failure_during_insert_rolls_back_everything(engine, workbook, monkeypatch):
    def fail(*_args, **_kwargs):
        raise IntegrityError("INSERT INTO material_items ...", {}, Exception("simulated"))

    monkeypatch.setattr(loader, "_insert_items", fail)
    before = table_counts(engine)

    code, output = run_loader(engine, workbook, "--commit")

    assert code == loader.EXIT_ABORTED
    assert "IntegrityError" in output and "rolled back" in output
    assert table_counts(engine) == before  # departments and UOMs inserted earlier were rolled back


def test_protected_table_change_rolls_back(engine, workbook, monkeypatch):
    real_count = loader.count_protected
    calls = {"n": 0}

    def drifting_count(conn):
        calls["n"] += 1
        counts = real_count(conn)
        if calls["n"] == 2:  # the in-transaction check after inserting
            counts["stock_ledger_entries"] += 1
        return counts

    monkeypatch.setattr(loader, "count_protected", drifting_count)
    before = table_counts(engine)

    code, output = run_loader(engine, workbook, "--commit")

    assert code == loader.EXIT_VERIFICATION_FAILED
    assert "stock_ledger_entries" in output
    assert table_counts(engine) == before


def test_protected_tables_cover_everything_except_targets():
    assert set(loader.PROTECTED_TABLES) == set(Base.metadata.tables) - {"departments", "uoms", "material_items"}
    for table in ("vendors", "grn_headers", "material_issue_headers", "waste_disposition_headers",
                  "physical_audit_headers", "heat_headers", "stock_ledger_entries", "item_opening_valuations", "costing_runs"):
        assert table in loader.PROTECTED_TABLES


def test_loader_import_does_not_create_the_app_engine():
    """Importing the loader must not import app.db.session, which builds an engine from settings."""
    probe = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('m', r'{LOADER_PATH}');"
        "m = importlib.util.module_from_spec(spec); sys.modules['m'] = m; spec.loader.exec_module(m);"
        "print('app.db.session' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=BACKEND_DIR, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
