"""add mobile auth and profile columns

Revision ID: 012_add_mobile_auth
Revises: 011_add_lecture_recordings
Create Date: 2026-06-24 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '012_add_mobile_auth'
down_revision = '011_add_lecture_recordings'
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = insp.get_table_names()

    # 1. Add gender and dob to students table if they do not exist
    if 'students' in tables:
        cols = {col['name'] for col in insp.get_columns('students')}
        if 'gender' not in cols:
            op.add_column('students', sa.Column('gender', sa.String(length=50), nullable=True))
        if 'dob' not in cols:
            op.add_column('students', sa.Column('dob', sa.String(length=50), nullable=True))

    # 2. Create mobile_otp_codes table if it does not exist
    if 'mobile_otp_codes' not in tables:
        op.create_table(
            'mobile_otp_codes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('mobile', sa.String(length=20), nullable=False),
            sa.Column('code', sa.String(length=6), nullable=False),
            sa.Column('otp_token', sa.String(length=64), nullable=False),
            sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_mobile_otp_codes_id'), 'mobile_otp_codes', ['id'], unique=False)
        op.create_index(op.f('ix_mobile_otp_codes_mobile'), 'mobile_otp_codes', ['mobile'], unique=False)
        op.create_index(op.f('ix_mobile_otp_codes_otp_token'), 'mobile_otp_codes', ['otp_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_mobile_otp_codes_otp_token'), table_name='mobile_otp_codes')
    op.drop_index(op.f('ix_mobile_otp_codes_mobile'), table_name='mobile_otp_codes')
    op.drop_index(op.f('ix_mobile_otp_codes_id'), table_name='mobile_otp_codes')
    op.drop_table('mobile_otp_codes')

    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = insp.get_table_names()
    if 'students' in tables:
        cols = {col['name'] for col in insp.get_columns('students')}
        if 'gender' in cols:
            op.drop_column('students', 'gender')
        if 'dob' in cols:
            op.drop_column('students', 'dob')
