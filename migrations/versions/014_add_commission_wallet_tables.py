"""add commission wallet tables

Revision ID: 014_add_commission_wallet_tables
Revises: 013_repair_payment_transactions
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_add_commission_wallet_tables"
down_revision: Union[str, None] = "013_repair_payment_transactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("course_ib_commissions"):
        op.create_table(
            "course_ib_commissions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("ib_id", sa.Integer(), nullable=False),
            sa.Column("commission_type", sa.String(length=20), nullable=False, server_default="percentage"),
            sa.Column("commission_value", sa.Float(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["ib_id"], ["distributors.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("course_id", "ib_id", name="uq_course_ib_commission"),
        )
        op.create_index("ix_course_ib_commissions_id", "course_ib_commissions", ["id"])

    if not insp.has_table("ib_wallets"):
        op.create_table(
            "ib_wallets",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("ib_id", sa.Integer(), nullable=False),
            sa.Column("available_balance", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_earned", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_withdrawn", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["ib_id"], ["distributors.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("ib_id", name="uq_ib_wallets_ib_id"),
        )
        op.create_index("ix_ib_wallets_id", "ib_wallets", ["id"])

    if not insp.has_table("wallet_transactions"):
        op.create_table(
            "wallet_transactions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("ib_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("course_id", sa.Integer(), nullable=True),
            sa.Column("commission_amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("transaction_type", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("reference_no", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("balance_after", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["ib_id"], ["distributors.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("reference_no", name="uq_wallet_transactions_reference_no"),
        )
        op.create_index("ix_wallet_transactions_id", "wallet_transactions", ["id"])
        op.create_index("ix_wallet_transactions_reference_no", "wallet_transactions", ["reference_no"])

    if not insp.has_table("withdrawal_requests"):
        op.create_table(
            "withdrawal_requests",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("ib_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("withdrawal_method", sa.String(length=30), nullable=False),
            sa.Column("account_holder_name", sa.String(length=255), nullable=True),
            sa.Column("bank_name", sa.String(length=255), nullable=True),
            sa.Column("account_number", sa.String(length=100), nullable=True),
            sa.Column("ifsc_code", sa.String(length=50), nullable=True),
            sa.Column("upi_id", sa.String(length=255), nullable=True),
            sa.Column("qr_code_image", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("admin_remarks", sa.Text(), nullable=True),
            sa.Column("payment_proof", sa.Text(), nullable=True),
            sa.Column("wallet_transaction_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["ib_id"], ["distributors.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wallet_transaction_id"], ["wallet_transactions.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_withdrawal_requests_id", "withdrawal_requests", ["id"])

    if not insp.has_table("payment_proofs"):
        op.create_table(
            "payment_proofs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("withdrawal_request_id", sa.Integer(), nullable=False),
            sa.Column("utr_number", sa.String(length=100), nullable=True),
            sa.Column("transaction_reference", sa.String(length=150), nullable=True),
            sa.Column("proof_file", sa.Text(), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["withdrawal_request_id"], ["withdrawal_requests.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_payment_proofs_id", "payment_proofs", ["id"])

    if not insp.has_table("commission_audit_logs"):
        op.create_table(
            "commission_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_commission_audit_logs_id", "commission_audit_logs", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table_name in (
        "commission_audit_logs",
        "payment_proofs",
        "withdrawal_requests",
        "wallet_transactions",
        "ib_wallets",
        "course_ib_commissions",
    ):
        if insp.has_table(table_name):
            op.drop_table(table_name)
