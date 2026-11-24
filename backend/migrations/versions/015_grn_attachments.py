"""GRN attachments (supporting documents)

Revision ID: 015_grn_attachments
Revises: 014_pr_po_returns
Create Date: 2026-11-23 15:00:00.000000

Adds ONE new table, grn_attachments (the record of each uploaded document; the file itself is in the attachment store).
No existing table is changed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '015_grn_attachments'
down_revision: Union[str, None] = '014_pr_po_returns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'grn_attachments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('grn_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=200), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('storage_key', sa.String(length=300), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('uploaded_by', sa.String(length=100), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['grn_id'], ['grn_headers.id'], name='fk_grn_attachments_grn_id_grn_headers', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_grn_attachments'),
        sa.UniqueConstraint('storage_key', name='uq_grn_attachments_storage_key'),
    )
    op.create_index('ix_grn_attachments_grn_id', 'grn_attachments', ['grn_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_grn_attachments_grn_id', table_name='grn_attachments')
    op.drop_table('grn_attachments')
