# Proposed migrations (not applied)

Files here are **proposals awaiting explicit approval**. They sit outside Alembic's version location
(`migrations/versions`), so `alembic upgrade head` cannot apply them by accident.

| File | Purpose | Status |
|---|---|---|
| `009_material_item_cost_head.py` | Adds nullable `material_items.cost_head` with a CHECK of the ten v1.0 cost heads and a conservative backfill (only where code and category text both match v1.0). | Proposal only. Not approved, not executed. |
| `010_material_item_reconciliation_category.py` | Adds nullable `material_items.reconciliation_category` with a CHECK constraint ('HEAT_TRACEABLE', 'NON_HEAT_SPECIFIC', 'REVIEW_REQUIRED') and backfills approved override for Slax (FDY-RM-021). | Proposal only. Not approved, not executed. |
| `011_stock_ledger_valuation.py` | Adds nullable `unit_cost_rate` (Numeric 15,4), `value_delta` (Numeric 15,2), and `valuation_method` (VARCHAR 30) to `stock_ledger_entries`. Resolves Observations 8 and 9. | Proposal only. Not approved, not executed. |
| `012_heat_liquid_heel.py` | Adds opening/closing liquid heel, measurement method, verification status, and carry-forward foreign key to `heat_headers`. Resolves Observations 10 and 11. | Proposal only. Not approved, not executed. |

To adopt a proposal: review it, get approval, move it into `migrations/versions/`, run it on the isolated
non-production database first, and update the application code noted in its docstring.
