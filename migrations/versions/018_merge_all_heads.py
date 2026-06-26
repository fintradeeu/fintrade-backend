"""merge all current heads

Revision ID: 018_merge_all_heads
Revises: 012_add_mobile_auth, 017_referral_course_nullable
Create Date: 2026-06-26 15:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018_merge_all_heads'
down_revision: Union[str, None] = ('012_add_mobile_auth', '017_referral_course_nullable')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
