"""add user city

Revision ID: 010_add_user_city
Revises: 621bf7ebb607
Create Date: 2026-06-05 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_user_city'
down_revision = '3abe91512295'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('city', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'city')
