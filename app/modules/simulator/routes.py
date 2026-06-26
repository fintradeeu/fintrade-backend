"""Trading simulator API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.simulator import schemas, services
from app.services.twelve_data_service import twelve_data_service

router = APIRouter(prefix="/simulator", tags=["Trading Simulator"])


@router.get("/market-data", response_model=List[schemas.MarketQuoteResponse])
async def get_market_data(symbols: str = Query("AAPL,MSFT,TSLA,NVDA,BTC/USD,EUR/USD")):
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await services.create_account(db, current_user.id, req.profile_id)
    return schemas.SimulatorAccountResponse.model_validate(account)


@router.get("/dashboard", response_model=schemas.DashboardResponse)
async def trading_dashboard(
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trade = await services.close_position(db, current_user.id, req.position_id, req.exit_price)
    return schemas.TradeResponse.model_validate(trade)


@router.get("/positions", response_model=List[schemas.PositionResponse])
async def list_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    positions = await services.get_positions(db, current_user.id)
    return [schemas.PositionResponse.model_validate(p) for p in positions]


@router.get("/trades", response_model=List[schemas.TradeResponse])
async def list_trades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trades = await services.get_trades(db, current_user.id)
    return [schemas.TradeResponse.model_validate(t) for t in trades]


@router.get("/profiles", response_model=List[schemas.SimulatorProfileResponse])
async def list_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles = await services.get_profiles(db)
    return [schemas.SimulatorProfileResponse.model_validate(p) for p in profiles]


@router.get("/performance", response_model=schemas.PerformanceResponse)
async def get_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    metric = await services.compute_performance(db, current_user.id)
    return schemas.PerformanceResponse.model_validate(metric)


@router.get("/reports/{period}", response_model=schemas.ReportResponse)
async def get_report(
    period: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await services.generate_report(db, current_user.id, period=period)


@router.get("/reports/{period}/export")
async def export_report(
    period: str,
    format: str = Query("csv", pattern="^(csv|excel|pdf)$"),
    current_user: User = Depends(get_current_user),
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
