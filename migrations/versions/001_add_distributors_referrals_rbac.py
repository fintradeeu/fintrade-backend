"""add distributors referrals and rbac columns

Revision ID: 001_add_dist_rbac
Revises: (initial)
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001_add_dist_rbac'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    
    def col_exists(table, col):
        return any(c['name'] == col for c in insp.get_columns(table))

    # ── Add created_by to users ──────────────────────────────────────
    if not col_exists('users', 'created_by'):
        op.add_column('users', sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

    # ── Add columns to offers ────────────────────────────────────────
    if not col_exists('offers', 'created_by_admin'):
        op.add_column('offers', sa.Column('created_by_admin', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    if not col_exists('offers', 'distributor_id'):
        op.add_column('offers', sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id', ondelete='SET NULL'), nullable=True))

    # ── Add columns to course_enrollments ────────────────────────────
    if not col_exists('course_enrollments', 'discount_applied'):
        op.add_column('course_enrollments', sa.Column('discount_applied', sa.Float(), server_default='0.0', nullable=True))
    if not col_exists('course_enrollments', 'price_paid'):
        op.add_column('course_enrollments', sa.Column('price_paid', sa.Float(), nullable=True))
    if not col_exists('course_enrollments', 'distributor_id'):
        op.add_column('course_enrollments', sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    # Downgrades are generally not needed for sync fixes, but kept for structure
    pass
