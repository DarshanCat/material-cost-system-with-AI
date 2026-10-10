"""create phase 5 heat log, material aliases, and reconciliation tables

Revision ID: 004_phase5_heat_reconciliation
Revises: 003_phase4_stock_ledger
Create Date: 2026-10-10 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_phase5_heat_reconciliation'
down_revision: Union[str, None] = '003_phase4_stock_ledger'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. heat_headers
    op.create_table(
        'heat_headers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('heat_number', sa.String(length=50), nullable=False),
        sa.Column('original_heat_number', sa.String(length=50), nullable=False),
        sa.Column('normalized_heat_number', sa.String(length=50), nullable=False),
        sa.Column('heat_date', sa.Date(), nullable=False),
        sa.Column('furnace_id', sa.String(length=50), nullable=True),
        sa.Column('shift', sa.String(length=20), nullable=True),
        sa.Column('metal_tapped_weight', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('metal_tapped_uom_id', sa.Integer(), nullable=True),
        sa.Column('production_status', sa.String(length=20), server_default='COMPLETED', nullable=False),
        sa.Column('source_document_reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['metal_tapped_uom_id'], ['uoms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('heat_number')
    )
    op.create_index('ix_heat_headers_heat_number', 'heat_headers', ['heat_number'], unique=True)
    op.create_index('ix_heat_headers_normalized', 'heat_headers', ['normalized_heat_number'], unique=False)
    op.create_index('ix_heat_headers_heat_date', 'heat_headers', ['heat_date'], unique=False)
    op.create_index('ix_heat_headers_furnace_id', 'heat_headers', ['furnace_id'], unique=False)
    op.create_index('ix_heat_headers_status', 'heat_headers', ['production_status'], unique=False)
    op.create_index('ix_heat_date_furnace', 'heat_headers', ['heat_date', 'furnace_id'], unique=False)

    # 2. heat_charge_lines
    op.create_table(
        'heat_charge_lines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('heat_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=True),
        sa.Column('original_material_description', sa.String(length=255), nullable=False),
        sa.Column('charged_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('source_row_reference', sa.String(length=100), nullable=True),
        sa.Column('validation_status', sa.String(length=20), server_default='VALID', nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['heat_id'], ['heat_headers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], ),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_heat_charge_lines_heat_id', 'heat_charge_lines', ['heat_id'], unique=False)
    op.create_index('ix_heat_charge_lines_material_item_id', 'heat_charge_lines', ['material_item_id'], unique=False)
    op.create_index('ix_heat_charge_lines_uom_id', 'heat_charge_lines', ['uom_id'], unique=False)
    op.create_index('ix_heat_charge_heat_line', 'heat_charge_lines', ['heat_id', 'line_number'], unique=True)

    # 3. heat_parts_produced
    op.create_table(
        'heat_parts_produced',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('heat_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('part_item_id', sa.Integer(), nullable=True),
        sa.Column('original_part_description', sa.String(length=255), nullable=False),
        sa.Column('quantity_produced', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit_cast_weight', sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column('weight_uom_id', sa.Integer(), nullable=True),
        sa.Column('classification', sa.String(length=20), server_default='GOOD', nullable=False),
        sa.Column('source_row_reference', sa.String(length=100), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['heat_id'], ['heat_headers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_item_id'], ['material_items.id'], ),
        sa.ForeignKeyConstraint(['weight_uom_id'], ['uoms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_heat_parts_produced_heat_id', 'heat_parts_produced', ['heat_id'], unique=False)
    op.create_index('ix_heat_parts_heat_line', 'heat_parts_produced', ['heat_id', 'line_number'], unique=True)

    # 4. material_aliases
    op.create_table(
        'material_aliases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alias_text', sa.String(length=255), nullable=False),
        sa.Column('normalized_alias_key', sa.String(length=255), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='APPROVED', nullable=False),
        sa.Column('reviewer_id', sa.String(length=100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('normalized_alias_key')
    )
    op.create_index('ix_material_aliases_normalized_key', 'material_aliases', ['normalized_alias_key'], unique=True)
    op.create_index('ix_material_aliases_material_item_id', 'material_aliases', ['material_item_id'], unique=False)
    op.create_index('ix_material_aliases_status', 'material_aliases', ['status'], unique=False)

    # 5. material_alias_audit_logs
    op.create_table(
        'material_alias_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alias_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=50), nullable=True),
        sa.Column('to_status', sa.String(length=50), nullable=True),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['alias_id'], ['material_aliases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alias_audit_alias_id', 'material_alias_audit_logs', ['alias_id'], unique=False)

    # 6. reconciliation_runs
    op.create_table(
        'reconciliation_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_number', sa.String(length=50), nullable=False),
        sa.Column('algorithm_version', sa.String(length=50), server_default='v1.0-3pass-deterministic', nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='COMPLETED', nullable=False),
        sa.Column('total_evaluated_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('exact_matches_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('batch_matches_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('fuzzy_candidates_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('discrepancies_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_number')
    )
    op.create_index('ix_reconciliation_runs_run_number', 'reconciliation_runs', ['run_number'], unique=True)
    op.create_index('ix_reconciliation_runs_date_from', 'reconciliation_runs', ['date_from'], unique=False)
    op.create_index('ix_reconciliation_runs_date_to', 'reconciliation_runs', ['date_to'], unique=False)

    # 7. reconciliation_results
    op.create_table(
        'reconciliation_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=True),
        sa.Column('heat_id', sa.Integer(), nullable=True),
        sa.Column('match_method', sa.String(length=50), nullable=False),
        sa.Column('issued_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('charged_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('variance_quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('variance_percentage', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('applied_tolerance', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('tolerance_basis', sa.String(length=100), nullable=False),
        sa.Column('variance_class', sa.String(length=50), nullable=False),
        sa.Column('contributing_issue_ids', sa.Text(), nullable=True),
        sa.Column('contributing_issue_line_ids', sa.Text(), nullable=True),
        sa.Column('contributing_heat_ids', sa.Text(), nullable=True),
        sa.Column('contributing_charge_line_ids', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='RESOLVED', nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], ),
        sa.ForeignKeyConstraint(['heat_id'], ['heat_headers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reconciliation_results_run_id', 'reconciliation_results', ['run_id'], unique=False)
    op.create_index('ix_reconciliation_results_item_id', 'reconciliation_results', ['material_item_id'], unique=False)
    op.create_index('ix_reconciliation_results_variance_class', 'reconciliation_results', ['variance_class'], unique=False)

    # 8. reconciliation_candidate_matches
    op.create_table(
        'reconciliation_candidate_matches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('issue_line_id', sa.Integer(), nullable=False),
        sa.Column('heat_charge_line_id', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('suggestion_reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='SUGGESTED', nullable=False),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_comments', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issue_line_id'], ['material_issue_line_items.id'], ),
        sa.ForeignKeyConstraint(['heat_charge_line_id'], ['heat_charge_lines.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recon_candidate_run_id', 'reconciliation_candidate_matches', ['run_id'], unique=False)
    op.create_index('ix_recon_candidate_issue_line', 'reconciliation_candidate_matches', ['issue_line_id'], unique=False)
    op.create_index('ix_recon_candidate_charge_line', 'reconciliation_candidate_matches', ['heat_charge_line_id'], unique=False)

    # 9. reconciliation_exceptions
    op.create_table(
        'reconciliation_exceptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('exception_type', sa.String(length=50), nullable=False),
        sa.Column('source_reference', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('assigned_role', sa.String(length=50), server_default='Foundry', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='MEDIUM', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='OPEN', nullable=False),
        sa.Column('resolution_comments', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.String(length=100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recon_exceptions_run_id', 'reconciliation_exceptions', ['run_id'], unique=False)
    op.create_index('ix_recon_exceptions_type', 'reconciliation_exceptions', ['exception_type'], unique=False)
    op.create_index('ix_recon_exceptions_status', 'reconciliation_exceptions', ['status'], unique=False)

    # 10. reconciliation_exception_audit_logs
    op.create_table(
        'reconciliation_exception_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exception_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=50), nullable=True),
        sa.Column('to_status', sa.String(length=50), nullable=True),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exception_id'], ['reconciliation_exceptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recon_exception_audit_id', 'reconciliation_exception_audit_logs', ['exception_id'], unique=False)


def downgrade() -> None:
    op.drop_table('reconciliation_exception_audit_logs')
    op.drop_table('reconciliation_exceptions')
    op.drop_table('reconciliation_candidate_matches')
    op.drop_table('reconciliation_results')
    op.drop_table('reconciliation_runs')
    op.drop_table('material_alias_audit_logs')
    op.drop_table('material_aliases')
    op.drop_table('heat_parts_produced')
    op.drop_table('heat_charge_lines')
    op.drop_table('heat_headers')
