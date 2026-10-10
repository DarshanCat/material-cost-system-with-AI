"""create phase 2 master data and approval workflow tables

Revision ID: 001_phase2_master_data
Revises: 
Create Date: 2026-10-10 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_phase2_master_data'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. departments table
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
        sa.UniqueConstraint('name', name=op.f('uq_departments_name'))
    )
    op.create_index(op.f('ix_departments_code'), 'departments', ['code'], unique=True)

    # 2. uoms table
    op.create_table(
        'uoms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('decimal_precision', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_uoms'))
    )
    op.create_index(op.f('ix_uoms_code'), 'uoms', ['code'], unique=True)

    # 3. vendors table
    op.create_table(
        'vendors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('normalized_name', sa.String(length=255), nullable=False),
        sa.Column('gstin', sa.String(length=15), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('contact_person', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vendors'))
    )
    op.create_index(op.f('ix_vendors_normalized_name'), 'vendors', ['normalized_name'], unique=True)
    op.create_index(op.f('ix_vendors_gstin'), 'vendors', ['gstin'], unique=False)

    # 4. material_items table
    op.create_table(
        'material_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('subcategory', sa.String(length=50), nullable=True),
        sa.Column('base_uom_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_material_items_department_id_departments')),
        sa.ForeignKeyConstraint(['base_uom_id'], ['uoms.id'], name=op.f('fk_material_items_base_uom_id_uoms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_material_items'))
    )
    op.create_index(op.f('ix_material_items_item_code'), 'material_items', ['item_code'], unique=True)
    op.create_index(op.f('ix_material_items_name'), 'material_items', ['name'], unique=False)
    op.create_index(op.f('ix_material_items_category'), 'material_items', ['category'], unique=False)
    op.create_index(op.f('ix_material_items_department_id'), 'material_items', ['department_id'], unique=False)
    op.create_index(op.f('ix_material_items_base_uom_id'), 'material_items', ['base_uom_id'], unique=False)

    # 5. item_requests table
    op.create_table(
        'item_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('request_number', sa.String(length=50), nullable=False),
        sa.Column('requested_name', sa.String(length=255), nullable=False),
        sa.Column('proposed_department_id', sa.Integer(), nullable=False),
        sa.Column('proposed_category', sa.String(length=50), nullable=False),
        sa.Column('proposed_subcategory', sa.String(length=50), nullable=True),
        sa.Column('proposed_uom_id', sa.Integer(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('requester_id', sa.String(length=100), nullable=False),
        sa.Column('requester_role', sa.String(length=50), nullable=False),
        sa.Column('requester_department', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_id', sa.String(length=100), nullable=True),
        sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_comments', sa.Text(), nullable=True),
        sa.Column('linked_item_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['proposed_department_id'], ['departments.id'], name=op.f('fk_item_requests_proposed_department_id_departments')),
        sa.ForeignKeyConstraint(['proposed_uom_id'], ['uoms.id'], name=op.f('fk_item_requests_proposed_uom_id_uoms')),
        sa.ForeignKeyConstraint(['linked_item_id'], ['material_items.id'], name=op.f('fk_item_requests_linked_item_id_material_items')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_item_requests'))
    )
    op.create_index(op.f('ix_item_requests_request_number'), 'item_requests', ['request_number'], unique=True)
    op.create_index(op.f('ix_item_requests_status'), 'item_requests', ['status'], unique=False)
    op.create_index(op.f('ix_item_requests_requester_id'), 'item_requests', ['requester_id'], unique=False)
    op.create_index(op.f('ix_item_requests_proposed_department_id'), 'item_requests', ['proposed_department_id'], unique=False)
    op.create_index(op.f('ix_item_requests_proposed_category'), 'item_requests', ['proposed_category'], unique=False)

    # 6. item_request_audit_logs table
    op.create_table(
        'item_request_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('actor_role', sa.String(length=50), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['item_requests.id'], name=op.f('fk_item_request_audit_logs_request_id_item_requests')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_item_request_audit_logs'))
    )
    op.create_index(op.f('ix_item_request_audit_logs_request_id'), 'item_request_audit_logs', ['request_id'], unique=False)


def downgrade() -> None:
    op.drop_table('item_request_audit_logs')
    op.drop_table('item_requests')
    op.drop_table('material_items')
    op.drop_table('vendors')
    op.drop_table('uoms')
    op.drop_table('departments')
