"""
Guarded UAT reference-data loader.

Loads departments, units of measure and material items from the approved VSPL Item Master workbook
into the local NON-PRODUCTION database, so browser UAT has reference data to select from. It never
touches vendors, documents, ledger, valuation or costing tables.

Safety model
  * Dry-run by default: one READ ONLY transaction, rolled back. `--commit` is required to insert.
  * The database target is checked BEFORE any connection: 127.0.0.1:5439/vspl_material_management,
    ENVIRONMENT=development, no DATABASE_URL override and no libpq PG* connection variables (which could
    otherwise redirect the connection). The server is then re-checked after connecting.
  * The workbook must match the recorded SHA256 and pass structural/reference validation.
  * Insert-only by natural key (department code, UOM code, item code). Existing rows are never updated,
    reactivated or deleted; an existing row that differs from the workbook aborts the run.
  * One transaction for the commit; any error rolls everything back. Row counts of every other table
    are compared before and after and the run aborts if any changed.

Usage (from backend/):
  .venv\\Scripts\\python.exe scripts\\load_reference_master.py            # dry run
  .venv\\Scripts\\python.exe scripts\\load_reference_master.py --commit   # insert missing rows
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import openpyxl  # noqa: E402
from sqlalchemy import create_engine, func, insert, select, text  # noqa: E402
from sqlalchemy.engine import Connection, Engine, make_url  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.models  # noqa: E402,F401  registers every table on Base.metadata
from app.db.base import Base  # noqa: E402
from app.db.seed import INITIAL_UOMS  # noqa: E402

# --------------------------------------------------------------------------------------------------
# Approved target and source (change only with explicit approval)
# --------------------------------------------------------------------------------------------------
APPROVED_DRIVER = "postgresql+psycopg"
APPROVED_HOST = "127.0.0.1"
APPROVED_PORT = 5439
APPROVED_DATABASE = "vspl_material_management"
APPROVED_ENVIRONMENT = "development"
APPROVED_ALEMBIC_REVISION = "007_opening_val_versioning"

# libpq fills any connection parameter missing from the URL from these variables, so they could redirect
# the connection (PGHOSTADDR, a service entry) or the schema (PGOPTIONS search_path) after the URL check.
LIBPQ_TARGET_ENV_VARS = (
    "PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR", "PGOPTIONS",
)

DEFAULT_WORKBOOK = Path(r"C:\VSPL_MM\VSPL_MM_Data\inputs\VSPL_Item_Master.xlsx")
APPROVED_WORKBOOK_SHA256 = "6005441b7b022cc8b6e4e65b2d2563ca4462e2448eb3c66d5fdf40552c6e8ccd"
APPROVED_DEPARTMENT_CODES = frozenset({"FDY", "MCS", "MNT", "GEN", "PKD", "QLY", "UTL"})
APPROVED_ITEM_COUNT = 391

# UOM codes are stored upper-case, matching the existing seed convention (KG, NOS, LTR, MTR).
# Decimal precision follows app/db/seed.py; PACK and ROLL are counted units like BAG and SET.
UOM_PRECISION = {u["code"]: u["decimal_precision"] for u in INITIAL_UOMS} | {"PACK": 0, "ROLL": 0}

# Item code format from docs/BUSINESS_RULES.md.
ITEM_CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,5}-[A-Z0-9]{2,5}-[0-9]{3,6}$")

TARGET_TABLES = ("departments", "uoms", "material_items")
PROTECTED_TABLES = tuple(sorted(name for name in Base.metadata.tables if name not in TARGET_TABLES))

DEPARTMENTS = Base.metadata.tables["departments"]
UOMS = Base.metadata.tables["uoms"]
ITEMS = Base.metadata.tables["material_items"]

EXIT_OK = 0
EXIT_TARGET_REJECTED = 2
EXIT_SOURCE_INVALID = 3
EXIT_CONFLICTS = 4
EXIT_VERIFICATION_FAILED = 5
EXIT_ABORTED = 6

DRY_RUN_DISCLAIMER = (
    "Dry run only: nothing was written. This does not prove --commit will succeed; data can change "
    "between runs, and constraints, locks and triggers are only exercised by a real commit."
)


class TargetRejected(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class SourceInvalid(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} source validation error(s)")
        self.errors = errors


class VerificationFailed(Exception):
    pass


# --------------------------------------------------------------------------------------------------
# 1. Target verification (no connection)
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Target:
    host: str
    port: int
    database: str

    def describe(self) -> str:
        return f"{self.host}:{self.port}/{self.database}"


def verify_target(settings: Any, environ: Mapping[str, str] | None = None) -> Target:
    """Reject anything but the approved non-production target. Never reports credentials."""
    environ = os.environ if environ is None else environ
    problems: list[str] = []
    overrides = [name for name in LIBPQ_TARGET_ENV_VARS if environ.get(name)]
    if overrides:
        problems.append(f"libpq environment override(s) set: {', '.join(overrides)} (unset them to run)")
    if getattr(settings, "DATABASE_URL", None):
        problems.append("DATABASE_URL override is set; only the approved POSTGRES_* target is accepted")
    if settings.ENVIRONMENT != APPROVED_ENVIRONMENT:
        problems.append(f"ENVIRONMENT is {settings.ENVIRONMENT!r}, expected {APPROVED_ENVIRONMENT!r}")
    if problems and getattr(settings, "DATABASE_URL", None):
        raise TargetRejected(problems)  # do not parse an override URL at all

    try:
        url = make_url(settings.sync_database_url)
    except Exception:
        raise TargetRejected(problems + ["database URL could not be parsed"]) from None

    if url.drivername != APPROVED_DRIVER:
        problems.append(f"driver is {url.drivername!r}, expected {APPROVED_DRIVER!r}")
    if url.host != APPROVED_HOST:
        problems.append(f"host is {url.host!r}, expected {APPROVED_HOST!r}")
    if url.port != APPROVED_PORT:
        problems.append(f"port is {url.port!r}, expected {APPROVED_PORT}")
    if url.database != APPROVED_DATABASE:
        problems.append(f"database is {url.database!r}, expected {APPROVED_DATABASE!r}")
    if problems:
        raise TargetRejected(problems)
    return Target(host=url.host, port=url.port, database=url.database)


# --------------------------------------------------------------------------------------------------
# 2. Source workbook validation (no database)
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DepartmentRow:
    code: str
    name: str


@dataclass(frozen=True)
class UomRow:
    code: str  # canonical (upper-case)
    source_code: str
    name: str
    decimal_precision: int


@dataclass(frozen=True)
class ItemRow:
    row_number: int
    item_code: str
    name: str
    category: str
    department_code: str
    uom_code: str  # canonical


@dataclass
class SourceData:
    sha256: str
    departments: list[DepartmentRow]
    uoms: list[UomRow]
    items: list[ItemRow]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sheet_rows(wb, sheet: str, required: tuple[str, ...], errors: list[str]) -> list[tuple[int, dict]]:
    """Non-empty rows of a sheet as (excel_row_number, {header: value}); records structural errors."""
    if sheet not in wb.sheetnames:
        errors.append(f"missing sheet {sheet!r}")
        return []
    rows = wb[sheet].iter_rows(values_only=True)
    header = next(rows, None) or ()
    columns = [str(h).strip() if h is not None else "" for h in header]
    missing = [c for c in required if c not in columns]
    if missing:
        errors.append(f"sheet {sheet!r} is missing column(s): {', '.join(missing)}")
        return []
    duplicated = [c for c, n in Counter(c for c in columns if c).items() if n > 1]
    if duplicated:
        errors.append(f"sheet {sheet!r} has duplicate column(s): {', '.join(duplicated)}")
        return []
    out = []
    for offset, values in enumerate(rows, start=2):
        if values is None or all(v is None or (isinstance(v, str) and not v.strip()) for v in values):
            continue
        out.append((offset, {c: (values[i] if i < len(values) else None) for i, c in enumerate(columns) if c}))
    return out


def _text(value: Any, where: str, column: str, max_len: int, errors: list[str]) -> str | None:
    """A required text cell, kept exactly as written; whitespace padding is an error, not trimmed."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{where}: {column!r} is required")
        return None
    if not isinstance(value, str):
        errors.append(f"{where}: {column!r} must be text, got {type(value).__name__} {value!r}")
        return None
    if value != value.strip():
        errors.append(f"{where}: {column!r} has leading/trailing whitespace: {value!r}")
        return None
    if len(value) > max_len:
        errors.append(f"{where}: {column!r} exceeds {max_len} characters")
        return None
    return value


