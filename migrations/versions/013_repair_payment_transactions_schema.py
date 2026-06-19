"""repair payment transactions schema

Revision ID: 013_repair_payment_transactions
Revises: df05f2889739
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "013_repair_payment_transactions"
down_revision: Union[str, None] = "df05f2889739"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("payment_transactions"):
        return

    columns = {column["name"] for column in insp.get_columns("payment_transactions")}
    json_type = postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()

    if "easepayid" not in columns:
        op.add_column("payment_transactions", sa.Column("easepayid", sa.String(length=100), nullable=True))
    if "payment_mode" not in columns:
        op.add_column("payment_transactions", sa.Column("payment_mode", sa.String(length=50), nullable=True))
    if "coupon_code" not in columns:
        op.add_column("payment_transactions", sa.Column("coupon_code", sa.String(length=100), nullable=True))
    if "gateway_response" not in columns:
        op.add_column("payment_transactions", sa.Column("gateway_response", json_type, nullable=True))
    if "updated_at" not in columns:
        op.add_column("payment_transactions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("payment_transactions"):
        return

    columns = {column["name"] for column in insp.get_columns("payment_transactions")}
    for column_name in ("updated_at", "gateway_response", "coupon_code", "payment_mode", "easepayid"):
        if column_name in columns:
            op.drop_column("payment_transactions", column_name)
