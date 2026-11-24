"""PROPOSED — add liquid heel and furnace mass-balance tracking to heat_headers

Revision ID: 012_heat_liquid_heel
Revises: 011_stock_ledger_valuation
Create Date: 2026-11-05 11:15:00.000000

STATUS: PROPOSAL ONLY. NOT APPROVED. NOT EXECUTED.
This file deliberately lives in migrations/proposed/, outside Alembic's version location
(migrations/versions), so `alembic upgrade head` cannot apply it. To adopt it after explicit approval,
review it, move it into migrations/versions/, and run it against the isolated non-production database first.

Why:
Remediates External Review Observation 10 & 11 (Phase 2B-1 & Phase 2B-2A):
1. Untracked induction furnace liquid heel carryover caused apparent negative melt loss (-3.78% to -4.82%)
   and melting recovery > 100% (103.78% to 104.82%) across historical heats H-20261015-0001, H-20261016-0001,
   and H-20261022-0001 (cumulative unexplained excess tapped metal: +890.0000 kg).
2. Establishes schema fields for opening liquid heel, closing liquid heel, measurement methodology,
   maker-checker verification status, and heat-to-heat carry-forward traceability.

Columns Added to heat_headers:
- opening_liquid_heel_kg NUMERIC(15, 4) NULL (CHECK >= 0)
- closing_liquid_heel_kg NUMERIC(15, 4) NULL (CHECK >= 0)
- heel_measurement_method VARCHAR(50) NULL
- heel_recorded_by VARCHAR(100) NULL
- heel_verified_by VARCHAR(100) NULL
- heel_verified_at TIMESTAMP WITH TIME ZONE NULL
- heel_verification_status VARCHAR(30) NOT NULL DEFAULT 'UNRECORDED'
- is_cold_start BOOLEAN NOT NULL DEFAULT FALSE
- is_furnace_empty BOOLEAN NOT NULL DEFAULT FALSE
- opening_heel_source_heat_id INTEGER NULL REFERENCES heat_headers(id)

Constraints & Indexes:
- chk_opening_heel_non_negative: opening_liquid_heel_kg IS NULL OR opening_liquid_heel_kg >= 0
- chk_closing_heel_non_negative: closing_liquid_heel_kg IS NULL OR closing_liquid_heel_kg >= 0
- uq_heat_opening_heel_source: UNIQUE index on opening_heel_source_heat_id WHERE NOT NULL
  (prevents concurrent/duplicate consumption of a single closing heel)
- ix_heat_headers_heel_verification_status: index on heel_verification_status
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012_heat_liquid_heel'
down_revision: Union[str, None] = '011_stock_ledger_valuation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add liquid heel columns
    op.add_column('heat_headers', sa.Column('opening_liquid_heel_kg', sa.Numeric(precision=15, scale=4), nullable=True))
    op.add_column('heat_headers', sa.Column('closing_liquid_heel_kg', sa.Numeric(precision=15, scale=4), nullable=True))
    op.add_column('heat_headers', sa.Column('heel_measurement_method', sa.String(length=50), nullable=True))
    op.add_column('heat_headers', sa.Column('heel_recorded_by', sa.String(length=100), nullable=True))
    op.add_column('heat_headers', sa.Column('heel_verified_by', sa.String(length=100), nullable=True))
    op.add_column('heat_headers', sa.Column('heel_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('heat_headers', sa.Column('heel_verification_status', sa.String(length=30), nullable=False, server_default='UNRECORDED'))
    op.add_column('heat_headers', sa.Column('is_cold_start', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
    op.add_column('heat_headers', sa.Column('is_furnace_empty', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')))
    op.add_column('heat_headers', sa.Column('opening_heel_source_heat_id', sa.Integer(), nullable=True))

    # 2. Add foreign key for carry-forward source heat
    op.create_foreign_key(
        'fk_heat_headers_opening_heel_source',
        'heat_headers',
        'heat_headers',
        ['opening_heel_source_heat_id'],
        ['id'],
    )

    # 3. Add CHECK constraints for non-negative heel quantities
    op.create_check_constraint(
        'chk_opening_heel_non_negative',
        'heat_headers',
        'opening_liquid_heel_kg IS NULL OR opening_liquid_heel_kg >= 0',
    )
    op.create_check_constraint(
        'chk_closing_heel_non_negative',
        'heat_headers',
        'closing_liquid_heel_kg IS NULL OR closing_liquid_heel_kg >= 0',
    )

    # 4. Add index on verification status
    op.create_index(
        'ix_heat_headers_heel_verification_status',
        'heat_headers',
        ['heel_verification_status'],
        unique=False,
    )

    # 5. Add unique partial index to prevent multiple heats from consuming the same closing heel
    op.create_index(
        'uq_heat_opening_heel_source',
        'heat_headers',
        ['opening_heel_source_heat_id'],
        unique=True,
        postgresql_where=sa.text('opening_heel_source_heat_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_heat_opening_heel_source', table_name='heat_headers')
    op.drop_index('ix_heat_headers_heel_verification_status', table_name='heat_headers')
    op.drop_constraint('chk_closing_heel_non_negative', 'heat_headers', type_='check')
    op.drop_constraint('chk_opening_heel_non_negative', 'heat_headers', type_='check')
    op.drop_constraint('fk_heat_headers_opening_heel_source', 'heat_headers', type_='foreignkey')

    op.drop_column('heat_headers', 'opening_heel_source_heat_id')
    op.drop_column('heat_headers', 'is_furnace_empty')
    op.drop_column('heat_headers', 'is_cold_start')
    op.drop_column('heat_headers', 'heel_verification_status')
    op.drop_column('heat_headers', 'heel_verified_at')
    op.drop_column('heat_headers', 'heel_verified_by')
    op.drop_column('heat_headers', 'heel_recorded_by')
    op.drop_column('heat_headers', 'heel_measurement_method')
    op.drop_column('heat_headers', 'closing_liquid_heel_kg')
    op.drop_column('heat_headers', 'opening_liquid_heel_kg')
