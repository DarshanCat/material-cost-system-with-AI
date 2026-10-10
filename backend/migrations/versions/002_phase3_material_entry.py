"""create phase 3 material entry and transaction validation tables

Revision ID: 002_phase3_material_entry
Revises: 001_phase2_master_data
Create Date: 2026-10-10 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_phase3_material_entry'
down_revision: Union[str, None] = '001_phase2_master_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. grn_headers table
    op.create_table(
        'grn_headers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('grn_number', sa.String(length=50), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('source_type', sa.String(length=30), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=True),
        sa.Column('vendor_invoice_no', sa.String(length=100), nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=True),
        sa.Column('reference_document', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], name=op.f('fk_grn_headers_vendor_id_vendors')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grn_headers'))
    )
    op.create_index(op.f('ix_grn_headers_grn_number'), 'grn_headers', ['grn_number'], unique=True)
    op.create_index(op.f('ix_grn_headers_receipt_date'), 'grn_headers', ['receipt_date'], unique=False)
    op.create_index(op.f('ix_grn_headers_status'), 'grn_headers', ['status'], unique=False)
    op.create_index(op.f('ix_grn_headers_vendor_id'), 'grn_headers', ['vendor_id'], unique=False)
    op.create_index('ix_grn_vendor_invoice', 'grn_headers', ['vendor_id', 'vendor_invoice_no', 'invoice_date'], unique=False)

    # 2. grn_line_items table
    op.create_table(
        'grn_line_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('grn_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('rate_ex_gst', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('gst_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['grn_id'], ['grn_headers.id'], name=op.f('fk_grn_line_items_grn_id_grn_headers'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_grn_line_items_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], name=op.f('fk_grn_line_items_uom_id_uoms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grn_line_items'))
    )
    op.create_index(op.f('ix_grn_line_items_grn_id'), 'grn_line_items', ['grn_id'], unique=False)
    op.create_index(op.f('ix_grn_line_items_material_item_id'), 'grn_line_items', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_grn_line_items_uom_id'), 'grn_line_items', ['uom_id'], unique=False)

    # 3. grn_audit_logs table
    op.create_table(
        'grn_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('grn_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['grn_id'], ['grn_headers.id'], name=op.f('fk_grn_audit_logs_grn_id_grn_headers'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grn_audit_logs'))
    )
    op.create_index(op.f('ix_grn_audit_logs_grn_id'), 'grn_audit_logs', ['grn_id'], unique=False)

    # 4. material_issue_headers table
    op.create_table(
        'material_issue_headers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_slip_number', sa.String(length=50), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('issuing_department_id', sa.Integer(), nullable=False),
        sa.Column('receiving_department_id', sa.Integer(), nullable=False),
        sa.Column('heat_reference_number', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['issuing_department_id'], ['departments.id'], name=op.f('fk_material_issue_headers_issuing_department_id_departments')),
        sa.ForeignKeyConstraint(['receiving_department_id'], ['departments.id'], name=op.f('fk_material_issue_headers_receiving_department_id_departments')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_material_issue_headers'))
    )
    op.create_index(op.f('ix_material_issue_headers_issue_slip_number'), 'material_issue_headers', ['issue_slip_number'], unique=True)
    op.create_index(op.f('ix_material_issue_headers_issue_date'), 'material_issue_headers', ['issue_date'], unique=False)
    op.create_index(op.f('ix_material_issue_headers_issuing_department_id'), 'material_issue_headers', ['issuing_department_id'], unique=False)
    op.create_index(op.f('ix_material_issue_headers_receiving_department_id'), 'material_issue_headers', ['receiving_department_id'], unique=False)
    op.create_index(op.f('ix_material_issue_headers_heat_reference_number'), 'material_issue_headers', ['heat_reference_number'], unique=False)
    op.create_index(op.f('ix_material_issue_headers_status'), 'material_issue_headers', ['status'], unique=False)
    op.create_index('ix_issue_slip_date_recv', 'material_issue_headers', ['issue_slip_number', 'issue_date', 'receiving_department_id'], unique=False)

    # 5. material_issue_line_items table
    op.create_table(
        'material_issue_line_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['issue_id'], ['material_issue_headers.id'], name=op.f('fk_material_issue_line_items_issue_id_material_issue_headers'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_material_issue_line_items_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], name=op.f('fk_material_issue_line_items_uom_id_uoms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_material_issue_line_items'))
    )
    op.create_index(op.f('ix_material_issue_line_items_issue_id'), 'material_issue_line_items', ['issue_id'], unique=False)
    op.create_index(op.f('ix_material_issue_line_items_material_item_id'), 'material_issue_line_items', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_material_issue_line_items_uom_id'), 'material_issue_line_items', ['uom_id'], unique=False)

    # 6. issue_audit_logs table
    op.create_table(
        'issue_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['issue_id'], ['material_issue_headers.id'], name=op.f('fk_issue_audit_logs_issue_id_material_issue_headers'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_issue_audit_logs'))
    )
    op.create_index(op.f('ix_issue_audit_logs_issue_id'), 'issue_audit_logs', ['issue_id'], unique=False)

    # 7. waste_disposition_headers table
    op.create_table(
        'waste_disposition_headers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('waste_number', sa.String(length=50), nullable=False),
        sa.Column('disposition_date', sa.Date(), nullable=False),
        sa.Column('waste_type', sa.String(length=50), nullable=False),
        sa.Column('disposition_type', sa.String(length=50), nullable=False),
        sa.Column('source_department_id', sa.Integer(), nullable=False),
        sa.Column('destination_notes', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_department_id'], ['departments.id'], name=op.f('fk_waste_disposition_headers_source_department_id_departments')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_waste_disposition_headers'))
    )
    op.create_index(op.f('ix_waste_disposition_headers_waste_number'), 'waste_disposition_headers', ['waste_number'], unique=True)
    op.create_index(op.f('ix_waste_disposition_headers_disposition_date'), 'waste_disposition_headers', ['disposition_date'], unique=False)
    op.create_index(op.f('ix_waste_disposition_headers_waste_type'), 'waste_disposition_headers', ['waste_type'], unique=False)
    op.create_index(op.f('ix_waste_disposition_headers_disposition_type'), 'waste_disposition_headers', ['disposition_type'], unique=False)
    op.create_index(op.f('ix_waste_disposition_headers_source_department_id'), 'waste_disposition_headers', ['source_department_id'], unique=False)
    op.create_index(op.f('ix_waste_disposition_headers_status'), 'waste_disposition_headers', ['status'], unique=False)

    # 8. waste_disposition_line_items table
    op.create_table(
        'waste_disposition_line_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('waste_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('material_item_id', sa.Integer(), nullable=False),
        sa.Column('uom_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['waste_id'], ['waste_disposition_headers.id'], name=op.f('fk_waste_disposition_line_items_waste_id_waste_disposition_headers'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_item_id'], ['material_items.id'], name=op.f('fk_waste_disposition_line_items_material_item_id_material_items')),
        sa.ForeignKeyConstraint(['uom_id'], ['uoms.id'], name=op.f('fk_waste_disposition_line_items_uom_id_uoms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_waste_disposition_line_items'))
    )
    op.create_index(op.f('ix_waste_disposition_line_items_waste_id'), 'waste_disposition_line_items', ['waste_id'], unique=False)
    op.create_index(op.f('ix_waste_disposition_line_items_material_item_id'), 'waste_disposition_line_items', ['material_item_id'], unique=False)
    op.create_index(op.f('ix_waste_disposition_line_items_uom_id'), 'waste_disposition_line_items', ['uom_id'], unique=False)

    # 9. waste_audit_logs table
    op.create_table(
        'waste_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('waste_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['waste_id'], ['waste_disposition_headers.id'], name=op.f('fk_waste_audit_logs_waste_id_waste_disposition_headers'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_waste_audit_logs'))
    )
    op.create_index(op.f('ix_waste_audit_logs_waste_id'), 'waste_audit_logs', ['waste_id'], unique=False)


def downgrade() -> None:
    op.drop_table('waste_audit_logs')
    op.drop_table('waste_disposition_line_items')
    op.drop_table('waste_disposition_headers')
    op.drop_table('issue_audit_logs')
    op.drop_table('material_issue_line_items')
    op.drop_table('material_issue_headers')
    op.drop_table('grn_audit_logs')
    op.drop_table('grn_line_items')
    op.drop_table('grn_headers')
