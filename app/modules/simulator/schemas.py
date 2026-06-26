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
