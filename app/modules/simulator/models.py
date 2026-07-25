"""Simulator module — database models for trading simulator."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class SimulatorProfile(Base):
    """Prop-firm style profile with configurable rules."""
    __tablename__ = "simulator_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    initial_balance = Column(Float, default=100000.0)
    daily_loss_limit = Column(Float, default=5000.0)
    max_drawdown = Column(Float, default=10000.0)
    profit_target = Column(Float, default=10000.0)
    risk_per_trade = Column(Float, default=1.0)
    max_open_trades = Column(Integer, default=5)
    max_position_size = Column(Float, default=50000.0)
    commission = Column(Float, default=0.0)
    spread = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    trading_hours_start = Column(String(5), default="09:15")
    trading_hours_end = Column(String(5), default="15:30")
    allowed_markets = Column(JSON, nullable=True)
    stop_loss_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SimulatorProfile {self.name}>"


class SimulatorAccount(Base):
    """Virtual trading account for a student."""
    __tablename__ = "simulator_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(Integer, ForeignKey("simulator_profiles.id"), nullable=True)
    balance = Column(Float, default=100000.0)
    initial_balance = Column(Float, default=100000.0)
    equity = Column(Float, default=100000.0)
    buying_power = Column(Float, default=100000.0)
    peak_equity = Column(Float, default=100000.0)
    daily_realized_pnl = Column(Float, default=0.0)
    challenge_status = Column(String(30), default="active")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    trades = relationship("Trade", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    wallet = relationship("Wallet", back_populates="account", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SimulatorAccount user={self.user_id} balance={self.balance}>"


class Trade(Base):
    """Completed or active trade record."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    commission = Column(Float, default=0.0)
    pnl = Column(Float, nullable=True)
    status = Column(String(20), default="open")  # open, closed
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # relationships
    account = relationship("SimulatorAccount", back_populates="trades")

    def __repr__(self):
        return f"<Trade {self.symbol} {self.side} qty={self.quantity}>"


class Position(Base):
    """Currently open position."""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    account = relationship("SimulatorAccount", back_populates="positions")

    def __repr__(self):
        return f"<Position {self.symbol} {self.side} qty={self.quantity}>"


class Order(Base):
    """Order record (market/limit)."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), default="market")  # market, limit
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    status = Column(String(20), default="filled")  # pending, filled, cancelled
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    account = relationship("SimulatorAccount", back_populates="orders")

    def __repr__(self):
        return f"<Order {self.symbol} {self.side} {self.order_type}>"


class RiskRule(Base):
    """Configurable risk rules per profile."""
    __tablename__ = "risk_rules"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("simulator_profiles.id", ondelete="CASCADE"), nullable=False)
    rule_type = Column(String(50), nullable=False)  # daily_loss_limit, max_position_size, stop_loss_required
    value = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<RiskRule {self.rule_type}={self.value}>"


class Wallet(Base):
    """Virtual wallet snapshot for a simulator account."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    cash_balance = Column(Float, default=100000.0)
    equity = Column(Float, default=100000.0)
    buying_power = Column(Float, default=100000.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("SimulatorAccount", back_populates="wallet")


class TradeLog(Base):
    """Immutable audit trail for every simulator action."""
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=True)
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChallengeResult(Base):
    """Current challenge evaluation result for a simulator account."""
    __tablename__ = "challenge_results"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(String(30), default="active")
    profit_target_hit = Column(Boolean, default=False)
    daily_loss_breached = Column(Boolean, default=False)
    max_drawdown_breached = Column(Boolean, default=False)
    violations = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SimulatorNotification(Base):
    """Simulator-specific student/admin notification."""
    __tablename__ = "simulator_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=True)
    level = Column(String(20), default="info")
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StudentPerformance(Base):
    """Daily student performance snapshots for reporting."""
    __tablename__ = "student_performance"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    period = Column(String(20), default="daily")
    starting_equity = Column(Float, default=0.0)
    ending_equity = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    violations = Column(JSON, nullable=True)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PerformanceMetric(Base):
    """Computed performance analytics for an account."""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("simulator_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    risk_score = Column(Float, default=50.0)  # 0-100, lower is better
    consistency_score = Column(Float, default=50.0)  # 0-100, higher is better
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<PerformanceMetric account={self.account_id} pnl={self.total_pnl}>"


class SimulatorWatchlist(Base):
    """Persistent user watchlist for paper trading simulator."""
    __tablename__ = "simulator_watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=True)
    exchange = Column(String(20), default="NSE")
    tv_symbol = Column(String(50), nullable=True)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_user_simulator_watchlist_symbol"),
    )

    def __repr__(self):
        return f"<SimulatorWatchlist user={self.user_id} symbol={self.symbol}>"


class SimulatorUserSettings(Base):
    """User-level simulator preferences and configurations."""
    __tablename__ = "simulator_user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    default_timeframe = Column(String(10), default="1m")
    chart_theme = Column(String(20), default="light")
    default_quantity = Column(Float, default=50.0)
    beginner_mode = Column(Boolean, default=True)
    active_strategy_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SimulatorUserSettings user={self.user_id} timeframe={self.default_timeframe}>"


class TradingJournalEntry(Base):
    """Student trading journal entries with notes, emotions, and AI reviews."""
    __tablename__ = "trading_journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    pnl = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    emotion = Column(String(30), default="disciplined")  # confident, fearful, greedy, fomo, disciplined, patient
    rating = Column(Integer, default=3)  # 1 to 5 stars
    ai_review = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TradingJournalEntry id={self.id} symbol={self.symbol} rating={self.rating}>"


class TradingStrategy(Base):
    """Student or instructor trading strategies for educational backtesting."""
    __tablename__ = "trading_strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    entry_rules = Column(Text, nullable=True)
    exit_rules = Column(Text, nullable=True)
    timeframe = Column(String(10), default="1day")
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=1.0)
    backtest_results = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TradingStrategy id={self.id} name={self.name}>"


class PriceAlert(Base):
    """User price alerts for real-time notification simulation."""
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    target_price = Column(Float, nullable=False)
    condition = Column(String(20), default="above")  # above, below
    is_triggered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<PriceAlert user={self.user_id} symbol={self.symbol} target={self.target_price}>"