def read_workbook(
    path: Path,
    *,
    expected_sha256: str,
    approved_department_codes: frozenset[str],
    expected_item_count: int,
) -> SourceData:
    """Fingerprint and validate the workbook. Raises SourceInvalid listing every problem found."""
    if not path.is_file():
        raise SourceInvalid([f"workbook not found: {path}"])
    actual_sha = sha256_of(path)
    if actual_sha != expected_sha256:
        raise SourceInvalid([f"workbook SHA256 {actual_sha} does not match approved {expected_sha256}"])

    errors: list[str] = []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        dept_rows = _sheet_rows(wb, "Departments", ("Code", "Department"), errors)
        uom_rows = _sheet_rows(wb, "UOM", ("UOM", "Meaning"), errors)
        cat_rows = _sheet_rows(wb, "Categories", ("Department", "Category", "Item Count"), errors)
        item_rows = _sheet_rows(
            wb,
            "Item Master",
            ("Item Code", "Item Description", "Item Category", "Department", "UOM", "Status"),
            errors,
        )
    finally:
        wb.close()
    if errors:
        raise SourceInvalid(errors)

    # Departments
    departments: list[DepartmentRow] = []
    dept_code_by_name: dict[str, str] = {}
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for row_no, row in dept_rows:
        where = f"Departments row {row_no}"
        code = _text(row["Code"], where, "Code", 20, errors)
        name = _text(row["Department"], where, "Department", 100, errors)
        if code is None or name is None:
            continue
        if code.casefold() in seen_codes:
            errors.append(f"{where}: duplicate department code {code!r}")
            continue
        if name.casefold() in seen_names:
            errors.append(f"{where}: duplicate department name {name!r}")
            continue
        seen_codes.add(code.casefold())
        seen_names.add(name.casefold())
        departments.append(DepartmentRow(code, name))
        dept_code_by_name[name] = code
    codes = {d.code for d in departments}
    if codes != approved_department_codes:
        missing = sorted(approved_department_codes - codes)
        extra = sorted(codes - approved_department_codes)
        errors.append(f"department codes differ from the approved set (missing {missing}, unexpected {extra})")

    # UOMs
    uoms: list[UomRow] = []
    uom_by_source: dict[str, str] = {}
    for row_no, row in uom_rows:
        where = f"UOM row {row_no}"
        source_code = _text(row["UOM"], where, "UOM", 20, errors)
        name = _text(row["Meaning"], where, "Meaning", 100, errors)
        if source_code is None or name is None:
            continue
        code = source_code.upper()
        if any(u.code == code for u in uoms):
            errors.append(f"{where}: duplicate UOM {source_code!r} (canonical {code!r})")
            continue
        if code not in UOM_PRECISION:
            errors.append(f"{where}: no approved decimal precision for UOM {code!r}")
            continue
        uoms.append(UomRow(code, source_code, name, UOM_PRECISION[code]))
        uom_by_source[source_code] = code

    # Categories: (department name, category) -> declared item count
    declared_counts: dict[tuple[str, str], int] = {}
    for row_no, row in cat_rows:
        where = f"Categories row {row_no}"
        dept = _text(row["Department"], where, "Department", 100, errors)
        cat = _text(row["Category"], where, "Category", 50, errors)
        count = row["Item Count"]
        if dept is None or cat is None:
            continue
        if dept not in dept_code_by_name:
            errors.append(f"{where}: unknown department {dept!r}")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"{where}: 'Item Count' must be a non-negative integer, got {count!r}")
            continue
        if (dept, cat) in declared_counts:
            errors.append(f"{where}: duplicate category {cat!r} for {dept!r}")
            continue
        declared_counts[(dept, cat)] = count

    # Items
    items: list[ItemRow] = []
    seen_item_codes: dict[str, int] = {}
    actual_counts: Counter[tuple[str, str]] = Counter()
    for row_no, row in item_rows:
        where = f"Item Master row {row_no}"
        code = _text(row["Item Code"], where, "Item Code", 50, errors)
        name = _text(row["Item Description"], where, "Item Description", 255, errors)
        category = _text(row["Item Category"], where, "Item Category", 50, errors)
        dept_name = _text(row["Department"], where, "Department", 100, errors)
        uom_source = _text(row["UOM"], where, "UOM", 20, errors)
        status = _text(row["Status"], where, "Status", 20, errors)
        if None in (code, name, category, dept_name, uom_source, status):
            continue
        ok = True
        if not ITEM_CODE_PATTERN.match(code):
            errors.append(f"{where}: item code {code!r} does not match the approved format")
            ok = False
        if code.casefold() in seen_item_codes:
            errors.append(f"{where}: duplicate item code {code!r} (first seen on row {seen_item_codes[code.casefold()]})")
            ok = False
        else:
            seen_item_codes[code.casefold()] = row_no
        dept_code = dept_code_by_name.get(dept_name)
        if dept_code is None:
            errors.append(f"{where}: unknown department {dept_name!r}")
            ok = False
        elif code.split("-")[0] != dept_code:
            errors.append(f"{where}: item code {code!r} does not start with its department code {dept_code!r}")
            ok = False
        uom_code = uom_by_source.get(uom_source)
        if uom_code is None:
            errors.append(f"{where}: unknown UOM {uom_source!r}")
            ok = False
        if (dept_name, category) not in declared_counts:
            errors.append(f"{where}: category {category!r} is not declared for {dept_name!r} in Categories")
            ok = False
        if status != "Active":
            errors.append(f"{where}: status {status!r} is not 'Active'; inactive items are not loaded")
            ok = False
        if ok:
            items.append(ItemRow(row_no, code, name, category, dept_code, uom_code))
            actual_counts[(dept_name, category)] += 1

    if not errors:
        for key, declared in sorted(declared_counts.items()):
            if actual_counts[key] != declared:
                errors.append(f"Categories: {key[1]!r} ({key[0]}) declares {declared} items, Item Master has {actual_counts[key]}")
        if len(items) != expected_item_count:
            errors.append(f"Item Master has {len(items)} valid items, expected {expected_item_count}")
    if errors:
        raise SourceInvalid(errors)
    return SourceData(actual_sha, departments, uoms, items)


