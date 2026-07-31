"""Trading simulator API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query, Response, status, HTTPException, Body, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles, require_student_kyc
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.simulator import schemas, services
from app.modules.simulator.ws import market_stream_manager
from app.services.twelve_data_service import twelve_data_service

router = APIRouter(prefix="/simulator", tags=["Trading Simulator"])


@router.websocket("/ws/market")
async def websocket_market_stream(websocket: WebSocket):
    """Bidirectional WebSocket streaming real-time market ticks."""
    await market_stream_manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await market_stream_manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        market_stream_manager.disconnect(websocket)
    except Exception:
        market_stream_manager.disconnect(websocket)


@router.get("/market-data", response_model=List[schemas.MarketQuoteResponse])
async def get_market_data(symbols: str = Query("RELIANCE,TCS,HDFCBANK,INFY,SENSEX,NIFTY,TATAMOTORS,ICICIBANK,BTC/USD,AAPL")):
    """Server-side market quotes from Twelve Data. The API key never reaches the frontend."""
    selected = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    return await services.market_quotes(selected)


@router.get("/market/price/{symbol}", response_model=schemas.MarketQuoteResponse)
async def latest_price(symbol: str):
    """Latest executable simulator price from Twelve Data."""
    return await twelve_data_service.latest_price(symbol)


@router.get("/market/search")
async def symbol_search(query: str = Query(..., min_length=1)):
    """Search tradable symbols through Twelve Data."""
    return await twelve_data_service.search(query)


@router.get("/market/candles")
async def historical_candles(
    symbol: str = Query(..., min_length=1),
    interval: str = Query("1day"),
    outputsize: int = Query(100, ge=1, le=5000),
):
    """Historical candles for TradingView-compatible chart overlays."""
    return await twelve_data_service.candles(symbol, interval=interval, outputsize=outputsize)


@router.post("/market/quotes")
async def market_quotes(req: schemas.MarketDataRequest):
    """Batch quotes from Twelve Data."""
    return await twelve_data_service.quotes(req.symbols)


@router.post("/start", response_model=schemas.SimulatorAccountResponse, status_code=201)
async def start_simulator(
    req: schemas.SimulatorStartRequest,
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    account = await services.create_account(db, current_user.id, req.profile_id)
    return schemas.SimulatorAccountResponse.model_validate(account)


@router.get("/dashboard", response_model=schemas.DashboardResponse)
async def trading_dashboard(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    data = await services.get_dashboard(db, current_user.id)
    return {
        "account": schemas.SimulatorAccountResponse.model_validate(data["account"]),
        "wallet": schemas.WalletResponse.model_validate(data["wallet"]),
        "open_positions": [schemas.PositionResponse.model_validate(p) for p in data["open_positions"]],
        "closed_trades": [schemas.TradeResponse.model_validate(t) for t in data["closed_trades"]],
        "order_history": data["order_history"],
        "performance": data["performance"],
    }


@router.post("/trade", response_model=schemas.TradeResponse, status_code=201)
async def open_trade(
    req: schemas.TradeRequest,
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    trade = await services.open_trade(
        db,
        current_user.id,
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
        price=req.price,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
    )
    return schemas.TradeResponse.model_validate(trade)


@router.post("/close", response_model=schemas.TradeResponse)
async def close_position(
    req: schemas.ClosePositionRequest,
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    trade = await services.close_position(db, current_user.id, req.position_id, req.exit_price)
    return schemas.TradeResponse.model_validate(trade)


@router.get("/positions", response_model=List[schemas.PositionResponse])
async def list_positions(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    positions = await services.get_positions(db, current_user.id)
    return [schemas.PositionResponse.model_validate(p) for p in positions]


@router.get("/trades", response_model=List[schemas.TradeResponse])
async def list_trades(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    trades = await services.get_trades(db, current_user.id)
    return [schemas.TradeResponse.model_validate(t) for t in trades]


@router.get("/profiles", response_model=List[schemas.SimulatorProfileResponse])
async def list_profiles(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    profiles = await services.get_profiles(db)
    return [schemas.SimulatorProfileResponse.model_validate(p) for p in profiles]


@router.get("/performance", response_model=schemas.PerformanceResponse)
async def get_performance(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    metric = await services.compute_performance(db, current_user.id)
    return schemas.PerformanceResponse.model_validate(metric)


@router.get("/reports/{period}", response_model=schemas.ReportResponse)
async def get_report(
    period: str,
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    return await services.generate_report(db, current_user.id, period=period)


@router.get("/reports/{period}/export")
async def export_report(
    period: str,
    format: str = Query("csv", pattern="^(csv|excel|pdf)$"),
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db),
):
    report = await services.generate_report(db, current_user.id, period=period)
    if format == "csv":
        return Response(
            content=services.export_report_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=simulator-{period}.csv"},
        )
    return {"message": f"{format.upper()} export is queued for generation.", "report": report}


@router.post("/admin/profiles", response_model=schemas.SimulatorProfileResponse, status_code=201)
async def admin_create_profile(
    req: schemas.SimulatorProfileUpsertRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    profile = await services.upsert_profile(db, req.model_dump())
    return schemas.SimulatorProfileResponse.model_validate(profile)


@router.put("/admin/profiles/{profile_id}", response_model=schemas.SimulatorProfileResponse)
async def admin_update_profile(
    profile_id: int,
    req: schemas.SimulatorProfileUpsertRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    profile = await services.upsert_profile(db, req.model_dump(), profile_id=profile_id)
    return schemas.SimulatorProfileResponse.model_validate(profile)


@router.get("/admin/monitor", response_model=schemas.AdminMonitorResponse)
async def admin_monitor(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    return await services.admin_monitor(db)


@router.get("/admin/students/{user_id}/dashboard", response_model=schemas.DashboardResponse)
async def admin_student_dashboard(
    user_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """View a specific student's trading simulator dashboard (Admin only)."""
    data = await services.get_dashboard(db, user_id)
    return {
        "account": schemas.SimulatorAccountResponse.model_validate(data["account"]),
        "wallet": schemas.WalletResponse.model_validate(data["wallet"]),
        "open_positions": [schemas.PositionResponse.model_validate(p) for p in data["open_positions"]],
        "closed_trades": [schemas.TradeResponse.model_validate(t) for t in data["closed_trades"]],
        "performance": data["performance"],
    }


