"""merge_all_heads

Revision ID: de8dc5db081f
Revises: 009_add_lecture_registrations, 011_add_lecture_recordings, 012_add_is_popular
Create Date: 2026-06-09 13:13:15.494679
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de8dc5db081f'
down_revision: Union[str, None] = ('009_add_lecture_registrations', '011_add_lecture_recordings', '012_add_is_popular')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
