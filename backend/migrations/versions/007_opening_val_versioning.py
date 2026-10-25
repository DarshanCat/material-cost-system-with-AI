"""opening valuation versioning, maker-checker audit history

Revision ID: 007_opening_val_versioning
Revises: 006_sprint2_ledger_immutability
Create Date: 2026-10-24 21:00:00.000000

Adds versioning, proposal/approval lifecycle columns, and audit history table
to item_opening_valuations for SW-06.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_opening_val_versioning'
down_revision: Union[str, None] = '006_sprint2_ledger_immutability'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # Drop unique constraint and unique index on material_item_id
        op.drop_constraint('uq_item_opening_valuations_material_item_id', 'item_opening_valuations', type_='unique')
        op.drop_index('ix_opening_valuation_item', table_name='item_opening_valuations')

        # Add non-unique index on material_item_id
        op.create_index('ix_opening_valuation_item', 'item_opening_valuations', ['material_item_id'], unique=False)

        # Add versioning and lifecycle columns
        op.add_column('item_opening_valuations', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
        op.add_column('item_opening_valuations', sa.Column('created_by', sa.String(length=100), server_default='SYSTEM_MIGRATION', nullable=False))
        op.add_column('item_opening_valuations', sa.Column('rejection_reason', sa.Text(), nullable=True))
        op.add_column('item_opening_valuations', sa.Column('superseded_by_id', sa.Integer(), nullable=True))
        op.add_column('item_opening_valuations', sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True))

        op.create_foreign_key(
            'fk_opening_valuation_superseded_by',
            'item_opening_valuations', 'item_opening_valuations',
            ['superseded_by_id'], ['id']
        )
        op.create_unique_constraint(
            'uq_opening_valuation_item_version',
            'item_opening_valuations',
            ['material_item_id', 'version']
        )

        # Backfill created_by if approved_by is present on historical rows
        op.execute("UPDATE item_opening_valuations SET created_by = COALESCE(approved_by, 'SYSTEM_MIGRATION') WHERE created_by = 'SYSTEM_MIGRATION'")

        # Create audit logs table
        op.create_table(
            'item_opening_valuation_audit_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('valuation_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('from_status', sa.String(length=30), nullable=True),
            sa.Column('to_status', sa.String(length=30), nullable=False),
            sa.Column('actor_id', sa.String(length=100), nullable=False),
            sa.Column('comments', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['valuation_id'], ['item_opening_valuations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_item_opening_val_audit_valuation_id', 'item_opening_valuation_audit_logs', ['valuation_id'], unique=False)
    else:
        # SQLite / other dialects (batch mode)
        with op.batch_alter_table('item_opening_valuations') as batch_op:
            batch_op.add_column(sa.Column('version', sa.Integer(), server_default='1', nullable=False))
            batch_op.add_column(sa.Column('created_by', sa.String(length=100), server_default='SYSTEM_MIGRATION', nullable=False))
            batch_op.add_column(sa.Column('rejection_reason', sa.Text(), nullable=True))
            batch_op.add_column(sa.Column('superseded_by_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True))
            batch_op.create_foreign_key('fk_opening_valuation_superseded_by', 'item_opening_valuations', ['superseded_by_id'], ['id'])
            batch_op.create_unique_constraint('uq_opening_valuation_item_version', ['material_item_id', 'version'])

        op.create_table(
            'item_opening_valuation_audit_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('valuation_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('from_status', sa.String(length=30), nullable=True),
            sa.Column('to_status', sa.String(length=30), nullable=False),
            sa.Column('actor_id', sa.String(length=100), nullable=False),
            sa.Column('comments', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['valuation_id'], ['item_opening_valuations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_item_opening_val_audit_valuation_id', 'item_opening_valuation_audit_logs', ['valuation_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.drop_table('item_opening_valuation_audit_logs')
        op.drop_constraint('uq_opening_valuation_item_version', 'item_opening_valuations', type_='unique')
        op.drop_constraint('fk_opening_valuation_superseded_by', 'item_opening_valuations', type_='foreignkey')
        op.drop_column('item_opening_valuations', 'superseded_at')
        op.drop_column('item_opening_valuations', 'superseded_by_id')
        op.drop_column('item_opening_valuations', 'rejection_reason')
        op.drop_column('item_opening_valuations', 'created_by')
        op.drop_column('item_opening_valuations', 'version')
        op.drop_index('ix_opening_valuation_item', table_name='item_opening_valuations')
        op.create_unique_constraint('uq_item_opening_valuations_material_item_id', 'item_opening_valuations', ['material_item_id'])
        op.create_index('ix_opening_valuation_item', 'item_opening_valuations', ['material_item_id'], unique=True)
    else:
        op.drop_table('item_opening_valuation_audit_logs')
        with op.batch_alter_table('item_opening_valuations') as batch_op:
            batch_op.drop_constraint('uq_opening_valuation_item_version', type_='unique')
            batch_op.drop_constraint('fk_opening_valuation_superseded_by', type_='foreignkey')
            batch_op.drop_column('superseded_at')
            batch_op.drop_column('superseded_by_id')
            batch_op.drop_column('rejection_reason')
            batch_op.drop_column('created_by')
            batch_op.drop_column('version')
