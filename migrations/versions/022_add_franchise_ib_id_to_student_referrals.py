"""Add franchise_ib_id to student_referrals

Revision ID: 022_add_franchise_ib_id
Revises: 021_add_offline_payment_columns
Create Date: 2026-07-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '022_add_franchise_ib_id'
down_revision: Union[str, None] = '021_add_offline_payment_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add franchise_ib_id column to student_referrals
    op.add_column('student_referrals', sa.Column('franchise_ib_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'student_referrals_franchise_ib_id_fkey',
        'student_referrals', 'franchise_ibs',
        ['franchise_ib_id'], ['id'],
        ondelete='CASCADE'
    )

def downgrade() -> None:
    # Drop franchise_ib_id column and foreign key
    op.drop_constraint('student_referrals_franchise_ib_id_fkey', 'student_referrals', type_='foreignkey')
    op.drop_column('student_referrals', 'franchise_ib_id')