# ── Watchlist Routes ─────────────────────────────────────────────────
@router.get("/watchlist", response_model=List[schemas.WatchlistResponse])
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Get persistent user watchlist (auto-seeds defaults if empty)."""
    return await services.get_user_watchlist(db, current_user.id)


@router.post("/watchlist", response_model=schemas.WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(
    req: schemas.WatchlistAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Add a stock symbol to user's persistent watchlist."""
    try:
        return await services.add_to_watchlist(db, current_user.id, req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/watchlist/{symbol}", status_code=status.HTTP_200_OK)
async def delete_watchlist_item(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Remove a symbol from persistent watchlist."""
    removed = await services.remove_from_watchlist(db, current_user.id, symbol)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found in watchlist")
    return {"message": "Symbol removed successfully", "symbol": symbol.upper()}


# ── User Settings Routes ─────────────────────────────────────────────
@router.get("/settings", response_model=schemas.UserSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Get user's trading simulator preferences."""
    return await services.get_user_settings(db, current_user.id)


@router.put("/settings", response_model=schemas.UserSettingsResponse)
async def update_settings(
    req: schemas.UserSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Update user's trading simulator preferences."""
    return await services.update_user_settings(db, current_user.id, req.model_dump())


# ── Trading Journal Routes ───────────────────────────────────────────
@router.get("/journal", response_model=List[schemas.JournalResponse])
async def list_journal_entries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """List student's trading journal entries."""
    return await services.get_journal_entries(db, current_user.id)


@router.post("/journal", response_model=schemas.JournalResponse, status_code=status.HTTP_201_CREATED)
async def create_journal(
    req: schemas.JournalCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Create a new trading journal entry."""
    return await services.create_journal_entry(db, current_user.id, req.model_dump())


@router.put("/journal/{entry_id}", response_model=schemas.JournalResponse)
async def update_journal(
    entry_id: int,
    req: schemas.JournalUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Update an existing journal entry."""
    return await services.update_journal_entry(db, current_user.id, entry_id, req.model_dump())


@router.delete("/journal/{entry_id}", status_code=status.HTTP_200_OK)
async def delete_journal(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Delete a trading journal entry."""
    removed = await services.delete_journal_entry(db, current_user.id, entry_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return {"message": "Journal entry deleted successfully"}


@router.post("/journal/{entry_id}/ai-review")
async def generate_ai_trade_review(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Generate an AI-powered educational review for a trade."""
    return await services.generate_ai_review(db, current_user.id, entry_id)


# ── Trading Strategies Routes ────────────────────────────────────────
@router.get("/strategies", response_model=List[schemas.StrategyResponse])
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """List user's custom trading strategies."""
    return await services.get_strategies(db, current_user.id)


@router.post("/strategies", response_model=schemas.StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_trading_strategy(
    req: schemas.StrategyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Create a new trading strategy for educational backtesting."""
    return await services.create_strategy(db, current_user.id, req.model_dump())


@router.post("/strategies/{strategy_id}/backtest")
async def run_strategy_backtest(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Run an educational backtest for a strategy against historical data."""
    return await services.backtest_strategy(db, current_user.id, strategy_id)


# ── Position Size & Risk Calculator Routes ───────────────────────────
@router.post("/calculator/position-size", response_model=schemas.PositionSizeCalcResponse)
async def calc_position_size(
    req: schemas.PositionSizeCalcRequest,
    _user: User = Depends(require_student_kyc),
):
    """Calculate recommended position size and monetary risk."""
    return services.calculate_position_size(req.model_dump())


# ── Advanced Analytics Routes ────────────────────────────────────────
@router.get("/analytics/advanced", response_model=schemas.AdvancedAnalyticsResponse)
async def get_advanced_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student_kyc),
):
    """Get comprehensive trading analytics, ratios, equity curve, and emotion breakdown."""
    return await services.get_advanced_analytics(db, current_user.id)
