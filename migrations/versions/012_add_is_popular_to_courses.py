"""add is_popular to courses

Revision ID: 012_add_is_popular
Revises: 3abe91512295
Create Date: 2026-06-07 11:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012_add_is_popular'
down_revision = '3abe91512295'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add is_popular column to courses table
    # Using batch operations for SQLite compatibility
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_popular', sa.Boolean(), server_default='0', nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('is_popular')
