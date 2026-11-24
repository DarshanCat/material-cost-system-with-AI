"""purchase requests, purchase orders and return-to-store tables

Revision ID: 014_pr_po_returns
Revises: 013_app_users
Create Date: 2026-11-23 12:30:00.000000

The models for Purchase Requests (pr_*), Purchase Orders (po_*) and Return to Store (material_return_*) existed, but no
migration created their tables: they were only created by a `Base.metadata.create_all` call that ran when the API
modules were imported, which is not used for a database managed by Alembic. On a database built by migrations every
request to these three modules failed with "relation pr_headers does not exist". This revision creates the nine
tables, only if missing, from the current model definitions. It adds NEW tables only.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '014_pr_po_returns'
down_revision: Union[str, None] = '013_app_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'pr_headers', 'pr_line_items', 'pr_audit_logs',
    'po_headers', 'po_line_items', 'po_audit_logs',
    'material_return_headers', 'material_return_line_items', 'material_return_audit_logs',
)


def upgrade() -> None:
    import app.models  # noqa: F401  registers every table on Base.metadata
    from app.db.base import Base

    # Foreign-key order is resolved by create_all; tables that already exist are skipped.
    Base.metadata.create_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in TABLES], checkfirst=True)


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.db.base import Base

    Base.metadata.drop_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in TABLES], checkfirst=True)
