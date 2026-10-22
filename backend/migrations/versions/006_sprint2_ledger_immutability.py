"""enforce append-only stock_ledger_entries with PostgreSQL triggers

Revision ID: 006_sprint2_ledger_immutability
Revises: 005_phase6_costing_valuation
Create Date: 2026-10-22 12:00:00.000000

Adds BEFORE UPDATE/DELETE (row) and BEFORE TRUNCATE (statement) triggers that raise an exception, so
posted ledger rows cannot be changed or removed by any client, including raw SQL from the application
role. No data and no existing revision is modified. PostgreSQL only; a no-op on other dialects.

NOT YET EXECUTED against any database. Apply only to the isolated non-production instance (port 5439)
after gate G12, then run the ledger tests there. Complementary DBA step (outside Alembic): REVOKE UPDATE,
DELETE, TRUNCATE ON stock_ledger_entries FROM the application role.
"""
from typing import Sequence, Union

from alembic import op


# SQL is inlined (frozen) on purpose: a migration must not change when application code changes.
# tests/test_ledger_immutability.py asserts it stays identical to app.db.ledger_guard.
PG_UPGRADE_SQL = [
    """
    CREATE OR REPLACE FUNCTION stock_ledger_entries_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'stock_ledger_entries is append-only: UPDATE, DELETE and TRUNCATE are not permitted (attempted: %)', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER trg_stock_ledger_entries_no_update_delete
    BEFORE UPDATE OR DELETE ON stock_ledger_entries
    FOR EACH ROW EXECUTE FUNCTION stock_ledger_entries_append_only()
    """,
    """
    CREATE TRIGGER trg_stock_ledger_entries_no_truncate
    BEFORE TRUNCATE ON stock_ledger_entries
    FOR EACH STATEMENT EXECUTE FUNCTION stock_ledger_entries_append_only()
    """,
]
PG_DOWNGRADE_SQL = [
    """DROP TRIGGER IF EXISTS trg_stock_ledger_entries_no_truncate ON stock_ledger_entries""",
    """DROP TRIGGER IF EXISTS trg_stock_ledger_entries_no_update_delete ON stock_ledger_entries""",
    """DROP FUNCTION IF EXISTS stock_ledger_entries_append_only()""",
]

# revision identifiers, used by Alembic.
revision: str = '006_sprint2_ledger_immutability'
down_revision: Union[str, None] = '005_phase6_costing_valuation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for statement in PG_UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for statement in PG_DOWNGRADE_SQL:
        op.execute(statement)
