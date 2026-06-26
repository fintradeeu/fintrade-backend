"""add google event id to lectures

Revision ID: 019_google_meet
Revises: 018_merge_all_heads
Create Date: 2026-06-26 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '019_google_meet'
down_revision: Union[str, None] = '018_merge_all_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'lectures' in insp.get_table_names():
        cols = {col['name'] for col in insp.get_columns('lectures')}
        if 'google_event_id' not in cols:
            op.add_column('lectures', sa.Column('google_event_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('lectures', 'google_event_id')
