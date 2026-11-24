"""PROPOSED — add material_items.reconciliation_category with CHECK constraint and Slax override

Revision ID: 010_item_reconciliation_cat
Revises: 009_material_item_cost_head
Create Date: 2026-10-29 11:00:00.000000

STATUS: PROPOSAL ONLY. NOT APPROVED. NOT EXECUTED.
This file deliberately lives in migrations/proposed/, outside Alembic's version location
(migrations/versions), so `alembic upgrade head` cannot apply it. To adopt it after explicit approval,
review it, move it into migrations/versions/, and run it against the non-production database first.

Why: Phase 5 Step 3 requires an authorized, audited item-level classification override for
heat log reconciliation, resolving items like Slax (FDY-RM-021) which are coded under Raw Material (RM)
yet are non-heat floor consumables.

Column
  reconciliation_category VARCHAR(30) NULL,
  CHECK (reconciliation_category IS NULL OR reconciliation_category IN ('HEAT_TRACEABLE', 'NON_HEAT_SPECIFIC', 'REVIEW_REQUIRED')).

Conservative backfill:
  - Seeds approved override: 'FDY-RM-021' (Slax) -> 'NON_HEAT_SPECIFIC'.
  - Other items remain NULL so they dynamically resolve via Nomenclature Standard v1.0 defaults or human review.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


RECON_CATEGORIES = ("HEAT_TRACEABLE", "NON_HEAT_SPECIFIC", "REVIEW_REQUIRED")

# revision identifiers, used by Alembic.
revision: str = '010_item_reconciliation_cat'
down_revision: Union[str, None] = '009_material_item_cost_head'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    allowed = ", ".join(f"'{cat}'" for cat in RECON_CATEGORIES)
    with op.batch_alter_table('material_items') as batch:
        batch.add_column(sa.Column('reconciliation_category', sa.String(length=30), nullable=True))
        batch.create_check_constraint(
            'ck_material_item_reconciliation_category',
            f"reconciliation_category IS NULL OR reconciliation_category IN ({allowed})"
        )

    material_items = sa.table(
        'material_items',
        sa.column('item_code', sa.String),
        sa.column('reconciliation_category', sa.String),
    )
    # Approved override for Slax
    op.execute(
        material_items.update()
        .where(material_items.c.item_code == "FDY-RM-021")
        .values(reconciliation_category="NON_HEAT_SPECIFIC")
    )


def downgrade() -> None:
    with op.batch_alter_table('material_items') as batch:
        batch.drop_constraint('ck_material_item_reconciliation_category', type_='check')
        batch.drop_column('reconciliation_category')
