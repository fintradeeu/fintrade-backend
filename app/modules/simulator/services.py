"""Trading simulator engine, risk management, market data, and reports."""

from __future__ import annotations

import csv
import io
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.certificates.models import Certificate
from app.modules.courses.models import CourseEnrollment
from app.modules.simulator.models import (
    ChallengeResult,
    Order,
    PerformanceMetric,
    Position,
    SimulatorAccount,
    SimulatorNotification,
    SimulatorProfile,
    StudentPerformance,
    Trade,
    TradeLog,
    Wallet,
)
from app.services.twelve_data_service import twelve_data_service


DEFAULT_SYMBOLS = ["SENSEX", "NIFTY", "RELIANCE", "TATAMOTORS", "ICICIBANK", "WIPRO", "ITC", "AAPL", "BTC/USD"]
TRADINGVIEW_SYMBOLS = {
    "SENSEX": "BSE:SENSEX",
    "NIFTY": "NSE:NIFTY50",
    "RELIANCE": "NSE:RELIANCE",
    "TATAMOTORS": "NSE:TATAMOTORS",
    "ICICIBANK": "NSE:ICICIBANK",
    "WIPRO": "NSE:WIPRO",
    "ITC": "NSE:ITC",
    "BTC/USD": "BINANCE:BTCUSDT",
    "AAPL": "NASDAQ:AAPL",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


async def _log(
    db: AsyncSession,
    account: SimulatorAccount,
    action: str,
    message: str,
    symbol: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    db.add(
        TradeLog(
            account_id=account.id,
            user_id=account.user_id,
            action=action,
            symbol=symbol,
            message=message,
            payload=payload,
        )
    )


async def _notify(
    db: AsyncSession,
    account: SimulatorAccount,
    message: str,
    level: str = "info",
) -> None:
    db.add(
        SimulatorNotification(
            user_id=account.user_id,
            account_id=account.id,
            level=level,
            message=message,
        )
    )


async def _get_profile(db: AsyncSession, account: SimulatorAccount) -> SimulatorProfile:
    if account.profile_id:
        profile = await db.get(SimulatorProfile, account.profile_id)
        if profile:
            return profile
    profile = await get_or_create_default_profile(db)
    account.profile_id = profile.id
    return profile


async def get_or_create_default_profile(db: AsyncSession) -> SimulatorProfile:
    result = await db.execute(select(SimulatorProfile).where(SimulatorProfile.name == "FinTrade Challenge"))
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    profile = SimulatorProfile(
        name="FinTrade Challenge",
        description="Default paper-trading challenge with mandatory stop-loss and risk controls.",
        initial_balance=100000.0,
        daily_loss_limit=5000.0,
        max_drawdown=10000.0,
        profit_target=10000.0,
        risk_per_trade=1.0,
        max_open_trades=5,
        max_position_size=50000.0,
        commission=0.0,
        spread=0.0,
        slippage=0.0,
        trading_hours_start="00:00",
        trading_hours_end="23:59",
        allowed_markets=["stocks", "forex", "crypto", "commodities", "indices"],
        stop_loss_required=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


async def _ensure_wallet(db: AsyncSession, account: SimulatorAccount) -> Wallet:
    result = await db.execute(select(Wallet).where(Wallet.account_id == account.id))
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet

    wallet = Wallet(
        account_id=account.id,
        cash_balance=account.balance,
        equity=account.equity or account.balance,
        buying_power=account.buying_power or account.balance,
    )
    db.add(wallet)
    await db.flush()
    return wallet


async def _refresh_wallet(db: AsyncSession, account: SimulatorAccount) -> Wallet:
    positions = await get_positions(db, account.user_id, update_prices=False)
    unrealized = sum(position.unrealized_pnl or 0.0 for position in positions)
    equity = round((account.balance or 0.0) + unrealized, 2)
    account.equity = equity
    account.buying_power = max(0.0, round(account.balance or 0.0, 2))
    account.peak_equity = max(account.peak_equity or account.initial_balance or equity, equity)

    wallet = await _ensure_wallet(db, account)
    wallet.cash_balance = round(account.balance or 0.0, 2)
    wallet.equity = equity
    wallet.buying_power = account.buying_power
    wallet.unrealized_pnl = round(unrealized, 2)
    wallet.realized_pnl = round(equity - (account.initial_balance or 0.0) - unrealized, 2)
    return wallet


async def _ensure_student_access(db: AsyncSession, user_id: int) -> None:
    enrollment_result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.is_active == True,  # noqa: E712
            CourseEnrollment.completed_at.is_not(None),
        ).limit(1)
    )
    has_completed_course = enrollment_result.scalar_one_or_none() is not None

    cert_result = await db.execute(select(Certificate).where(Certificate.user_id == user_id).limit(1))
    has_certificate = cert_result.scalar_one_or_none() is not None

    if not (has_completed_course or has_certificate):
        raise HTTPException(
            status_code=403,
            detail="Trading Simulator unlocks after enrollment, course completion, and admin pass approval.",
        )


async def create_account(db: AsyncSession, user_id: int, profile_id: Optional[int] = None) -> SimulatorAccount:
    await _ensure_student_access(db, user_id)

    existing = await db.execute(
        select(SimulatorAccount).where(SimulatorAccount.user_id == user_id, SimulatorAccount.is_active == True).limit(1)
    )
    account = existing.scalar_one_or_none()
    if account:
        return account

    profile = await db.get(SimulatorProfile, profile_id) if profile_id else await get_or_create_default_profile(db)
    if profile is None or not profile.is_active:
        raise HTTPException(status_code=404, detail="Simulator profile not found")

    account = SimulatorAccount(
        user_id=user_id,
        profile_id=profile.id,
        balance=profile.initial_balance,
        initial_balance=profile.initial_balance,
        equity=profile.initial_balance,
        buying_power=profile.initial_balance,
        peak_equity=profile.initial_balance,
    )
    db.add(account)
    await db.flush()
    await _ensure_wallet(db, account)
    await _log(db, account, "account_created", "Simulator account created.", payload={"profile_id": profile.id})
    await db.refresh(account)
    return account


async def get_user_account(db: AsyncSession, user_id: int) -> SimulatorAccount:
    result = await db.execute(
        select(SimulatorAccount).where(SimulatorAccount.user_id == user_id, SimulatorAccount.is_active == True).limit(1)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="No active simulator account. Start one first.")
    return account


async def _market_price(symbol: str) -> float:
    latest = await twelve_data_service.latest_price(symbol)
    return float(latest["price"])


async def _check_risk_rules(
    db: AsyncSession,
    account: SimulatorAccount,
    profile: SimulatorProfile,
    symbol: str,
    quantity: float,
    price: float,
    stop_loss: Optional[float],
    side: str,
) -> None:
    await _ensure_student_access(db, account.user_id)
    await _refresh_wallet(db, account)

    now = _utcnow().time()
    start = _parse_hhmm(profile.trading_hours_start or "00:00")
    end = _parse_hhmm(profile.trading_hours_end or "23:59")
    if start <= end and not (start <= now <= end):
        raise HTTPException(status_code=400, detail="Market is closed for this simulator profile.")

    open_count = (
        await db.execute(select(func.count(Position.id)).where(Position.account_id == account.id))
    ).scalar() or 0
    if open_count >= (profile.max_open_trades or 1):
        raise HTTPException(status_code=400, detail="Maximum open trades reached.")

    position_value = quantity * price
    if position_value > profile.max_position_size:
        raise HTTPException(
            status_code=400,
            detail=f"Position size {position_value:.2f} exceeds max {profile.max_position_size:.2f}.",
        )

    if profile.stop_loss_required and stop_loss is None:
        raise HTTPException(status_code=400, detail="Stop-loss is mandatory for this challenge.")

    if stop_loss is not None:
        risk_amount = abs(price - stop_loss) * quantity
        max_risk = account.equity * ((profile.risk_per_trade or 1.0) / 100)
        if risk_amount > max_risk:
            raise HTTPException(status_code=400, detail=f"Risk per trade exceeded: {risk_amount:.2f} > {max_risk:.2f}.")

    if position_value > account.buying_power:
        raise HTTPException(status_code=400, detail="Insufficient buying power.")

    daily_loss = abs(min(account.daily_realized_pnl or 0.0, 0.0))
    if daily_loss >= profile.daily_loss_limit:
        raise HTTPException(status_code=400, detail="Daily loss limit exceeded.")

    drawdown = (account.peak_equity or account.initial_balance) - (account.equity or account.balance)
    if drawdown >= profile.max_drawdown:
        raise HTTPException(status_code=400, detail="Maximum drawdown exceeded.")


async def open_trade(
    db: AsyncSession,
    user_id: int,
    symbol: str,
    side: str,
    quantity: float,
    price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> Trade:
    account = await get_user_account(db, user_id)
    profile = await _get_profile(db, account)
    clean_symbol = symbol.upper()
    market_price = await _market_price(clean_symbol)

    adjustment = (profile.spread or 0.0) + (profile.slippage or 0.0)
    execution_price = market_price + adjustment if side == "buy" else market_price - adjustment
    commission = round((quantity * execution_price) * ((profile.commission or 0.0) / 100), 2)

    await _check_risk_rules(db, account, profile, clean_symbol, quantity, execution_price, stop_loss, side)

    margin = quantity * execution_price
    account.balance = round(account.balance - margin - commission, 2)

    trade = Trade(
        account_id=account.id,
        symbol=clean_symbol,
        side=side,
        quantity=quantity,
        entry_price=round(execution_price, 4),
        stop_loss=stop_loss,
        take_profit=take_profit,
        commission=commission,
        status="open",
    )
    db.add(trade)

    position = Position(
        account_id=account.id,
        symbol=clean_symbol,
        side=side,
        quantity=quantity,
        entry_price=round(execution_price, 4),
        current_price=round(execution_price, 4),
        unrealized_pnl=0.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    db.add(position)

    db.add(
        Order(
            account_id=account.id,
            symbol=clean_symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=round(execution_price, 4),
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="filled",
        )
    )
    await _log(
        db,
        account,
        "order_filled",
        "Virtual order filled.",
        clean_symbol,
        {
            "side": side,
            "quantity": quantity,
            "price": execution_price,
            "commission": commission,
            "requested_price_ignored": price,
        },
    )
    await _refresh_wallet(db, account)
    await db.flush()
    await db.refresh(trade)
    return trade


async def close_position(
    db: AsyncSession,
    user_id: int,
    position_id: int,
    exit_price: Optional[float] = None,
) -> Trade:
    account = await get_user_account(db, user_id)
    profile = await _get_profile(db, account)
    result = await db.execute(select(Position).where(Position.id == position_id, Position.account_id == account.id))
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")

    market_price = await _market_price(position.symbol)
    adjustment = (profile.spread or 0.0) + (profile.slippage or 0.0)
    execution_price = market_price - adjustment if position.side == "buy" else market_price + adjustment
    pnl = (
        (execution_price - position.entry_price) * position.quantity
        if position.side == "buy"
        else (position.entry_price - execution_price) * position.quantity
    )
    close_commission = round((position.quantity * execution_price) * ((profile.commission or 0.0) / 100), 2)
    pnl = round(pnl - close_commission, 2)

    account.balance = round(account.balance + (position.quantity * position.entry_price) + pnl, 2)
    account.daily_realized_pnl = round((account.daily_realized_pnl or 0.0) + pnl, 2)

    trade_result = await db.execute(
        select(Trade)
        .where(Trade.account_id == account.id, Trade.symbol == position.symbol, Trade.status == "open")
        .order_by(Trade.opened_at.desc())
        .limit(1)
    )
    trade = trade_result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Matching trade not found")

    trade.exit_price = round(execution_price, 4)
    trade.pnl = pnl
    trade.commission = round((trade.commission or 0.0) + close_commission, 2)
    trade.status = "closed"
    trade.closed_at = _utcnow()

    await db.delete(position)
    await _log(
        db,
        account,
        "position_closed",
        "Position closed.",
        trade.symbol,
        {"pnl": pnl, "exit_price": execution_price, "requested_exit_price_ignored": exit_price},
    )
    await evaluate_challenge(db, account)
    await _refresh_wallet(db, account)
    await db.flush()
    await db.refresh(trade)
    return trade


async def get_positions(db: AsyncSession, user_id: int, update_prices: bool = True) -> List[Position]:
    account = await get_user_account(db, user_id)
    result = await db.execute(select(Position).where(Position.account_id == account.id).order_by(Position.opened_at.desc()))
    positions = list(result.scalars().all())
    if update_prices and positions:
        symbols = list({p.symbol for p in positions})
        try:
            quotes = await twelve_data_service.latest_prices_batch(symbols)
            price_map = {q["symbol"].upper(): q["price"] for q in quotes}
            triggered_positions = []
            for position in positions:
                sym_upper = position.symbol.upper()
                if sym_upper in price_map:
                    price = price_map[sym_upper]
                    position.current_price = price
                    position.unrealized_pnl = round(
                        (price - position.entry_price) * position.quantity
                        if position.side == "buy"
                        else (position.entry_price - price) * position.quantity,
                        2,
                    )
                    
                    # Check stop_loss or take_profit trigger
                    triggered = False
                    if position.side == "buy":
                        if position.stop_loss is not None and price <= position.stop_loss:
                            triggered = True
                        elif position.take_profit is not None and price >= position.take_profit:
                            triggered = True
                    elif position.side == "sell":
                        if position.stop_loss is not None and price >= position.stop_loss:
                            triggered = True
                        elif position.take_profit is not None and price <= position.take_profit:
                            triggered = True
                            
                    if triggered:
                        triggered_positions.append((position.id, price))
                        
            if triggered_positions:
                for pos_id, exit_pr in triggered_positions:
                    try:
                        await close_position(db, user_id, pos_id, exit_price=exit_pr)
                    except Exception as ex:
                        import logging
                        logging.getLogger(__name__).warning(f"Failed to auto-close triggered position {pos_id}: {ex}")
                
                # Refetch remaining open positions
                result = await db.execute(select(Position).where(Position.account_id == account.id).order_by(Position.opened_at.desc()))
                positions = list(result.scalars().all())
                for position in positions:
                    sym_upper = position.symbol.upper()
                    if sym_upper in price_map:
                        price = price_map[sym_upper]
                        position.current_price = price
                        position.unrealized_pnl = round(
                            (price - position.entry_price) * position.quantity
                            if position.side == "buy"
                            else (position.entry_price - price) * position.quantity,
                            2,
                        )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to batch update position prices: {e}")
    return positions


async def get_trades(db: AsyncSession, user_id: int) -> List[Trade]:
    account = await get_user_account(db, user_id)
    result = await db.execute(select(Trade).where(Trade.account_id == account.id).order_by(Trade.opened_at.desc()))
    return list(result.scalars().all())


async def get_orders(db: AsyncSession, account_id: int) -> List[Order]:
    result = await db.execute(select(Order).where(Order.account_id == account_id).order_by(Order.created_at.desc()))
    return list(result.scalars().all())


async def get_profiles(db: AsyncSession) -> List[SimulatorProfile]:
    await get_or_create_default_profile(db)
    result = await db.execute(select(SimulatorProfile).where(SimulatorProfile.is_active == True))
    return list(result.scalars().all())


async def upsert_profile(db: AsyncSession, data: Dict[str, Any], profile_id: Optional[int] = None) -> SimulatorProfile:
    profile = await db.get(SimulatorProfile, profile_id) if profile_id else None
    if profile is None:
        profile = SimulatorProfile()
        db.add(profile)
    for key, value in data.items():
        setattr(profile, key, value)
    await db.flush()
    await db.refresh(profile)
    return profile


async def evaluate_challenge(db: AsyncSession, account: SimulatorAccount) -> ChallengeResult:
    profile = await _get_profile(db, account)
    await _refresh_wallet(db, account)
    total_profit = (account.equity or 0.0) - (account.initial_balance or 0.0)
    drawdown = (account.peak_equity or account.initial_balance or 0.0) - (account.equity or 0.0)
    daily_loss = abs(min(account.daily_realized_pnl or 0.0, 0.0))

    violations = []
    if daily_loss >= profile.daily_loss_limit:
        violations.append("daily_loss_limit")
    if drawdown >= profile.max_drawdown:
        violations.append("max_drawdown")

    status = "passed" if total_profit >= profile.profit_target and not violations else "active"
    if violations:
        status = "failed"
    account.challenge_status = status

    result = (
        await db.execute(select(ChallengeResult).where(ChallengeResult.account_id == account.id))
    ).scalar_one_or_none()
    if result is None:
        result = ChallengeResult(account_id=account.id)
        db.add(result)
    result.status = status
    result.profit_target_hit = total_profit >= profile.profit_target
    result.daily_loss_breached = "daily_loss_limit" in violations
    result.max_drawdown_breached = "max_drawdown" in violations
    result.violations = violations
    result.evaluated_at = _utcnow()

    if status in {"passed", "failed"}:
        await _notify(db, account, f"Trading challenge {status}.", "success" if status == "passed" else "warning")
    return result


async def compute_performance(db: AsyncSession, user_id: int) -> PerformanceMetric:
    account = await get_user_account(db, user_id)
    result = await db.execute(select(Trade).where(Trade.account_id == account.id, Trade.status == "closed"))
    closed_trades = list(result.scalars().all())

    total_trades = len(closed_trades)
    winning = [t for t in closed_trades if (t.pnl or 0) > 0]
    losing = [t for t in closed_trades if (t.pnl or 0) < 0]
    total_pnl = sum(t.pnl or 0 for t in closed_trades)
    win_rate = (len(winning) / total_trades) * 100 if total_trades else 0.0
    avg_win = sum(t.pnl or 0 for t in winning) / len(winning) if winning else 0.0
    avg_loss = sum(t.pnl or 0 for t in losing) / len(losing) if losing else 0.0

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for trade in sorted(closed_trades, key=lambda item: item.closed_at or item.opened_at):
        cumulative += trade.pnl or 0.0
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    metric = (
        await db.execute(select(PerformanceMetric).where(PerformanceMetric.account_id == account.id))
    ).scalar_one_or_none()
    if metric is None:
        metric = PerformanceMetric(account_id=account.id)
        db.add(metric)

    metric.total_trades = total_trades
    metric.winning_trades = len(winning)
    metric.losing_trades = len(losing)
    metric.total_pnl = round(total_pnl, 2)
    metric.win_rate = round(win_rate, 2)
    metric.avg_win = round(avg_win, 2)
    metric.avg_loss = round(avg_loss, 2)
    metric.max_drawdown = round(max_drawdown, 2)
    metric.risk_score = round(min(100.0, (len(losing) / total_trades * 50 if total_trades else 0) + max_drawdown), 2)
    metric.consistency_score = round(min(100.0, win_rate * 0.7 + min(total_trades, 50) * 0.6), 2)
    metric.computed_at = _utcnow()

    await db.flush()
    await db.refresh(metric)
    return metric


async def get_dashboard(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    account = await get_user_account(db, user_id)
    positions = await get_positions(db, user_id)
    wallet = await _refresh_wallet(db, account)
    trades = await get_trades(db, user_id)
    orders = await get_orders(db, account.id)
    metric = await compute_performance(db, user_id)
    return {
        "account": account,
        "wallet": wallet,
        "open_positions": positions,
        "closed_trades": [trade for trade in trades if trade.status == "closed"],
        "order_history": [
            {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status,
                "created_at": order.created_at,
            }
            for order in orders
        ],
        "performance": {
            "total_trades": metric.total_trades,
            "total_pnl": metric.total_pnl,
            "win_rate": metric.win_rate,
            "max_drawdown": metric.max_drawdown,
            "risk_score": metric.risk_score,
        },
    }


async def admin_monitor(db: AsyncSession) -> Dict[str, Any]:
    from app.modules.auth.models import User
    
    # Fetch accounts with joined user details
    accounts_result = await db.execute(
        select(SimulatorAccount, User.full_name, User.email)
        .join(User, User.id == SimulatorAccount.user_id)
        .options(selectinload(SimulatorAccount.wallet))
        .order_by(SimulatorAccount.created_at.desc())
    )
    accounts_data = accounts_result.all()
    accounts = [row[0] for row in accounts_data]
    
    positions = (await db.execute(select(Position).order_by(Position.opened_at.desc()).limit(100))).scalars().all()
    trades = (await db.execute(select(Trade).order_by(Trade.opened_at.desc()).limit(100))).scalars().all()
    logs = (await db.execute(select(TradeLog).order_by(TradeLog.created_at.desc()).limit(100))).scalars().all()
    results = (await db.execute(select(ChallengeResult).order_by(ChallengeResult.evaluated_at.desc()).limit(100))).scalars().all()

    return {
        "live_trades": [{"id": t.id, "account_id": t.account_id, "symbol": t.symbol, "side": t.side, "quantity": t.quantity} for t in trades if t.status == "open"],
        "open_positions": [{"id": p.id, "account_id": p.account_id, "symbol": p.symbol, "side": p.side, "quantity": p.quantity, "unrealized_pnl": p.unrealized_pnl} for p in positions],
        "closed_positions": [{"id": t.id, "account_id": t.account_id, "symbol": t.symbol, "pnl": t.pnl, "closed_at": t.closed_at} for t in trades if t.status == "closed"],
        "wallet_balances": [{"account_id": a.id, "user_id": a.user_id, "balance": a.balance, "equity": a.equity, "status": a.challenge_status} for a in accounts],
        "student_rankings": sorted(
            [{"account_id": a.id, "user_id": a.user_id, "student_name": name, "student_email": email, "equity": a.equity, "pnl": (a.equity or 0) - (a.initial_balance or 0)} for a, name, email in accounts_data],
            key=lambda row: row["pnl"],
            reverse=True,
        ),
        "violations": [{"account_id": r.account_id, "violations": r.violations, "status": r.status} for r in results if r.violations],
        "challenge_status": [{"account_id": r.account_id, "status": r.status, "evaluated_at": r.evaluated_at} for r in results],
        "trade_logs": [{"id": log.id, "account_id": log.account_id, "action": log.action, "message": log.message, "created_at": log.created_at} for log in logs],
    }


async def generate_report(db: AsyncSession, user_id: int, period: str = "daily") -> Dict[str, Any]:
    account = await get_user_account(db, user_id)
    trades = await get_trades(db, user_id)
    closed = [trade for trade in trades if trade.status == "closed"]
    rows = [
        {
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "closed_at": trade.closed_at,
        }
        for trade in closed
    ]
    summary = {
        "account_id": account.id,
        "balance": account.balance,
        "equity": account.equity,
        "total_trades": len(closed),
        "total_pnl": round(sum(trade.pnl or 0.0 for trade in closed), 2),
        "challenge_status": account.challenge_status,
    }
    db.add(
        StudentPerformance(
            account_id=account.id,
            user_id=user_id,
            period=period,
            starting_equity=account.initial_balance,
            ending_equity=account.equity,
            realized_pnl=summary["total_pnl"],
            total_trades=len(closed),
            violations=[],
        )
    )
    return {"period": period, "generated_at": _utcnow(), "summary": summary, "rows": rows}


def export_report_csv(report: Dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["symbol", "side", "quantity", "entry_price", "exit_price", "pnl", "closed_at"])
    writer.writeheader()
    writer.writerows(report["rows"])
    return output.getvalue()


async def market_quotes(symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    selected = symbols or DEFAULT_SYMBOLS
    try:
        quotes = await twelve_data_service.latest_prices_batch(selected)
        for quote in quotes:
            symbol = quote["symbol"]
            quote["tv_symbol"] = TRADINGVIEW_SYMBOLS.get(symbol.upper(), symbol.upper())
        return quotes
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error fetching market quotes: {e}")
        return []
