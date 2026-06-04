"""add_feedback_forms

Revision ID: 621bf7ebb607
Revises: 008_add_user_permissions
Create Date: 2026-06-04 07:25:33.207830
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '621bf7ebb607'
down_revision: Union[str, None] = '008_add_user_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Create feedback_forms table if it does not exist
    if 'feedback_forms' not in tables:
        op.create_table(
            'feedback_forms',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(length=36), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('course_id', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_feedback_forms_id'), 'feedback_forms', ['id'], unique=False)
        op.create_index(op.f('ix_feedback_forms_token'), 'feedback_forms', ['token'], unique=True)
        # Refresh tables list
        tables.append('feedback_forms')
    else:
        feedback_forms_cols = {col['name'] for col in insp.get_columns('feedback_forms')}
        if 'token' not in feedback_forms_cols:
            op.add_column('feedback_forms', sa.Column('token', sa.String(length=36), nullable=True))
            op.create_index(op.f('ix_feedback_forms_token'), 'feedback_forms', ['token'], unique=True)


    # 2. Add columns to feedback table if they do not exist
    if 'feedback' in tables:
        feedback_cols = {col['name'] for col in insp.get_columns('feedback')}
        if 'form_id' not in feedback_cols:
            op.add_column('feedback', sa.Column('form_id', sa.Integer(), nullable=True))
        if 'full_name' not in feedback_cols:
            op.add_column('feedback', sa.Column('full_name', sa.String(length=255), nullable=True))
        if 'email' not in feedback_cols:
            op.add_column('feedback', sa.Column('email', sa.String(length=255), nullable=True))
        if 'show_on_landing_page' not in feedback_cols:
            op.add_column('feedback', sa.Column('show_on_landing_page', sa.Boolean(), nullable=True))

        # Alter user_id to be nullable
        cols = insp.get_columns('feedback')
        user_id_col = next((c for c in cols if c['name'] == 'user_id'), None)
        if user_id_col and not user_id_col['nullable']:
            op.alter_column('feedback', 'user_id',
                       existing_type=sa.INTEGER(),
                       nullable=True)

        # Create foreign key for form_id if not present
        fks = insp.get_foreign_keys('feedback')
        has_form_fk = any(fk['referred_table'] == 'feedback_forms' for fk in fks)
        if not has_form_fk:
            op.create_foreign_key('fk_feedback_form_id', 'feedback', 'feedback_forms', ['form_id'], ['id'], ondelete='SET NULL')

    # 3. Add column to course_exams if it does not exist
    if 'course_exams' in tables:
        course_exams_cols = {col['name'] for col in insp.get_columns('course_exams')}
        if 'reattempt_fee' not in course_exams_cols:
            op.add_column('course_exams', sa.Column('reattempt_fee', sa.Float(), nullable=True))

    # 4. Alter admin_permissions admin_role column type if not already varchar
    if 'admin_permissions' in tables:
        cols = insp.get_columns('admin_permissions')
        admin_role_col = next((c for c in cols if c['name'] == 'admin_role'), None)
        if admin_role_col and not isinstance(admin_role_col['type'], sa.String):
            op.alter_column('admin_permissions', 'admin_role',
                       existing_type=postgresql.ENUM('super_admin', 'content_admin', 'finance_admin', 'support_admin', name='admin_role_type'),
                       type_=sa.String(length=50),
                       existing_nullable=False)

    # 5. Alter news_articles views_count nullable constraint if needed
    if 'news_articles' in tables:
        cols = insp.get_columns('news_articles')
        views_count_col = next((c for c in cols if c['name'] == 'views_count'), None)
        if views_count_col and views_count_col['nullable']:
            op.alter_column('news_articles', 'views_count',
                       existing_type=sa.INTEGER(),
                       nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'feedback' in tables:
        feedback_cols = {col['name'] for col in insp.get_columns('feedback')}
        fks = insp.get_foreign_keys('feedback')
        has_form_fk = any(fk['referred_table'] == 'feedback_forms' for fk in fks)
        if has_form_fk:
            op.drop_constraint('fk_feedback_form_id', 'feedback', type_='foreignkey')

        if 'form_id' in feedback_cols:
            op.drop_column('feedback', 'form_id')
        if 'full_name' in feedback_cols:
            op.drop_column('feedback', 'full_name')
        if 'email' in feedback_cols:
            op.drop_column('feedback', 'email')
        if 'show_on_landing_page' in feedback_cols:
            op.drop_column('feedback', 'show_on_landing_page')

        cols = insp.get_columns('feedback')
        user_id_col = next((c for c in cols if c['name'] == 'user_id'), None)
        if user_id_col and user_id_col['nullable']:
            op.alter_column('feedback', 'user_id',
                       existing_type=sa.INTEGER(),
                       nullable=False)

    if 'feedback_forms' in tables:
        op.drop_index(op.f('ix_feedback_forms_token'), table_name='feedback_forms')
        op.drop_index(op.f('ix_feedback_forms_id'), table_name='feedback_forms')
        op.drop_table('feedback_forms')
