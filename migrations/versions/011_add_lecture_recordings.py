"""add lecture_recordings and missing lecture columns

Revision ID: 011_add_lecture_recordings
Revises: 010_add_user_city
Create Date: 2026-06-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '011_add_lecture_recordings'
down_revision = '010_add_user_city'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = insp.get_table_names()

    # 1. Create lecture_recordings table if not exists
    if 'lecture_recordings' not in tables:
        op.create_table(
            'lecture_recordings',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('lecture_id', sa.Integer(), sa.ForeignKey('lectures.id', ondelete='CASCADE'), nullable=False),
            sa.Column('recording_url', sa.Text(), nullable=False),
            sa.Column('duration_seconds', sa.Integer(), nullable=True),
            sa.Column('file_size_mb', sa.Integer(), nullable=True),
            sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        )

    # 2. Add missing columns to lectures table
    if 'lectures' in tables:
        cols = {col['name'] for col in insp.get_columns('lectures')}
        if 'is_live' not in cols:
            op.add_column('lectures', sa.Column('is_live', sa.Boolean(), server_default='false', nullable=False))
        if 'is_completed' not in cols:
            op.add_column('lectures', sa.Column('is_completed', sa.Boolean(), server_default='false', nullable=False))
        if 'max_participants' not in cols:
            op.add_column('lectures', sa.Column('max_participants', sa.Integer(), server_default='0', nullable=False))
        if 'meeting_link' not in cols:
            op.add_column('lectures', sa.Column('meeting_link', sa.Text(), nullable=True))
        if 'duration_minutes' not in cols:
            op.add_column('lectures', sa.Column('duration_minutes', sa.Integer(), server_default='60', nullable=False))
        if 'instructor_id' not in cols:
            op.add_column('lectures', sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

def downgrade() -> None:
    op.drop_table('lecture_recordings')
