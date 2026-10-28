# Proposed migrations (not applied)

Files here are **proposals awaiting explicit approval**. They sit outside Alembic's version location
(`migrations/versions`), so `alembic upgrade head` cannot apply them by accident.

| File | Purpose | Status |
|---|---|---|
| `009_material_item_cost_head.py` | Adds nullable `material_items.cost_head` with a CHECK of the ten v1.0 cost heads and a conservative backfill (only where code and category text both match v1.0). | Proposal only. Not approved, not executed. |

To adopt a proposal: review it, get approval, move it into `migrations/versions/`, run it on the isolated
non-production database first, and update the application code noted in its docstring.
