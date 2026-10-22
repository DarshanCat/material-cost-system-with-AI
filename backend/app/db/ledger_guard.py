"""
Append-only protection for `stock_ledger_entries`.

Three independent layers (defence in depth):

1. ORM guard (this module): SQLAlchemy mapper events reject UPDATE/DELETE of a posted StockLedgerEntry
   through the unit of work, and a session-level `do_orm_execute` hook rejects bulk ORM
   `update()` / `delete()` statements that target the ledger. Application code therefore cannot modify
   posted rows; corrections must be new, separately authorised compensating entries.
2. SQLite triggers (installed on `create_all`, i.e. the test database): any UPDATE/DELETE, including raw
   SQL, aborts. This keeps the guard testable without PostgreSQL. SQLite is NOT proof of PostgreSQL behaviour.
3. PostgreSQL triggers (Alembic revision 006, SQL below): BEFORE UPDATE/DELETE row triggers and a
   BEFORE TRUNCATE statement trigger raise an exception. These have NOT been executed against a real
   PostgreSQL server yet (no instance exists; gate G12). A DBA should additionally REVOKE UPDATE,
   DELETE, TRUNCATE on the table from the application role and keep ownership with a separate role,
   because a table owner/superuser can still drop triggers.

Historical rows are never touched: triggers only act on future UPDATE/DELETE/TRUNCATE statements.
"""

from sqlalchemy import DDL, event
from sqlalchemy.orm import Session

from app.models.ledger import StockLedgerEntry

LEDGER_TABLE = "stock_ledger_entries"
IMMUTABLE_MESSAGE = "stock_ledger_entries is append-only: UPDATE, DELETE and TRUNCATE are not permitted"


class LedgerImmutableError(Exception):
    """Raised when code attempts to modify or delete a posted stock ledger entry."""


# ----------------------------------------------------------------------------------------------
# 1. ORM guard
# ----------------------------------------------------------------------------------------------

def _reject_mutation(mapper, connection, target):  # noqa: ARG001
    raise LedgerImmutableError(f"{IMMUTABLE_MESSAGE} (entry {getattr(target, 'entry_number', target)}).")


def _reject_bulk(orm_execute_state):
    if (orm_execute_state.is_update or orm_execute_state.is_delete) and any(
        m.class_ is StockLedgerEntry for m in orm_execute_state.all_mappers
    ):
        raise LedgerImmutableError(f"{IMMUTABLE_MESSAGE} (bulk statement).")


# ----------------------------------------------------------------------------------------------
# 2. SQLite triggers (create_all path only)
# ----------------------------------------------------------------------------------------------

SQLITE_TRIGGER_DDL = [
    DDL(
        f"CREATE TRIGGER IF NOT EXISTS trg_{LEDGER_TABLE}_no_update BEFORE UPDATE ON {LEDGER_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{IMMUTABLE_MESSAGE}'); END"
    ),
    DDL(
        f"CREATE TRIGGER IF NOT EXISTS trg_{LEDGER_TABLE}_no_delete BEFORE DELETE ON {LEDGER_TABLE} "
        f"BEGIN SELECT RAISE(ABORT, '{IMMUTABLE_MESSAGE}'); END"
    ),
]

# ----------------------------------------------------------------------------------------------
# 3. PostgreSQL SQL, executed by Alembic revision 006 (not by create_all)
# ----------------------------------------------------------------------------------------------

PG_FUNCTION_NAME = "stock_ledger_entries_append_only"
PG_UPGRADE_SQL = [
    f"""
    CREATE OR REPLACE FUNCTION {PG_FUNCTION_NAME}() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION '{IMMUTABLE_MESSAGE} (attempted: %)', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
    f"""
    CREATE TRIGGER trg_{LEDGER_TABLE}_no_update_delete
    BEFORE UPDATE OR DELETE ON {LEDGER_TABLE}
    FOR EACH ROW EXECUTE FUNCTION {PG_FUNCTION_NAME}()
    """,
    f"""
    CREATE TRIGGER trg_{LEDGER_TABLE}_no_truncate
    BEFORE TRUNCATE ON {LEDGER_TABLE}
    FOR EACH STATEMENT EXECUTE FUNCTION {PG_FUNCTION_NAME}()
    """,
]
PG_DOWNGRADE_SQL = [
    f"DROP TRIGGER IF EXISTS trg_{LEDGER_TABLE}_no_truncate ON {LEDGER_TABLE}",
    f"DROP TRIGGER IF EXISTS trg_{LEDGER_TABLE}_no_update_delete ON {LEDGER_TABLE}",
    f"DROP FUNCTION IF EXISTS {PG_FUNCTION_NAME}()",
]


def install_ledger_guard() -> None:
    """Register the ORM guard and SQLite triggers (idempotent; called once from app.models)."""
    if getattr(install_ledger_guard, "_done", False):
        return
    event.listen(StockLedgerEntry, "before_update", _reject_mutation)
    event.listen(StockLedgerEntry, "before_delete", _reject_mutation)
    event.listen(Session, "do_orm_execute", _reject_bulk)
    for ddl in SQLITE_TRIGGER_DDL:
        event.listen(StockLedgerEntry.__table__, "after_create", ddl.execute_if(dialect="sqlite"))
    install_ledger_guard._done = True
