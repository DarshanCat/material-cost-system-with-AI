"""create phase 6 costing and valuation tables

Revision ID: 005_phase6_costing_valuation
Revises: 004_phase5_heat_reconciliation
Create Date: 2026-10-10 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_phase6_costing_valuation'
down_revision: Union[str, None] = '004_phase5_heat_reconciliation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. costing_runs
    op.create_table(
        'costing_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_number', sa.String(length=50), nullable=False),
        sa.Column('calculation_version', sa.String(length=20), server_default='v1.0.0', nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('denominator_policy', sa.String(length=30), server_default='METAL_TAPPED', nullable=False),
        sa.Column('internal_recovery_policy', sa.String(length=30), server_default='POLICY_PENDING', nullable=False),
        sa.Column('cost_scope', sa.String(length=30), server_default='MATERIAL_ONLY', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='IN_PROGRESS', nullable=False),
        sa.Column('total_items_evaluated', sa.Integer(), server_default='0', nullable=False),
        sa.Column('valued_items_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('unvalued_items_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_inventory_valuation', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_heats_evaluated', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completed_heats_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('partial_heats_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_heat_material_cost', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('summary_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_number')
    )
    op.create_index('ix_costing_runs_run_number', 'costing_runs', ['run_number'], unique=True)
    op.create_index('ix_costing_runs_period_start', 'costing_runs', ['period_start'], unique=False)
    op.create_index('ix_costing_runs_period_end', 'costing_runs', ['period_end'], unique=False)
    op.create_index('ix_costing_runs_as_of_date', 'costing_runs', ['as_of_date'], unique=False)
    op.create_index('ix_costing_runs_status', 'costing_runs', ['status'], unique=False)

    # 2. item_cost_snapshots
    op.create_table(
        'item_cost_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('costing_run_id', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('inventory_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('weighted_average_rate', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('extended_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('valuation_status', sa.String(length=30), server_default='VALUED', nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('rate_source', sa.String(length=50), nullable=True),
        sa.Column('anomaly_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['costing_run_id'], ['costing_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id']),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_item_snapshot_run_item', 'item_cost_snapshots', ['costing_run_id', 'material_item_id'], unique=True)
    op.create_index('ix_item_snapshots_item', 'item_cost_snapshots', ['material_item_id'], unique=False)
    op.create_index('ix_item_snapshots_date', 'item_cost_snapshots', ['as_of_date'], unique=False)
    op.create_index('ix_item_snapshots_status', 'item_cost_snapshots', ['valuation_status'], unique=False)

    # 3. item_cost_journal_entries
    op.create_table(
        'item_cost_journal_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('costing_run_id', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('stock_ledger_entry_id', sa.Integer(), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('movement_type', sa.String(length=50), nullable=False),
        sa.Column('quantity_delta', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('running_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('receipt_rate', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('applied_rate', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('resulting_average_rate', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('movement_extended_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('cumulative_value', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='APPLIED', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['costing_run_id'], ['costing_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id']),
        sa.ForeignKeyConstraint(['stock_ledger_entry_id'], ['stock_ledger_entries.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cost_journal_item_tx', 'item_cost_journal_entries', ['material_item_id', 'transaction_date'], unique=False)

    # 4. heat_cost_records
    op.create_table(
        'heat_cost_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('costing_run_id', sa.Integer(), nullable=False),
        sa.Column('heat_id', sa.Integer(), nullable=False),
        sa.Column('heat_number', sa.String(length=50), nullable=False),
        sa.Column('heat_date', sa.Date(), nullable=False),
        sa.Column('total_charged_quantity', sa.Numeric(precision=15, scale=4), server_default='0.0000', nullable=False),
        sa.Column('total_material_cost', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('metal_tapped_weight', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('cost_denominator_value', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('denominator_type', sa.String(length=30), server_default='METAL_TAPPED', nullable=False),
        sa.Column('cost_per_kg', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('cost_scope', sa.String(length=30), server_default='MATERIAL_ONLY', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='COMPLETE', nullable=False),
        sa.Column('total_lines', sa.Integer(), server_default='0', nullable=False),
        sa.Column('valued_lines', sa.Integer(), server_default='0', nullable=False),
        sa.Column('unvalued_lines', sa.Integer(), server_default='0', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['costing_run_id'], ['costing_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['heat_id'], ['heat_headers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_heat_cost_run_heat', 'heat_cost_records', ['costing_run_id', 'heat_id'], unique=True)
    op.create_index('ix_heat_cost_records_heat_num', 'heat_cost_records', ['heat_number'], unique=False)
    op.create_index('ix_heat_cost_records_date', 'heat_cost_records', ['heat_date'], unique=False)
    op.create_index('ix_heat_cost_records_status', 'heat_cost_records', ['status'], unique=False)

    # 5. heat_cost_lines
    op.create_table(
        'heat_cost_lines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('heat_cost_record_id', sa.Integer(), nullable=False),
        sa.Column('heat_charge_line_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=True),
        sa.Column('raw_material_description', sa.String(length=255), nullable=False),
        sa.Column('charged_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('applicable_rate', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('line_cost', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('rate_source', sa.String(length=50), nullable=True),
        sa.Column('is_included', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='VALUED', nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['heat_cost_record_id'], ['heat_cost_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['heat_charge_line_id'], ['heat_charge_lines.id']),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_heat_cost_lines_record', 'heat_cost_lines', ['heat_cost_record_id'], unique=False)
    op.create_index('ix_heat_cost_lines_charge', 'heat_cost_lines', ['heat_charge_line_id'], unique=False)

    # 6. part_cost_records
    op.create_table(
        'part_cost_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('costing_run_id', sa.Integer(), nullable=False),
        sa.Column('heat_cost_record_id', sa.Integer(), nullable=False),
        sa.Column('heat_parts_produced_id', sa.Integer(), nullable=False),
        sa.Column('part_number', sa.String(length=100), nullable=False),
        sa.Column('part_name', sa.String(length=255), nullable=False),
        sa.Column('part_item_id', sa.Integer(), nullable=True),
        sa.Column('quantity_produced', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit_cast_weight', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('weight_uom_id', sa.Integer(), nullable=True),
        sa.Column('cost_per_kg', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('part_material_cost_per_unit', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('total_part_material_cost', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('cost_scope', sa.String(length=30), server_default='MATERIAL_ONLY', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='CALCULATED', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['costing_run_id'], ['costing_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['heat_cost_record_id'], ['heat_cost_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['heat_parts_produced_id'], ['heat_parts_produced.id']),
        sa.ForeignKeyConstraint(['part_item_id'], ['material_items.id']),
        sa.ForeignKeyConstraint(['weight_uom_id'], ['uoms.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_part_cost_run', 'part_cost_records', ['costing_run_id'], unique=False)
    op.create_index('ix_part_cost_heat_rec', 'part_cost_records', ['heat_cost_record_id'], unique=False)
    op.create_index('ix_part_cost_part_num', 'part_cost_records', ['part_number'], unique=False)
    op.create_index('ix_part_cost_status', 'part_cost_records', ['status'], unique=False)

    # 7. item_opening_valuations
    op.create_table(
        'item_opening_valuations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('baseline_date', sa.Date(), nullable=False),
        sa.Column('opening_rate_ex_gst', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='PENDING_APPROVAL', nullable=False),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('material_item_id')
    )
    op.create_index('ix_opening_valuation_item', 'item_opening_valuations', ['material_item_id'], unique=True)
    op.create_index('ix_opening_valuation_status', 'item_opening_valuations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('item_opening_valuations')
    op.drop_table('part_cost_records')
    op.drop_table('heat_cost_lines')
    op.drop_table('heat_cost_records')
    op.drop_table('item_cost_journal_entries')
    op.drop_table('item_cost_snapshots')
    op.drop_table('costing_runs')
