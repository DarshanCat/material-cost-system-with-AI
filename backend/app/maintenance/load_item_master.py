"""Load the validated item master plan (departments, units, items, item-code registry and audit rows) in ONE transaction.

    python -m app.maintenance.load_item_master            # dry run: everything is done, then rolled back
    python -m app.maintenance.load_item_master --commit   # write

The plan (``data/item_master_plan.json``) was built from the item master workbook with the agreed rules and checked
before being shipped. Insert-only by natural key (department code, UOM code, item code): a row that already exists with
the same values is left alone, one that differs aborts the whole run. Nothing is updated or deleted. Every new item also
gets its permanent code-registry row and a REGISTERED audit row, in the same transaction. Only row counts and codes are
printed, never connection details.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  registers every table
from app.models.department import Department
from app.models.item import MaterialItem
from app.models.item_code import ItemCodeRegistry, ItemMasterAction, ItemMasterAuditLog
from app.models.uom import UOM
from app.services import item_nomenclature as nom

PLAN_PATH = Path(__file__).parent / "data" / "item_master_plan.json"
ACTOR = "item-master-import"
ACTOR_ROLE = "System"


class LoadAborted(Exception):
    pass


def load_plan(path: Path = PLAN_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_plan(db: Session, plan: dict[str, Any]) -> dict[str, int]:
    """Insert what is missing. Raises LoadAborted on any conflict. The caller commits or rolls back."""
    now = datetime.now(timezone.utc)
    counts = {k: 0 for k in ("departments_new", "departments_existing", "uoms_new", "uoms_existing",
                              "items_new", "items_existing", "registry_new", "audit_new")}
    conflicts: list[str] = []

    depts = {d.code: d for d in db.execute(select(Department)).scalars()}
    for d in plan["departments"]:
        cur = depts.get(d["code"])
        if cur is None:
            row = Department(code=d["code"], name=d["name"], is_active=True)
            db.add(row)
            depts[d["code"]] = row
            counts["departments_new"] += 1
        elif cur.name != d["name"]:
            conflicts.append(f"department {d['code']}: database has {cur.name!r}, plan has {d['name']!r}")
        else:
            counts["departments_existing"] += 1

    uoms = {u.code: u for u in db.execute(select(UOM)).scalars()}
    for u in plan["uoms"]:
        cur = uoms.get(u["code"])
        if cur is None:
            row = UOM(code=u["code"], name=u["name"], decimal_precision=u["decimal_precision"], is_active=True)
            db.add(row)
            uoms[u["code"]] = row
            counts["uoms_new"] += 1
        elif cur.name != u["name"] or cur.decimal_precision != u["decimal_precision"]:
            conflicts.append(f"UOM {u['code']}: database differs from the plan")
        else:
            counts["uoms_existing"] += 1
    if conflicts:
        raise LoadAborted("; ".join(conflicts))
    db.flush()

    existing = {i.item_code: i for i in db.execute(select(MaterialItem)).scalars()}
    # Inspect through the session's own connection (a separate connection could not see our uncommitted work).
    columns = {c["name"] for c in inspect(db.connection()).get_columns("material_items")}
    has_cost_head = "cost_head" in columns
    has_recon = "reconciliation_category" in columns
    reason = f"Initial load from {plan['source']['file']} (sha256 {plan['source']['sha256'][:12]})"

    for it in plan["items"]:
        code = it["item_code"]
        parsed = nom.parse_item_code(code)
        if parsed is None:
            conflicts.append(f"{code}: not in the standard format")
            continue
        dept_code, cat_code, serial = parsed
        cur = existing.get(code)
        if cur is not None:
            same = (
                cur.name == it["name"] and cur.category == it["category"]
                and cur.department_id == depts[it["department_code"]].id and cur.base_uom_id == uoms[it["uom_code"]].id
            )
            if same:
                counts["items_existing"] += 1
            else:
                conflicts.append(f"{code}: the database already has this code with different values")
            continue
        item = MaterialItem(
            item_code=code, name=it["name"], department_id=depts[it["department_code"]].id, category=it["category"],
            subcategory=None, base_uom_id=uoms[it["uom_code"]].id, description=it["description"], is_active=it["is_active"],
        )
        db.add(item)
        db.flush()
        db.add(ItemCodeRegistry(
            item_code=code, department_code=dept_code, category_code=cat_code, serial=serial, material_item_id=item.id,
            item_request_id=None, standard_version=nom.STANDARD_VERSION, issued_by=ACTOR, issued_at=now,
        ))
        db.add(ItemMasterAuditLog(
            material_item_id=item.id, item_code=code, action=ItemMasterAction.REGISTERED, field_name=None, old_value=None,
            new_value=it["name"], reason=reason, item_request_id=None, actor_id=ACTOR, actor_role=ACTOR_ROLE, timestamp=now,
        ))
        sets, params = [], {"id": item.id}
        if has_cost_head and (head := nom.cost_head_for_category(cat_code)) is not None:
            sets.append("cost_head = :ch")
            params["ch"] = head
        if has_recon:
            sets.append("reconciliation_category = :rc")
            params["rc"] = nom.resolve_effective_reconciliation_category(code, it["category"])
        if sets:
            db.execute(text(f"UPDATE material_items SET {', '.join(sets)} WHERE id = :id"), params)
        counts["items_new"] += 1
        counts["registry_new"] += 1
        counts["audit_new"] += 1
    if conflicts:
        raise LoadAborted("; ".join(conflicts[:20]) + (f" (+{len(conflicts) - 20} more)" if len(conflicts) > 20 else ""))
    db.flush()

    # Verify inside the transaction: every planned item is present with its registry and audit row.
    planned = {i["item_code"] for i in plan["items"]}
    present = set(db.execute(select(MaterialItem.item_code).where(MaterialItem.item_code.in_(planned))).scalars())
    registered = set(db.execute(select(ItemCodeRegistry.item_code).where(ItemCodeRegistry.item_code.in_(planned))).scalars())
    if present != planned or registered != planned:
        raise LoadAborted(f"verification failed: {len(planned - present)} item(s) and {len(planned - registered)} registry row(s) missing")
    return counts


def run(db: Session, plan: dict[str, Any], *, commit: bool, out=print) -> int:
    before = {t: db.execute(select(func.count()).select_from(m)).scalar_one()
              for t, m in (("departments", Department), ("uoms", UOM), ("material_items", MaterialItem),
                           ("item_code_registry", ItemCodeRegistry), ("item_master_audit_logs", ItemMasterAuditLog))}
    try:
        counts = apply_plan(db, plan)
    except LoadAborted as exc:
        db.rollback()
        out(f"ABORTED, nothing written: {exc}")
        return 6
    out("Plan result: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    out("Rows before: " + ", ".join(f"{k}={v}" for k, v in before.items()))
    if commit:
        db.commit()
        out("COMMITTED.")
    else:
        db.rollback()
        out("DRY RUN: everything was applied and checked, then rolled back. Nothing was written.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="write the changes (default is a dry run)")
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        sys.exit(run(db, load_plan(), commit=args.commit))


if __name__ == "__main__":
    main()