# --------------------------------------------------------------------------------------------------
# 3. Planning against the database (read-only queries)
# --------------------------------------------------------------------------------------------------
@dataclass
class TablePlan:
    table: str
    inserts: list[dict] = field(default_factory=list)
    matches: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unrelated_existing: int = 0


@dataclass
class Plan:
    departments: TablePlan
    uoms: TablePlan
    items: TablePlan

    @property
    def tables(self) -> tuple[TablePlan, ...]:
        return (self.departments, self.uoms, self.items)

    @property
    def has_conflicts(self) -> bool:
        return any(t.conflicts for t in self.tables)

    @property
    def insert_count(self) -> int:
        return sum(len(t.inserts) for t in self.tables)


def _differences(existing: dict, expected: dict) -> list[str]:
    return [f"{k}: database={existing[k]!r} workbook={v!r}" for k, v in expected.items() if existing[k] != v]


def build_plan(conn: Connection, source: SourceData) -> Plan:
    # Departments: unique code and unique name.
    dept_plan = TablePlan("departments")
    existing = [dict(r._mapping) for r in conn.execute(select(DEPARTMENTS.c.code, DEPARTMENTS.c.name, DEPARTMENTS.c.is_active))]
    by_code = {r["code"]: r for r in existing}
    by_code_ci = {r["code"].casefold(): r for r in existing}
    by_name_ci = {r["name"].casefold(): r for r in existing}
    for d in source.departments:
        expected = {"name": d.name, "is_active": True}
        if d.code in by_code:
            diffs = _differences(by_code[d.code], expected)
            (dept_plan.conflicts if diffs else dept_plan.matches).append(
                f"{d.code}: " + ("; ".join(diffs) if diffs else d.name)
            )
        elif d.code.casefold() in by_code_ci:
            dept_plan.conflicts.append(f"{d.code}: existing code {by_code_ci[d.code.casefold()]['code']!r} differs only in case")
        elif d.name.casefold() in by_name_ci:
            dept_plan.conflicts.append(f"{d.code}: name {d.name!r} already belongs to department {by_name_ci[d.name.casefold()]['code']!r}")
        else:
            dept_plan.inserts.append({"code": d.code, "name": d.name, "is_active": True})
    dept_plan.unrelated_existing = len({r["code"] for r in existing} - {d.code for d in source.departments})

    # UOMs: unique code.
    uom_plan = TablePlan("uoms")
    existing = [dict(r._mapping) for r in conn.execute(select(UOMS.c.code, UOMS.c.name, UOMS.c.decimal_precision, UOMS.c.is_active))]
    by_code = {r["code"]: r for r in existing}
    by_code_ci = {r["code"].casefold(): r for r in existing}
    for u in source.uoms:
        expected = {"name": u.name, "decimal_precision": u.decimal_precision, "is_active": True}
        if u.code in by_code:
            diffs = _differences(by_code[u.code], expected)
            (uom_plan.conflicts if diffs else uom_plan.matches).append(f"{u.code}: " + ("; ".join(diffs) if diffs else u.name))
        elif u.code.casefold() in by_code_ci:
            uom_plan.conflicts.append(f"{u.code}: existing code {by_code_ci[u.code.casefold()]['code']!r} differs only in case")
        else:
            uom_plan.inserts.append({"code": u.code, "name": u.name, "decimal_precision": u.decimal_precision, "is_active": True})
    uom_plan.unrelated_existing = len({r["code"] for r in existing} - {u.code for u in source.uoms})

    # Items: unique item_code; department and UOM compared by code.
    item_plan = TablePlan("material_items")
    stmt = (
        select(
            ITEMS.c.item_code,
            ITEMS.c.name,
            ITEMS.c.category,
            ITEMS.c.subcategory,
            ITEMS.c.description,
            ITEMS.c.is_active,
            DEPARTMENTS.c.code.label("department_code"),
            UOMS.c.code.label("uom_code"),
        )
        .join(DEPARTMENTS, DEPARTMENTS.c.id == ITEMS.c.department_id)
        .join(UOMS, UOMS.c.id == ITEMS.c.base_uom_id)
    )
    existing = [dict(r._mapping) for r in conn.execute(stmt)]
    total_items = conn.execute(select(func.count()).select_from(ITEMS)).scalar_one()
    if total_items != len(existing):
        item_plan.conflicts.append(f"{total_items - len(existing)} existing item(s) reference a missing department or UOM")
    by_code = {r["item_code"]: r for r in existing}
    by_code_ci = {r["item_code"].casefold(): r for r in existing}
    for it in source.items:
        expected = {
            "name": it.name,
            "category": it.category,
            "subcategory": None,
            "description": None,
            "is_active": True,
            "department_code": it.department_code,
            "uom_code": it.uom_code,
        }
        label = f"{it.item_code} (row {it.row_number})"
        if it.item_code in by_code:
            diffs = _differences(by_code[it.item_code], expected)
            (item_plan.conflicts if diffs else item_plan.matches).append(f"{label}: " + ("; ".join(diffs) if diffs else it.name))
        elif it.item_code.casefold() in by_code_ci:
            item_plan.conflicts.append(f"{label}: existing code {by_code_ci[it.item_code.casefold()]['item_code']!r} differs only in case")
        else:
            item_plan.inserts.append(
                {
                    "item_code": it.item_code,
                    "name": it.name,
                    "category": it.category,
                    "department_code": it.department_code,
                    "uom_code": it.uom_code,
                }
            )
    item_plan.unrelated_existing = len({r["item_code"] for r in existing} - {i.item_code for i in source.items})
    return Plan(dept_plan, uom_plan, item_plan)


