"""item code generator: allocation sequences, permanent code registry, item master audit history

Revision ID: 008_item_code_registry
Revises: 007_opening_val_versioning
Create Date: 2026-10-26 10:00:00.000000

Adds three NEW tables only. No existing table, column, constraint or row is modified, and no data is
inserted or backfilled:

- item_code_sequences      (department_code, category_code) -> highest serial allocated by the generator.
                           Rows are created lazily at the first allocation for a pair; the starting point is
                           max(serials already present in material_items and item_code_registry), so no
                           backfill is required and existing codes are never reissued.
- item_code_registry       every code issued by the generator. Append-only.
- item_master_audit_logs   registration / retirement / reactivation / approved correction history. Append-only.

PostgreSQL triggers make the two history tables append-only (BEFORE UPDATE/DELETE row triggers and a
BEFORE TRUNCATE statement trigger). The SQL is frozen inline on purpose; tests/test_item_nomenclature.py
asserts it matches app.db.item_code_guard.

NOT YET EXECUTED against any database. Deployment dependency: the backend version that introduces the
item code generator requires this revision; apply it before deploying that backend. Note that
scripts/load_reference_master.py only accepts revision 007_opening_val_versioning, so run (or re-review)
that loader before applying this revision. Complementary DBA step (outside Alembic): REVOKE UPDATE,
DELETE, TRUNCATE on item_code_registry and item_master_audit_logs from the application role.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


PROTECTED_TABLES = ("item_code_registry", "item_master_audit_logs")


def _pg_upgrade_sql(table: str) -> list[str]:
    return [
        f"""
    CREATE OR REPLACE FUNCTION {table}_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION '{table} is append-only: UPDATE, DELETE and TRUNCATE are not permitted (attempted: %)', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """,
        f"""
    CREATE TRIGGER trg_{table}_no_update_delete
    BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION {table}_append_only()
    """,
        f"""
    CREATE TRIGGER trg_{table}_no_truncate
    BEFORE TRUNCATE ON {table}
    FOR EACH STATEMENT EXECUTE FUNCTION {table}_append_only()
    """,
    ]


def _pg_downgrade_sql(table: str) -> list[str]:
    return [
        f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON {table}",
        f"DROP TRIGGER IF EXISTS trg_{table}_no_update_delete ON {table}",
        f"DROP FUNCTION IF EXISTS {table}_append_only()",
    ]


# revision identifiers, used by Alembic.
revision: str = '008_item_code_registry'
down_revision: Union[str, None] = '007_opening_val_versioning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'item_code_sequences',
        sa.Column('department_code', sa.String(length=3), nullable=False),
        sa.Column('category_code', sa.String(length=2), nullable=False),
        sa.Column('last_serial', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('last_serial >= 0 AND last_serial <= 999', name=op.f('ck_item_code_sequences_last_serial_range')),
        sa.PrimaryKeyConstraint('department_code', 'category_code', name=op.f('pk_item_code_sequences')),
    )

    op.create_table(
        'item_code_registry',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_code', sa.String(length=50), nullable=False),
        sa.Column('department_code', sa.String(length=3), nullable=False),
        sa.Column('category_code', sa.String(length=2), nullable=False),
        sa.Column('serial', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('item_request_id', sa.Integer(), nullable=True),
        sa.Column('standard_version', sa.String(length=10), nullable=False),
        sa.Column('issued_by', sa.String(length=100), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('serial >= 1 AND serial <= 999', name=op.f('ck_item_code_registry_serial_range')),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_item_code_registry_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['item_request_id'], ['item_requests.id'], name=op.f('fk_item_code_registry_item_request_id_item_requests')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_item_code_registry')),
        sa.UniqueConstraint('material_item_id', name=op.f('uq_item_code_registry_material_item_id')),
    )
    op.create_index(op.f('ix_item_code_registry_item_code'), 'item_code_registry', ['item_code'], unique=True)

    op.create_table(
        'item_master_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('item_code', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=30), nullable=False),
        sa.Column('field_name', sa.String(length=50), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('item_request_id', sa.Integer(), nullable=True),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('actor_role', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_item_master_audit_logs_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['item_request_id'], ['item_requests.id'], name=op.f('fk_item_master_audit_logs_item_request_id_item_requests')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_item_master_audit_logs')),
    )
    op.create_index(op.f('ix_item_master_audit_logs_material_item_id'), 'item_master_audit_logs', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_item_master_audit_logs_item_code'), 'item_master_audit_logs', ['item_code'], unique=False)

    if op.get_bind().dialect.name == 'postgresql':
        for table in PROTECTED_TABLES:
            for statement in _pg_upgrade_sql(table):
                op.execute(statement)


def downgrade() -> None:
    # Downgrading destroys the permanent code registry and item history. Take a backup first; codes recorded
    # there must still never be reissued (the generator also derives its floor from material_items).
    if op.get_bind().dialect.name == 'postgresql':
        for table in PROTECTED_TABLES:
            for statement in _pg_downgrade_sql(table):
                op.execute(statement)
    op.drop_index(op.f('ix_item_master_audit_logs_item_code'), table_name='item_master_audit_logs')
    op.drop_index(op.f('ix_item_master_audit_logs_material_item_id'), table_name='item_master_audit_logs')
    op.drop_table('item_master_audit_logs')
    op.drop_index(op.f('ix_item_code_registry_item_code'), table_name='item_code_registry')
    op.drop_table('item_code_registry')
    op.drop_table('item_code_sequences')
