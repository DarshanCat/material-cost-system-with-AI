"""
Append-only protection for `item_code_registry` and `item_master_audit_logs`.

Same three layers as app/db/ledger_guard.py:

1. ORM guard: mapper events reject UPDATE/DELETE of these rows through the unit of work, and a
   session-level `do_orm_execute` hook rejects bulk ORM `update()` / `delete()` statements on them.
2. SQLite triggers (installed on `create_all`, i.e. the test database).
3. PostgreSQL triggers, executed by Alembic revision 008 (SQL below, frozen inline in the migration).
   NOT executed against any database by this change.

An issued item code is permanent: it is never edited, deleted or reused (Nomenclature Standard v1.0,
Section 2 "Golden rule").
"""

from sqlalchemy import DDL, event
from sqlalchemy.orm import Session

from app.models.item_code import ItemCodeRegistry, ItemMasterAuditLog

PROTECTED_MODELS = (ItemCodeRegistry, ItemMasterAuditLog)
PROTECTED_TABLES = tuple(model.__tablename__ for model in PROTECTED_MODELS)


class ItemHistoryImmutableError(Exception):
    """Raised when code attempts to modify or delete an issued item code or an item audit record."""


def _message(table: str) -> str:
    return f"{table} is append-only: UPDATE, DELETE and TRUNCATE are not permitted"


def _reject_mutation(mapper, connection, target):  # noqa: ARG001
    raise ItemHistoryImmutableError(_message(mapper.local_table.name))


def _reject_bulk(orm_execute_state):
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    for m in orm_execute_state.all_mappers:
        if m.class_ in PROTECTED_MODELS:
            raise ItemHistoryImmutableError(f"{_message(m.local_table.name)} (bulk statement).")


def sqlite_trigger_ddl(table: str) -> list[DDL]:
    return [
        DDL(
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{_message(table)}'); END"
        ),
        DDL(
            f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{_message(table)}'); END"
        ),
    ]


def pg_upgrade_sql(table: str) -> list[str]:
    function = f"{table}_append_only"
    return [
        f"""
    CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION '{_message(table)} (attempted: %)', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
        f"""
    CREATE TRIGGER trg_{table}_no_update_delete
    BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION {function}()
    """,
        f"""
    CREATE TRIGGER trg_{table}_no_truncate
    BEFORE TRUNCATE ON {table}
    FOR EACH STATEMENT EXECUTE FUNCTION {function}()
    """,
    ]


def pg_downgrade_sql(table: str) -> list[str]:
    return [
        f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON {table}",
        f"DROP TRIGGER IF EXISTS trg_{table}_no_update_delete ON {table}",
        f"DROP FUNCTION IF EXISTS {table}_append_only()",
    ]


def install_item_code_guard() -> None:
    """Register the ORM guard and SQLite triggers (idempotent; called once from app.models)."""
    if getattr(install_item_code_guard, "_done", False):
        return
    for model in PROTECTED_MODELS:
        event.listen(model, "before_update", _reject_mutation)
        event.listen(model, "before_delete", _reject_mutation)
        for ddl in sqlite_trigger_ddl(model.__tablename__):
            event.listen(model.__table__, "after_create", ddl.execute_if(dialect="sqlite"))
    event.listen(Session, "do_orm_execute", _reject_bulk)
    install_item_code_guard._done = True
