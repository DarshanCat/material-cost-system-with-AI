"""GRN quality inspection and payment records

Revision ID: 016_grn_qa_and_payment
Revises: 015_grn_attachments
Create Date: 2026-11-23 18:00:00.000000

Adds nullable columns to grn_headers: the QA inspection result and the payment record. No data is changed and no
existing column is altered, so existing GRNs keep working (they simply have no QA / payment details yet).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '016_grn_qa_and_payment'
down_revision: Union[str, None] = '015_grn_attachments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    sa.Column('quality_document_number', sa.String(length=100), nullable=True),
    sa.Column('quality_inspection_status', sa.String(length=30), nullable=True),
    sa.Column('quality_inspection_notes', sa.Text(), nullable=True),
    sa.Column('quality_inspected_by', sa.String(length=100), nullable=True),
    sa.Column('quality_inspected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('payment_status', sa.String(length=20), nullable=True),
    sa.Column('amount_paid', sa.Numeric(15, 2), nullable=True),
    sa.Column('payment_reference', sa.String(length=100), nullable=True),
    sa.Column('payment_date', sa.Date(), nullable=True),
    sa.Column('payment_mode', sa.String(length=30), nullable=True),
    sa.Column('payment_notes', sa.Text(), nullable=True),
    sa.Column('paid_by', sa.String(length=100), nullable=True),
]


def upgrade() -> None:
    for col in COLUMNS:
        op.add_column('grn_headers', col)


def downgrade() -> None:
    for col in reversed(COLUMNS):
        op.drop_column('grn_headers', col.name)
