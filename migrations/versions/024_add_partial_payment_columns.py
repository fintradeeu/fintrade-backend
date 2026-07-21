"""Add partial payment columns to course_enrollments and student_batch_enrollments

Revision ID: 024
Revises: 023
Create Date: 2026-07-21 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '024'
down_revision: Union[str, None] = '023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add partial payment columns to course_enrollments
    op.add_column('course_enrollments', sa.Column(
        'payment_status', sa.String(50), nullable=False, server_default='full'
    ))
    op.add_column('course_enrollments', sa.Column(
        'allowed_modules', sa.JSON(), nullable=True
    ))
    op.add_column('course_enrollments', sa.Column(
        'payment_due_date', sa.DateTime(timezone=True), nullable=True
    ))

    # Add partial payment columns to student_batch_enrollments
    op.add_column('student_batch_enrollments', sa.Column(
        'payment_status', sa.String(50), nullable=False, server_default='full'
    ))
    op.add_column('student_batch_enrollments', sa.Column(
        'allowed_modules', sa.JSON(), nullable=True
    ))
    op.add_column('student_batch_enrollments', sa.Column(
        'payment_due_date', sa.DateTime(timezone=True), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('student_batch_enrollments', 'payment_due_date')
    op.drop_column('student_batch_enrollments', 'allowed_modules')
    op.drop_column('student_batch_enrollments', 'payment_status')
    op.drop_column('course_enrollments', 'payment_due_date')
    op.drop_column('course_enrollments', 'allowed_modules')
    op.drop_column('course_enrollments', 'payment_status')
