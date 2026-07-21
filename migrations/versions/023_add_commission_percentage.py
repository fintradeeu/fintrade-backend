"""add commission_percentage to franchise_ibs

Revision ID: 023
Revises: 022
Create Date: 2026-07-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    # add commission_percentage column with default 100.0
    op.add_column('franchise_ibs', sa.Column('commission_percentage', sa.Float(), nullable=False, server_default='100.0'))


def downgrade():
    op.drop_column('franchise_ibs', 'commission_percentage')
