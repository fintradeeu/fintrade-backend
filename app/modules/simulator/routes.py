"""Simulator module — API routes."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.simulator import schemas, services

router = APIRouter(prefix="/simulator", tags=["Trading Simulator"])

import random

@router.get("/market-data")
async def get_market_data():
    """Simulated randomized live market data feed."""
    base_prices = {
        "NIFTY 50": 58720,
        "BANK NIFTY": 42580,
        "RELIANCE": 2456,
        "HDFC BANK": 1650,
        "TCS": 3800
    }
    
    data = []
    for symbol, base in base_prices.items():
        # Fluctuate by +/- 1%
        fluctuation = base * 0.01 * random.uniform(-1, 1)
        current = round(base + fluctuation, 2)
        change_pct = round((fluctuation / base) * 100, 2)
        volume = f"{random.randint(10, 300)}M"
        data.append({
            "symbol": symbol,
            "price": current,
            "change": change_pct,
            "volume": volume
        })
    return data



@router.post("/start", response_model=schemas.SimulatorAccountResponse, status_code=201)
async def start_simulator(
    req: schemas.SimulatorStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a virtual trading account (requires certification)."""
    account = await services.create_account(db, current_user.id, req.profile_id)
    return schemas.SimulatorAccountResponse.model_validate(account)


@router.post("/trade", response_model=schemas.TradeResponse, status_code=201)
async def open_trade(
    req: schemas.TradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open a new trade (mock price — future: TradingView API)."""
    trade = await services.open_trade(
        db, current_user.id,
        symbol=req.symbol, side=req.side, quantity=req.quantity, price=req.price,
        stop_loss=req.stop_loss, take_profit=req.take_profit,
    )
    return schemas.TradeResponse.model_validate(trade)


@router.post("/close", response_model=schemas.TradeResponse)
async def close_position(
    req: schemas.ClosePositionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Close an open position and realize PnL."""
    trade = await services.close_position(db, current_user.id, req.position_id, req.exit_price)
    return schemas.TradeResponse.model_validate(trade)


@router.get("/positions", response_model=List[schemas.PositionResponse])
async def list_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all open positions."""
    positions = await services.get_positions(db, current_user.id)
    return [schemas.PositionResponse.model_validate(p) for p in positions]


@router.get("/trades", response_model=List[schemas.TradeResponse])
async def list_trades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """View trade history."""
    trades = await services.get_trades(db, current_user.id)
    return [schemas.TradeResponse.model_validate(t) for t in trades]


@router.get("/profiles", response_model=List[schemas.SimulatorProfileResponse])
async def list_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available prop firm simulator profiles."""
    profiles = await services.get_profiles(db)
    return [schemas.SimulatorProfileResponse.model_validate(p) for p in profiles]


@router.get("/performance", response_model=schemas.PerformanceResponse)
async def get_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute and return performance analytics."""
    metric = await services.compute_performance(db, current_user.id)
    return schemas.PerformanceResponse.model_validate(metric)
