"""add_ai_tables

Revision ID: df05f2889739
Revises: de8dc5db081f
Create Date: 2026-06-17 11:35:36.691770
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df05f2889739'
down_revision: Union[str, None] = 'de8dc5db081f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)

    # 1. Create doubt_categories table
    if not insp.has_table('doubt_categories'):
        op.create_table(
            'doubt_categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_doubt_categories_id'), 'doubt_categories', ['id'], unique=False)

    # 2. Create faq_entries table
    if not insp.has_table('faq_entries'):
        op.create_table(
            'faq_entries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('question', sa.Text(), nullable=False),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('category_id', sa.Integer(), nullable=True),
            sa.Column('course_id', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('frequency', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['category_id'], ['doubt_categories.id'], ),
            sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_faq_entries_id'), 'faq_entries', ['id'], unique=False)

    # 3. Create chat_sessions table
    if not insp.has_table('chat_sessions'):
        op.create_table(
            'chat_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_chat_sessions_id'), 'chat_sessions', ['id'], unique=False)

    # 4. Create chat_messages table
    if not insp.has_table('chat_messages'):
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)

    op.alter_column('lecture_registrations', 'one_hour_email_sent',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))


def downgrade() -> None:
    op.alter_column('lecture_registrations', 'one_hour_email_sent',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))

    op.drop_index(op.f('ix_chat_messages_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_chat_sessions_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.drop_index(op.f('ix_faq_entries_id'), table_name='faq_entries')
    op.drop_table('faq_entries')
    op.drop_index(op.f('ix_doubt_categories_id'), table_name='doubt_categories')
    op.drop_table('doubt_categories')
