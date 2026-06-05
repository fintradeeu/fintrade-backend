"""add permissions column to users

Revision ID: 008_add_user_permissions
Revises: 007_fix_news_enums
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa

revision = "008_add_user_permissions"
down_revision = "007_fix_news_enums"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "users" in insp.get_table_names():
        columns = {col["name"] for col in insp.get_columns("users")}
        if "permissions" not in columns:
            op.add_column("users", sa.Column("permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "users" in insp.get_table_names():
        columns = {col["name"] for col in insp.get_columns("users")}
        if "permissions" in columns:
            op.drop_column("users", "permissions")
