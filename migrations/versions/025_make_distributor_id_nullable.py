"""Make distributor_id nullable in student_referrals

Revision ID: 025_make_distributor_id_nullable
Revises: 024
Create Date: 2026-07-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '025_make_distributor_id_nullable'
down_revision: Union[str, None] = '024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make distributor_id nullable in student_referrals
    op.alter_column(
        'student_referrals',
        'distributor_id',
        existing_type=sa.Integer(),
        nullable=True
    )


def downgrade() -> None:
    # Make distributor_id non-nullable
    op.alter_column(
        'student_referrals',
        'distributor_id',
        existing_type=sa.Integer(),
        nullable=False
    )
