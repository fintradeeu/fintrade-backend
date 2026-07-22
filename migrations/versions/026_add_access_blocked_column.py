"""Add access_blocked column to course_enrollments

Revision ID: 026
Revises: 025
Create Date: 2026-07-22 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '026'
down_revision: Union[str, None] = '025_make_distributor_id_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE course_enrollments ADD COLUMN IF NOT EXISTS access_blocked BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.drop_column('course_enrollments', 'access_blocked')
