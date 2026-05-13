"""add questions_per_attempt and proctoring models

Revision ID: 002_add_exam_features
Revises: 001_add_dist_rbac
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '002_add_exam_features'
down_revision = '001_add_dist_rbac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    
    def col_exists(table, col):
        return any(c['name'] == col for c in insp.get_columns(table))

    # 1. Add questions_per_attempt to entrance_exams and course_exams
    if not col_exists('entrance_exams', 'questions_per_attempt'):
        op.add_column('entrance_exams', sa.Column('questions_per_attempt', sa.Integer(), nullable=True))
    if not col_exists('course_exams', 'questions_per_attempt'):
        op.add_column('course_exams', sa.Column('questions_per_attempt', sa.Integer(), nullable=True))

    # 2. Add is_correct to exam_answers and course_exam_answers (if missing)
    if not col_exists('exam_answers', 'is_correct'):
        op.add_column('exam_answers', sa.Column('is_correct', sa.Boolean(), nullable=True))
    if not col_exists('course_exam_answers', 'is_correct'):
        op.add_column('course_exam_answers', sa.Column('is_correct', sa.Boolean(), nullable=True))

    # 3. Create exam_violations table (only if missing)
    if 'exam_violations' not in insp.get_table_names():
        op.create_table(
            'exam_violations',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('course_exam_attempts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('violation_type', sa.String(length=100), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 4. Create category_scores table (only if missing)
    if 'category_scores' not in insp.get_table_names():
        op.create_table(
            'category_scores',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('exam_id', sa.Integer(), sa.ForeignKey('course_exams.id', ondelete='CASCADE'), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('score', sa.Float(), server_default='0.0'),
            sa.Column('max_score', sa.Float(), server_default='100.0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    pass
