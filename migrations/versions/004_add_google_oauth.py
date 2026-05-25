"""add google oauth support

Revision ID: 004_add_google_oauth
Revises: 003_make_lecture_course_id_nullable
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '004_add_google_oauth'
down_revision = '003_make_lecture_course_id_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)

    def col_exists(table, col):
        return any(c['name'] == col for c in insp.get_columns(table))

    # ── Add google_id to users ───────────────────────────────────────
    if not col_exists('users', 'google_id'):
        op.add_column('users', sa.Column('google_id', sa.String(255), nullable=True, unique=True))
        op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)

    # ── Make hashed_password nullable ────────────────────────────────
    # SQLite requires table recreation for column alterations,
    # so we only attempt on dialects that support it directly.
    if bind.dialect.name == 'postgresql':
        op.alter_column('users', 'hashed_password', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    pass
