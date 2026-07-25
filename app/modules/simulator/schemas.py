"""Simulator module — Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────────────────

class SimulatorStartRequest(BaseModel):
    profile_id: Optional[int] = None  # use default profile if None


class TradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ClosePositionRequest(BaseModel):
    position_id: int
    exit_price: Optional[float] = Field(None, gt=0)


class SimulatorProfileUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    initial_balance: float = Field(100000.0, gt=0)
    daily_loss_limit: float = Field(5000.0, gt=0)
    max_drawdown: float = Field(10000.0, gt=0)
    profit_target: float = Field(10000.0, gt=0)
    risk_per_trade: float = Field(1.0, gt=0)
    max_open_trades: int = Field(5, gt=0)
    max_position_size: float = Field(50000.0, gt=0)
    commission: float = Field(0.0, ge=0)
    spread: float = Field(0.0, ge=0)
    slippage: float = Field(0.0, ge=0)
    trading_hours_start: str = "09:15"
    trading_hours_end: str = "15:30"
    allowed_markets: Optional[List[str]] = None
    stop_loss_required: bool = True
    is_active: bool = True


class MarketDataRequest(BaseModel):
    symbols: List[str] = Field(..., min_length=1, max_length=20)


class CandleRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    interval: str = "1day"
    outputsize: int = Field(100, ge=1, le=5000)


# ── Responses ────────────────────────────────────────────────────────

class SimulatorAccountResponse(BaseModel):
    id: int
    user_id: int
    profile_id: Optional[int] = None
    balance: float
    initial_balance: float
    equity: float = 0.0
    buying_power: float = 0.0
    peak_equity: float = 0.0
    daily_realized_pnl: float = 0.0
    challenge_status: str = "active"
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeResponse(BaseModel):
    id: int
    account_id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    commission: float = 0.0
    pnl: Optional[float] = None
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: int
    account_id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: Optional[float] = None
    unrealized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: datetime

    model_config = {"from_attributes": True}


class SimulatorProfileResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    initial_balance: float
    daily_loss_limit: float
    max_drawdown: float = 0.0
    profit_target: float = 0.0
    risk_per_trade: float = 0.0
    max_open_trades: int = 0
    max_position_size: float
    commission: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    trading_hours_start: str = "09:15"
    trading_hours_end: str = "15:30"
    allowed_markets: Optional[List[str]] = None
    stop_loss_required: bool
    is_active: bool

    model_config = {"from_attributes": True}


class PerformanceResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    risk_score: float
    consistency_score: float
    computed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


class MarketQuoteResponse(BaseModel):
    symbol: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    tv_symbol: Optional[str] = None
    timestamp: Optional[Any] = None


class WalletResponse(BaseModel):
    cash_balance: float
    equity: float
    buying_power: float
    realized_pnl: float
    unrealized_pnl: float

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    account: SimulatorAccountResponse
    wallet: WalletResponse
    open_positions: List[PositionResponse]
    closed_trades: List[TradeResponse]
    order_history: List[Dict[str, Any]]
    performance: Dict[str, Any]


class AdminMonitorResponse(BaseModel):
    live_trades: List[Dict[str, Any]]
    open_positions: List[Dict[str, Any]]
    closed_positions: List[Dict[str, Any]]
    wallet_balances: List[Dict[str, Any]]
    student_rankings: List[Dict[str, Any]]
    violations: List[Dict[str, Any]]
    challenge_status: List[Dict[str, Any]]
    trade_logs: List[Dict[str, Any]]


class ReportResponse(BaseModel):
    period: str
    generated_at: datetime
    summary: Dict[str, Any]
    rows: List[Dict[str, Any]]


# ── Watchlist Schemas ────────────────────────────────────────────────
class WatchlistAddRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None
    exchange: Optional[str] = "NSE"
    tv_symbol: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    name: Optional[str] = None
    exchange: str
    tv_symbol: Optional[str] = None
    added_at: datetime

    model_config = {"from_attributes": True}


# ── User Settings Schemas ────────────────────────────────────────────
class UserSettingsUpdateRequest(BaseModel):
    default_timeframe: Optional[str] = "1m"
    chart_theme: Optional[str] = "light"
    default_quantity: Optional[float] = 50.0
    beginner_mode: Optional[bool] = True
    active_strategy_id: Optional[int] = None


class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    default_timeframe: str
    chart_theme: str
    default_quantity: float
    beginner_mode: bool
    active_strategy_id: Optional[int] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Trading Journal Schemas ──────────────────────────────────────────
class JournalCreateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell)$")
    trade_id: Optional[int] = None
    pnl: Optional[float] = 0.0
    notes: Optional[str] = None
    emotion: str = "disciplined"
    rating: int = Field(3, ge=1, le=5)
    tags: Optional[List[str]] = None


class JournalUpdateRequest(BaseModel):
    notes: Optional[str] = None
    emotion: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    tags: Optional[List[str]] = None


class JournalResponse(BaseModel):
    id: int
    user_id: int
    trade_id: Optional[int] = None
    symbol: str
    side: str
    pnl: float
    notes: Optional[str] = None
    emotion: str
    rating: int
    ai_review: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Strategy Schemas ─────────────────────────────────────────────────
class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    entry_rules: Optional[str] = None
    exit_rules: Optional[str] = None
    timeframe: str = "1day"


class StrategyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    entry_rules: Optional[str] = None
    exit_rules: Optional[str] = None
    timeframe: str
    win_rate: float
    profit_factor: float
    backtest_results: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Position / Risk Calculator Schemas ───────────────────────────────
class PositionSizeCalcRequest(BaseModel):
    account_balance: float = Field(..., gt=0)
    risk_percentage: float = Field(..., gt=0, le=100)
    entry_price: float = Field(..., gt=0)
    stop_loss_price: float = Field(..., gt=0)


class PositionSizeCalcResponse(BaseModel):
    recommended_shares: int
    recommended_position_value: float
    monetary_risk_amount: float
    risk_reward_ratio: Optional[float] = None


# ── Advanced Analytics Schemas ───────────────────────────────────────
class AdvancedAnalyticsResponse(BaseModel):
    win_rate: float
    loss_rate: float
    profit_factor: float
    average_profit: float
    average_loss: float
    largest_winner: float
    largest_loser: float
    max_drawdown: float
    sharpe_ratio: float
    equity_curve: List[Dict[str, Any]]
    monthly_pnl: List[Dict[str, Any]]
    emotion_breakdown: Dict[str, int]
    total_trades: int

