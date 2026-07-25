"""add_simulator_features and merge heads

Revision ID: e01f2889740
Revises: df05f2889739, b27aa4a0eb6d, 60f574e19344, 3abe91512295, 621bf7ebb607
Create Date: 2026-07-25 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e01f2889740'
down_revision: Union[str, Sequence[str], None] = ('df05f2889739', 'b27aa4a0eb6d', '60f574e19344', '3abe91512295', '621bf7ebb607')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("simulator_watchlists"):
        op.create_table(
            "simulator_watchlists",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
            sa.Column("name", sa.String(length=100), nullable=True),
            sa.Column("exchange", sa.String(length=20), server_default="NSE", nullable=True),
            sa.Column("tv_symbol", sa.String(length=50), nullable=True),
            sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.UniqueConstraint("user_id", "symbol", name="uq_user_simulator_watchlist_symbol"),
        )

    if not insp.has_table("simulator_user_settings"):
        op.create_table(
            "simulator_user_settings",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("default_timeframe", sa.String(length=10), server_default="1m", nullable=True),
            sa.Column("chart_theme", sa.String(length=20), server_default="light", nullable=True),
            sa.Column("default_quantity", sa.Float(), server_default="50.0", nullable=True),
            sa.Column("beginner_mode", sa.Boolean(), server_default=sa.text("true"), nullable=True),
            sa.Column("active_strategy_id", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )

    if not insp.has_table("trading_journal_entries"):
        op.create_table(
            "trading_journal_entries",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trades.id", ondelete="SET NULL"), nullable=True),
            sa.Column("symbol", sa.String(length=20), nullable=False),
            sa.Column("side", sa.String(length=10), nullable=False),
            sa.Column("pnl", sa.Float(), server_default="0.0", nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("emotion", sa.String(length=30), server_default="disciplined", nullable=True),
            sa.Column("rating", sa.Integer(), server_default="3", nullable=True),
            sa.Column("ai_review", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )

    if not insp.has_table("trading_strategies"):
        op.create_table(
            "trading_strategies",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("entry_rules", sa.Text(), nullable=True),
            sa.Column("exit_rules", sa.Text(), nullable=True),
            sa.Column("timeframe", sa.String(length=10), server_default="1day", nullable=True),
            sa.Column("win_rate", sa.Float(), server_default="0.0", nullable=True),
            sa.Column("profit_factor", sa.Float(), server_default="1.0", nullable=True),
            sa.Column("backtest_results", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )

    if not insp.has_table("price_alerts"):
        op.create_table(
            "price_alerts",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("symbol", sa.String(length=20), nullable=False),
            sa.Column("target_price", sa.Float(), nullable=False),
            sa.Column("condition", sa.String(length=20), server_default="above", nullable=True),
            sa.Column("is_triggered", sa.Boolean(), server_default=sa.text("false"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    pass
