"""Make lectures.course_id nullable

Revision ID: 003_lecture_course_nullable
Revises: 002_add_exam_features
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '003_lecture_course_nullable'
down_revision = '002_add_exam_features'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make course_id nullable so lectures can exist without a course
    op.alter_column('lectures', 'course_id',
                    existing_type=sa.Integer(),
                    nullable=True)
    
    # Drop the old CASCADE foreign key and recreate with SET NULL
    op.drop_constraint('lectures_course_id_fkey', 'lectures', type_='foreignkey')
    op.create_foreign_key(
        'lectures_course_id_fkey',
        'lectures', 'courses',
        ['course_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Revert to NOT NULL with CASCADE
    op.drop_constraint('lectures_course_id_fkey', 'lectures', type_='foreignkey')
    op.create_foreign_key(
        'lectures_course_id_fkey',
        'lectures', 'courses',
        ['course_id'], ['id'],
        ondelete='CASCADE'
    )
    op.alter_column('lectures', 'course_id',
                    existing_type=sa.Integer(),
                    nullable=False)
