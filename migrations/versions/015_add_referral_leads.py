"""add referral leads

Revision ID: 015_add_referral_leads
Revises: 014_add_commission_wallet_tables
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_add_referral_leads"
down_revision: Union[str, None] = "014_add_commission_wallet_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("referral_leads"):
        return

    op.create_table(
        "referral_leads",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("distributor_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("referral_code", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("mobile_no", sa.String(length=50), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["distributor_id"], ["distributors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_referral_leads_id", "referral_leads", ["id"])
    op.create_index("ix_referral_leads_referral_code", "referral_leads", ["referral_code"])
    op.create_index("ix_referral_leads_email", "referral_leads", ["email"])
    op.create_index("ix_referral_leads_mobile_no", "referral_leads", ["mobile_no"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("referral_leads"):
        op.drop_table("referral_leads")
