"""trading simulator twelve data

Revision ID: 020_trading_sim_twelve_data
Revises: 019_google_meet
Create Date: 2026-06-27 01:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020_trading_sim_twelve_data"
down_revision: Union[str, None] = "019_google_meet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table_name):
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if insp.has_table("simulator_profiles"):
        _add_column("simulator_profiles", sa.Column("max_drawdown", sa.Float(), nullable=True, server_default="10000"))
        _add_column("simulator_profiles", sa.Column("profit_target", sa.Float(), nullable=True, server_default="10000"))
        _add_column("simulator_profiles", sa.Column("risk_per_trade", sa.Float(), nullable=True, server_default="1"))
        _add_column("simulator_profiles", sa.Column("max_open_trades", sa.Integer(), nullable=True, server_default="5"))
        _add_column("simulator_profiles", sa.Column("commission", sa.Float(), nullable=True, server_default="0"))
        _add_column("simulator_profiles", sa.Column("spread", sa.Float(), nullable=True, server_default="0"))
        _add_column("simulator_profiles", sa.Column("slippage", sa.Float(), nullable=True, server_default="0"))
        _add_column("simulator_profiles", sa.Column("trading_hours_start", sa.String(length=5), nullable=True, server_default="09:15"))
        _add_column("simulator_profiles", sa.Column("trading_hours_end", sa.String(length=5), nullable=True, server_default="15:30"))
        _add_column("simulator_profiles", sa.Column("allowed_markets", sa.JSON(), nullable=True))

    if insp.has_table("simulator_accounts"):
        _add_column("simulator_accounts", sa.Column("equity", sa.Float(), nullable=True, server_default="100000"))
        _add_column("simulator_accounts", sa.Column("buying_power", sa.Float(), nullable=True, server_default="100000"))
        _add_column("simulator_accounts", sa.Column("peak_equity", sa.Float(), nullable=True, server_default="100000"))
        _add_column("simulator_accounts", sa.Column("daily_realized_pnl", sa.Float(), nullable=True, server_default="0"))
        _add_column("simulator_accounts", sa.Column("challenge_status", sa.String(length=30), nullable=True, server_default="active"))

    if insp.has_table("trades"):
        _add_column("trades", sa.Column("stop_loss", sa.Float(), nullable=True))
        _add_column("trades", sa.Column("take_profit", sa.Float(), nullable=True))
        _add_column("trades", sa.Column("commission", sa.Float(), nullable=True, server_default="0"))

    if insp.has_table("orders"):
        _add_column("orders", sa.Column("stop_loss", sa.Float(), nullable=True))
        _add_column("orders", sa.Column("take_profit", sa.Float(), nullable=True))
        _add_column("orders", sa.Column("rejection_reason", sa.Text(), nullable=True))

    if not insp.has_table("wallets"):
        op.create_table(
            "wallets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("cash_balance", sa.Float(), nullable=True),
            sa.Column("equity", sa.Float(), nullable=True),
            sa.Column("buying_power", sa.Float(), nullable=True),
            sa.Column("realized_pnl", sa.Float(), nullable=True),
            sa.Column("unrealized_pnl", sa.Float(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["simulator_accounts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("account_id"),
        )
        op.create_index(op.f("ix_wallets_id"), "wallets", ["id"], unique=False)

    if not insp.has_table("trade_logs"):
        op.create_table(
            "trade_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("symbol", sa.String(length=20), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["simulator_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_trade_logs_id"), "trade_logs", ["id"], unique=False)

    if not insp.has_table("challenge_results"):
        op.create_table(
            "challenge_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=True),
            sa.Column("profit_target_hit", sa.Boolean(), nullable=True),
            sa.Column("daily_loss_breached", sa.Boolean(), nullable=True),
            sa.Column("max_drawdown_breached", sa.Boolean(), nullable=True),
            sa.Column("violations", sa.JSON(), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["simulator_accounts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("account_id"),
        )
        op.create_index(op.f("ix_challenge_results_id"), "challenge_results", ["id"], unique=False)

    if not insp.has_table("simulator_notifications"):
        op.create_table(
            "simulator_notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=True),
            sa.Column("level", sa.String(length=20), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["simulator_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_simulator_notifications_id"), "simulator_notifications", ["id"], unique=False)

    if not insp.has_table("student_performance"):
        op.create_table(
            "student_performance",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("period", sa.String(length=20), nullable=True),
            sa.Column("starting_equity", sa.Float(), nullable=True),
            sa.Column("ending_equity", sa.Float(), nullable=True),
            sa.Column("realized_pnl", sa.Float(), nullable=True),
            sa.Column("unrealized_pnl", sa.Float(), nullable=True),
            sa.Column("total_trades", sa.Integer(), nullable=True),
            sa.Column("violations", sa.JSON(), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["account_id"], ["simulator_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_student_performance_id"), "student_performance", ["id"], unique=False)


def downgrade() -> None:
    for table in ["student_performance", "simulator_notifications", "challenge_results", "trade_logs", "wallets"]:
        op.drop_table(table)
