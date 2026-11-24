"""application users and user audit log (admin-managed sign-in)

Revision ID: 013_app_users
Revises: 012_heat_liquid_heel
Create Date: 2026-11-22 20:00:00.000000

Adds two NEW tables only: app_users (e-mail, role, status, approval trail) and app_user_audit_logs.
No existing table is changed. Passwords are never stored here (Google Identity Platform owns them).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '013_app_users'
down_revision: Union[str, None] = '012_heat_liquid_heel'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('auth_uid', sa.String(length=128), nullable=True),
        sa.Column('auth_source', sa.String(length=32), nullable=False, server_default='password'),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('temp_password_set_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=254), nullable=True),
        sa.Column('decided_by', sa.String(length=254), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','active','rejected','disabled')", name='ck_app_users_status_valid'),
        sa.PrimaryKeyConstraint('id', name='pk_app_users'),
    )
    op.create_index('ix_app_users_email', 'app_users', ['email'], unique=True)
    op.create_index('ix_app_users_status', 'app_users', ['status'], unique=False)

    op.create_table(
        'app_user_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_email', sa.String(length=254), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('actor', sa.String(length=254), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_app_user_audit_logs'),
    )
    op.create_index('ix_app_user_audit_logs_user_email', 'app_user_audit_logs', ['user_email'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_app_user_audit_logs_user_email', table_name='app_user_audit_logs')
    op.drop_table('app_user_audit_logs')
    op.drop_index('ix_app_users_status', table_name='app_users')
    op.drop_index('ix_app_users_email', table_name='app_users')
    op.drop_table('app_users')
