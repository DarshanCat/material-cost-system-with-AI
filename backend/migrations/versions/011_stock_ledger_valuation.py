"""PROPOSED — add unit_cost_rate, value_delta, and valuation_method to stock_ledger_entries

Revision ID: 011_stock_ledger_valuation
Revises: 010_item_reconciliation_cat
Create Date: 2026-11-04 15:30:00.000000

STATUS: PROPOSAL ONLY. NOT APPROVED. NOT EXECUTED.
This file deliberately lives in migrations/proposed/, outside Alembic's version location
(migrations/versions), so `alembic upgrade head` cannot apply it. To adopt it after explicit approval,
review it, move it into migrations/versions/, and run it against the isolated non-production database first.

Why:
Remediates Observation 8 and Observation 9 from the External Review.
1. Observation 8: stock_ledger_entries persists physical quantity_delta only, lacking monetary
   rate and value tracking on individual movement lines.
2. Observation 9: Inventory valuation was dynamically reconstructed by multiplying running quantity
   by a 4-decimal rounded weighted-average rate, causing a +Rs 1.49 cumulative rounding error across
   the 43 historical inventory movements (Pig Iron: +Rs 1.40, FeSi: +Rs 0.02, FeMn: +Rs 0.07).

Columns Added:
- unit_cost_rate NUMERIC(15, 4) NULL:
  Unit cost rate applied to this specific movement (purchase rate for GRN inward, applicable
  blended moving average rate for outward issue/scrap, approved rate for opening balance).
- value_delta NUMERIC(15, 2) NULL:
  Exact transaction monetary impact in INR (positive for inward/opening, negative for outward).
  Preserves the fundamental accounting invariant:
  Closing Value = Opening Value + Inward Value - Outward Value +/- Approved Adjustments.
- valuation_method VARCHAR(30) NULL:
  Valuation policy applied (e.g., 'OPENING_VALUATION', 'PURCHASE_PRICE', 'WEIGHTED_AVERAGE').

Immutability & Trigger Considerations:
The table stock_ledger_entries is protected by the PostgreSQL trigger
`trg_stock_ledger_entries_no_update_delete` (from revision 006_sprint2_ledger_immutability).
Adding nullable columns via DDL (ALTER TABLE) succeeds without violating the trigger.
However, backfilling historical rows requires an explicit business decision by the Head of Accounts:
- Option A (Prospective Only): Existing 43 historical rows retain NULL rates/values. New rows mandate rates.
- Option B (Authorized Backfill): Temporarily disable the immutability trigger during a controlled
  maintenance window, backfill from verified GRN lines and opening valuations, and re-enable the trigger.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_stock_ledger_valuation'
down_revision: Union[str, None] = '010_item_reconciliation_cat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add valuation columns to stock_ledger_entries
    with op.batch_alter_table('stock_ledger_entries') as batch:
        batch.add_column(sa.Column('unit_cost_rate', sa.Numeric(15, 4), nullable=True))
        batch.add_column(sa.Column('value_delta', sa.Numeric(15, 2), nullable=True))
        batch.add_column(sa.Column('valuation_method', sa.String(30), nullable=True))


def downgrade() -> None:
    # Remove valuation columns
    with op.batch_alter_table('stock_ledger_entries') as batch:
        batch.drop_column('valuation_method')
        batch.drop_column('value_delta')
        batch.drop_column('unit_cost_rate')
