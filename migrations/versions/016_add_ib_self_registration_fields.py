"""add ib self registration fields

Revision ID: 016_ib_self_registration
Revises: 015_add_referral_leads
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_ib_self_registration"
down_revision: Union[str, None] = "015_add_referral_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in insp.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("distributors"):
        return

    additions = [
        ("profile_photo_url", sa.Column("profile_photo_url", sa.Text(), nullable=True)),
        ("aadhaar_card_url", sa.Column("aadhaar_card_url", sa.Text(), nullable=True)),
        ("pan_card_url", sa.Column("pan_card_url", sa.Text(), nullable=True)),
        ("bank_account_holder_name", sa.Column("bank_account_holder_name", sa.String(length=255), nullable=True)),
        ("bank_name", sa.Column("bank_name", sa.String(length=255), nullable=True)),
        ("bank_account_number", sa.Column("bank_account_number", sa.String(length=100), nullable=True)),
        ("bank_ifsc_code", sa.Column("bank_ifsc_code", sa.String(length=50), nullable=True)),
        ("bank_upi_id", sa.Column("bank_upi_id", sa.String(length=255), nullable=True)),
        ("self_registered", sa.Column("self_registered", sa.String(length=10), nullable=False, server_default="no")),
        ("verification_status", sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="approved")),
    ]
    for column_name, column in additions:
        if not _has_column(insp, "distributors", column_name):
            op.add_column("distributors", column)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("distributors"):
        return

    for column_name in (
        "verification_status",
        "self_registered",
        "bank_upi_id",
        "bank_ifsc_code",
        "bank_account_number",
        "bank_name",
        "bank_account_holder_name",
        "pan_card_url",
        "aadhaar_card_url",
        "profile_photo_url",
    ):
        if _has_column(insp, "distributors", column_name):
            op.drop_column("distributors", column_name)