def count_protected(conn: Connection) -> dict[str, int]:
    """Row counts of every table the loader must not change (names come from model metadata only)."""
    return {name: conn.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one() for name in PROTECTED_TABLES}


# --------------------------------------------------------------------------------------------------
# 4. Applying the plan (commit mode only)
# --------------------------------------------------------------------------------------------------
def _insert_departments(conn: Connection, rows: list[dict], now: datetime) -> None:
    if rows:
        conn.execute(insert(DEPARTMENTS), [r | {"created_at": now, "updated_at": now} for r in rows])


def _insert_uoms(conn: Connection, rows: list[dict], now: datetime) -> None:
    if rows:
        conn.execute(insert(UOMS), [r | {"created_at": now, "updated_at": now} for r in rows])


def _insert_items(conn: Connection, rows: list[dict], now: datetime) -> None:
    if not rows:
        return
    dept_ids = dict(conn.execute(select(DEPARTMENTS.c.code, DEPARTMENTS.c.id)).all())
    uom_ids = dict(conn.execute(select(UOMS.c.code, UOMS.c.id)).all())
    conn.execute(
        insert(ITEMS),
        [
            {
                "item_code": r["item_code"],
                "name": r["name"],
                "category": r["category"],
                "subcategory": None,
                "description": None,
                "department_id": dept_ids[r["department_code"]],
                "base_uom_id": uom_ids[r["uom_code"]],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for r in rows
        ],
    )


def apply_plan(conn: Connection, plan: Plan) -> None:
    now = datetime.now(timezone.utc)
    _insert_departments(conn, plan.departments.inserts, now)
    _insert_uoms(conn, plan.uoms.inserts, now)
    _insert_items(conn, plan.items.inserts, now)


def verify_applied(conn: Connection, source: SourceData, protected_before: dict[str, int]) -> None:
    """Inside the open transaction: every source row now matches exactly and nothing else changed."""
    replan = build_plan(conn, source)
    if replan.insert_count or replan.has_conflicts:
        raise VerificationFailed(
            f"post-insert check found {replan.insert_count} missing and "
            f"{sum(len(t.conflicts) for t in replan.tables)} conflicting row(s)"
        )
    after = count_protected(conn)
    changed = {t: (protected_before[t], after[t]) for t in PROTECTED_TABLES if protected_before[t] != after[t]}
    if changed:
        raise VerificationFailed(f"protected table row counts changed: {changed}")


# --------------------------------------------------------------------------------------------------
# 5. Server-side guards
# --------------------------------------------------------------------------------------------------
class Guards(Protocol):
    def begin_read_only(self, conn: Connection) -> None: ...
    def verify_server(self, conn: Connection, target: Target) -> None: ...
    def lock_for_write(self, conn: Connection) -> None: ...


class PostgresGuards:
    """Checks that only make sense against the real PostgreSQL target."""

    def begin_read_only(self, conn: Connection) -> None:
        conn.execute(text("SET TRANSACTION READ ONLY"))

    def verify_server(self, conn: Connection, target: Target) -> None:
        if conn.dialect.name != "postgresql":
            raise TargetRejected([f"connected dialect is {conn.dialect.name!r}, expected 'postgresql'"])
        database = conn.execute(text("SELECT current_database()")).scalar_one()
        if database != target.database:
            raise TargetRejected([f"server reports database {database!r}, expected {target.database!r}"])
        versions = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if versions != [APPROVED_ALEMBIC_REVISION]:
            raise TargetRejected([f"alembic revision is {versions!r}, expected [{APPROVED_ALEMBIC_REVISION!r}]"])
        missing = [
            name
            for name in TARGET_TABLES + PROTECTED_TABLES
            if conn.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{name}"}).scalar_one() is None
        ]
        if missing:
            raise TargetRejected([f"expected tables are missing: {missing}"])
        # A user trigger on a target table could write elsewhere; refuse rather than reason about it.
        triggers = conn.execute(
            text(
                "SELECT c.relname || '.' || t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "WHERE NOT t.tgisinternal AND c.relnamespace = 'public'::regnamespace AND c.relname = ANY(:tables)"
            ),
            {"tables": list(TARGET_TABLES)},
        ).scalars().all()
        if triggers:
            raise TargetRejected([f"user triggers exist on target tables: {triggers}"])

    def lock_for_write(self, conn: Connection) -> None:
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        conn.execute(text("LOCK TABLE departments, uoms, material_items IN SHARE ROW EXCLUSIVE MODE"))


# --------------------------------------------------------------------------------------------------
# 6. Orchestration
# --------------------------------------------------------------------------------------------------
def load_settings() -> Any:
    from app.core.config import Settings

    return Settings(_env_file=BACKEND_DIR / ".env")


def default_engine_factory(settings: Any) -> Engine:
    verify_target(settings)  # re-checked immediately before the engine is built
    return create_engine(settings.sync_database_url, poolclass=NullPool, connect_args={"connect_timeout": 5})


def print_plan(plan: Plan, out: Callable[[str], None]) -> None:
    for t in plan.tables:
        out(f"\n[{t.table}] insert={len(t.inserts)} existing_exact_match={len(t.matches)} conflicts={len(t.conflicts)}"
            f" existing_not_in_workbook={t.unrelated_existing}")
        for row in t.inserts:
            out("  INSERT   " + " | ".join(str(v) for v in row.values()))
        for line in t.matches:
            out("  MATCH    " + line)
        for line in t.conflicts:
            out("  CONFLICT " + line)


def _safe_error(exc: BaseException) -> str:
    """Error summary without driver messages, which can echo connection details."""
    if isinstance(exc, SQLAlchemyError):
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        return f"{type(exc).__name__}" + (f" (SQLSTATE {sqlstate})" if sqlstate else "")
    return f"{type(exc).__name__}: {exc}"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK, help="approved Item Master workbook")
    parser.add_argument("--commit", action="store_true", help="insert missing rows (default is a read-only dry run)")
    return parser.parse_args(argv)


