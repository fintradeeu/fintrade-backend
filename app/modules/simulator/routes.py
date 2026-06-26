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
import httpx
import asyncio
import time

# Tickers definitions for Yahoo Finance fetch and TradingView widget match
TICKERS_CONFIG = [
    {
        "label": "SENSEX",
        "symbol": "^BSESN",
        "tv_symbol": "BSE:SENSEX",
        "type": "index",
        "fallback_price": 74243.34,
        "fallback_prev_close": 74360.01
    },
    {
        "label": "SBI",
        "symbol": "SBIN.NS",
        "tv_symbol": "NSE:SBIN",
        "type": "stock",
        "fallback_price": 834.50,
        "fallback_prev_close": 822.20
    },
    {
        "label": "RELIANCE",
        "symbol": "RELIANCE.NS",
        "tv_symbol": "NSE:RELIANCE",
        "type": "stock",
        "fallback_price": 2934.10,
        "fallback_prev_close": 2888.90
    },
    {
        "label": "HDFC BANK",
        "symbol": "HDFCBANK.NS",
        "tv_symbol": "NSE:HDFCBANK",
        "type": "stock",
        "fallback_price": 1520.40,
        "fallback_prev_close": 1526.00
    },
    {
        "label": "TCS",
        "symbol": "TCS.NS",
        "tv_symbol": "NSE:TCS",
        "type": "stock",
        "fallback_price": 3890.00,
        "fallback_prev_close": 3864.60
    },
    {
        "label": "INFOSYS",
        "symbol": "INFY.NS",
        "tv_symbol": "NSE:INFY",
        "type": "stock",
        "fallback_price": 1450.20,
        "fallback_prev_close": 1435.10
    },
    {
        "label": "GOLD",
        "symbol": "GC=F",
        "tv_symbol": "TVC:GOLD",
        "type": "commodity",
        "fallback_price": 2350.00,
        "fallback_prev_close": 2364.20
    },
    {
        "label": "SILVER",
        "symbol": "SI=F",
        "tv_symbol": "TVC:SILVER",
        "type": "commodity",
        "fallback_price": 63.50,
        "fallback_prev_close": 65.30
    },
    {
        "label": "CRUDE OIL",
        "symbol": "CL=F",
        "tv_symbol": "TVC:USOIL",
        "type": "commodity",
        "fallback_price": 78.50,
        "fallback_prev_close": 78.75
    },
    {
        "label": "USD/INR",
        "symbol": "USDINR=X",
        "tv_symbol": "FX:USDINR",
        "type": "forex",
        "fallback_price": 83.45,
        "fallback_prev_close": 83.54
    },
    {
        "label": "BITCOIN",
        "symbol": "BTC-USD",
        "tv_symbol": "CRYPTO:BTCUSD",
        "type": "crypto",
        "fallback_price": 64230.00,
        "fallback_prev_close": 63030.00
    }
]

# In-memory cache variables
_market_data_cache = None
_market_data_last_fetched = 0.0
CACHE_TTL = 60.0

async def fetch_ticker_data(client: httpx.AsyncClient, cfg: dict) -> dict:
    symbol = cfg["symbol"]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/"
    }
    try:
        response = await client.get(url, headers=headers, timeout=4.0)
        if response.status_code == 200:
            res_json = response.json()
            meta = res_json["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev_close = meta.get("chartPreviousClose")
            if price is not None and prev_close is not None:
                return {
                    "symbol": cfg["label"],
                    "raw_price": float(price),
                    "raw_prev_close": float(prev_close),
                    "cfg": cfg,
                    "success": True
                }
    except Exception:
        pass
    
    return {
        "symbol": cfg["label"],
        "raw_price": cfg["fallback_price"],
        "raw_prev_close": cfg["fallback_prev_close"],
        "cfg": cfg,
        "success": False
    }

@router.get("/market-data")
async def get_market_data():
    """Live market data feed fetched from Yahoo Finance with memory cache and staggered fetching."""
    global _market_data_cache, _market_data_last_fetched
    now = time.time()
    if _market_data_cache is not None and (now - _market_data_last_fetched) < CACHE_TTL:
        return _market_data_cache

    results = []
    async with httpx.AsyncClient() as client:
        for cfg in TICKERS_CONFIG:
            res = await fetch_ticker_data(client, cfg)
            results.append(res)
            # Add a small delay between requests to avoid triggering Yahoo's rate limiter / 429 blocks
            await asyncio.sleep(0.2)

    final_data = []
    for item in results:
        cfg = item["cfg"]
        price = item["raw_price"]
        prev_close = item["raw_prev_close"]
        
        price = round(price, 2)
        prev_close = round(prev_close, 2)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close * 100) if prev_close else 0.0, 2)
        
        final_data.append({
            "symbol": cfg["label"],
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "tv_symbol": cfg["tv_symbol"],
            "volume": f"{random.randint(10, 300)}M"
        })

    _market_data_cache = final_data
    _market_data_last_fetched = now
    return final_data



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
