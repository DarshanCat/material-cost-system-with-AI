"""create phase 4 stock ledger and physical audit tables

Revision ID: 003_phase4_stock_ledger
Revises: 002_phase3_material_entry
Create Date: 2026-10-10 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_phase4_stock_ledger'
down_revision: Union[str, None] = '002_phase3_material_entry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. stock_ledger_entries table
    op.create_table(
        'stock_ledger_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entry_number', sa.String(length=50), nullable=False),
        sa.Column('posting_group_id', sa.String(length=50), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('movement_type', sa.String(length=50), nullable=False),
        sa.Column('quantity_delta', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('source_document_type', sa.String(length=30), nullable=False),
        sa.Column('source_document_id', sa.Integer(), nullable=False),
        sa.Column('source_line_id', sa.Integer(), nullable=False),
        sa.Column('source_document_number', sa.String(length=50), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('posted_by', sa.String(length=100), nullable=False),
        sa.Column('reversal_of_entry_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_stock_ledger_entries_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], name=op.f('fk_stock_ledger_entries_uom_id_uoms')),
        sa.ForeignKeyConstraint(['reversal_of_entry_id'], ['stock_ledger_entries.id'], name=op.f('fk_stock_ledger_entries_reversal_of_entry_id_stock_ledger_entries')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_ledger_entries')),
        sa.UniqueConstraint('source_document_type', 'source_line_id', name='uq_source_doc_line_posting')
    )
    op.create_index(op.f('ix_stock_ledger_entries_entry_number'), 'stock_ledger_entries', ['entry_number'], unique=True)
    op.create_index(op.f('ix_stock_ledger_entries_posting_group_id'), 'stock_ledger_entries', ['posting_group_id'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_material_item_id'), 'stock_ledger_entries', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_uom_id'), 'stock_ledger_entries', ['uom_id'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_transaction_date'), 'stock_ledger_entries', ['transaction_date'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_posted_at'), 'stock_ledger_entries', ['posted_at'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_movement_type'), 'stock_ledger_entries', ['movement_type'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_source_document_type'), 'stock_ledger_entries', ['source_document_type'], unique=False)
    op.create_index(op.f('ix_stock_ledger_entries_source_document_number'), 'stock_ledger_entries', ['source_document_number'], unique=False)
    op.create_index('ix_ledger_item_date', 'stock_ledger_entries', ['material_item_id', 'transaction_date'], unique=False)

    # 2. physical_audit_headers table
    op.create_table(
        'physical_audit_headers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_number', sa.String(length=50), nullable=False),
        sa.Column('audit_date', sa.Date(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_physical_audit_headers_department_id_departments')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_physical_audit_headers'))
    )
    op.create_index(op.f('ix_physical_audit_headers_audit_number'), 'physical_audit_headers', ['audit_number'], unique=True)
    op.create_index(op.f('ix_physical_audit_headers_audit_date'), 'physical_audit_headers', ['audit_date'], unique=False)
    op.create_index(op.f('ix_physical_audit_headers_department_id'), 'physical_audit_headers', ['department_id'], unique=False)
    op.create_index(op.f('ix_physical_audit_headers_status'), 'physical_audit_headers', ['status'], unique=False)

    # 3. physical_audit_lines table
    op.create_table(
        'physical_audit_lines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('system_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('physical_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('variance', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['audit_id'], ['physical_audit_headers.id'], name=op.f('fk_physical_audit_lines_audit_id_physical_audit_headers'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_physical_audit_lines_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], name=op.f('fk_physical_audit_lines_uom_id_uoms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_physical_audit_lines'))
    )
    op.create_index(op.f('ix_physical_audit_lines_audit_id'), 'physical_audit_lines', ['audit_id'], unique=False)
    op.create_index(op.f('ix_physical_audit_lines_material_item_id'), 'physical_audit_lines', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_physical_audit_lines_uom_id'), 'physical_audit_lines', ['uom_id'], unique=False)

    # 4. physical_audit_audit_logs table
    op.create_table(
        'physical_audit_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['physical_audit_headers.id'], name=op.f('fk_physical_audit_audit_logs_audit_id_physical_audit_headers'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_physical_audit_audit_logs'))
    )
    op.create_index(op.f('ix_physical_audit_audit_logs_audit_id'), 'physical_audit_audit_logs', ['audit_id'], unique=False)


def downgrade() -> None:
    op.drop_table('physical_audit_audit_logs')
    op.drop_table('physical_audit_lines')
    op.drop_table('physical_audit_headers')
    op.drop_table('stock_ledger_entries')