def run(
    argv: list[str] | None = None,
    *,
    settings: Any = None,
    engine_factory: Callable[[Any], Engine] = default_engine_factory,
    guards: Guards | None = None,
    expected_sha256: str = APPROVED_WORKBOOK_SHA256,
    expected_item_count: int = APPROVED_ITEM_COUNT,
    environ: Mapping[str, str] | None = None,
    out: Callable[[str], None] = print,
) -> int:
    args = parse_args(argv)
    mode = "COMMIT" if args.commit else "DRY RUN"
    out(f"VSPL reference-data loader - {mode}")

    settings = settings if settings is not None else load_settings()
    try:
        target = verify_target(settings, environ)
    except TargetRejected as exc:
        out("Target rejected before connecting:")
        for problem in exc.problems:
            out(f"  - {problem}")
        return EXIT_TARGET_REJECTED
    out(f"Target: {target.describe()} (ENVIRONMENT={settings.ENVIRONMENT})")

    try:
        source = read_workbook(
            args.workbook,
            expected_sha256=expected_sha256,
            approved_department_codes=APPROVED_DEPARTMENT_CODES,
            expected_item_count=expected_item_count,
        )
    except SourceInvalid as exc:
        out(f"Source workbook rejected ({len(exc.errors)} problem(s)):")
        for error in exc.errors:
            out(f"  - {error}")
        return EXIT_SOURCE_INVALID
    out(
        f"Source: {args.workbook} sha256={source.sha256} "
        f"departments={len(source.departments)} uoms={len(source.uoms)} items={len(source.items)}"
    )

    guards = guards if guards is not None else PostgresGuards()
    engine = engine_factory(settings)
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                if not args.commit:
                    guards.begin_read_only(conn)
                guards.verify_server(conn, target)
                if args.commit:
                    guards.lock_for_write(conn)
                before = count_protected(conn)
                plan = build_plan(conn, source)
                print_plan(plan, out)

                if plan.has_conflicts:
                    trans.rollback()
                    out("\nAborted: existing rows conflict with the workbook. Nothing was written.")
                    return EXIT_CONFLICTS
                if not args.commit:
                    trans.rollback()
                    out(f"\nWould insert {plan.insert_count} row(s). {DRY_RUN_DISCLAIMER}")
                    return EXIT_OK

                apply_plan(conn, plan)
                verify_applied(conn, source, before)
                trans.commit()
            except BaseException:
                if trans.is_active:
                    trans.rollback()
                raise

        with engine.connect() as conn:
            after = count_protected(conn)
        changed = {t: (before[t], after[t]) for t in PROTECTED_TABLES if before[t] != after[t]}
        out(f"\nCommitted {plan.insert_count} row(s). Protected tables unchanged: {not changed}")
        if changed:
            out(f"WARNING: protected table counts changed after commit (concurrent activity?): {changed}")
            return EXIT_VERIFICATION_FAILED
        return EXIT_OK
    except TargetRejected as exc:
        out("Target rejected by server checks; transaction rolled back:")
        for problem in exc.problems:
            out(f"  - {problem}")
        return EXIT_TARGET_REJECTED
    except VerificationFailed as exc:
        out(f"Verification failed; transaction rolled back: {exc}")
        return EXIT_VERIFICATION_FAILED
    except Exception as exc:  # noqa: BLE001 - report safely, never echo driver detail
        out(f"Aborted; transaction rolled back: {_safe_error(exc)}")
        return EXIT_ABORTED
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(run())
