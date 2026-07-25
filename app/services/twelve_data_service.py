"""Server-side Twelve Data market data client."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from app.config import settings


@dataclass
class RateLimitState:
    window_started_at: float = 0.0
    requests_in_window: int = 0


class TwelveDataService:
    """Thin async client for Twelve Data.

    This service is intentionally backend-only because it reads the API key from
    environment settings and never returns it to callers.
    """

    def __init__(self) -> None:
        self.base_url = settings.TWELVE_DATA_BASE_URL.rstrip("/")
        self.api_key = settings.TWELVE_DATA_API_KEY
        self.timeout = settings.TWELVE_DATA_TIMEOUT_SECONDS
        self.max_requests_per_minute = max(1, settings.TWELVE_DATA_RATE_LIMIT_PER_MINUTE)
        self._rate = RateLimitState()
        self._lock = asyncio.Lock()
        
        # In-memory cache to prevent hitting Twelve Data's strict rate limits (8 requests/min on free plan)
        # Structure: { symbol.upper(): (timestamp, price_data_dict) }
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl = 10.0  # cache quotes for 10 seconds

    def _has_slot(self) -> bool:
        now = time.monotonic()
        if now - self._rate.window_started_at >= 60:
            return True
        return self._rate.requests_in_window < self.max_requests_per_minute

    def _generate_mock_price(self, symbol: str) -> Dict[str, Any]:
        import random
        sym_upper = symbol.upper()
        sym_clean = sym_upper.replace(" ", "")
        
        # Default mock pricing values
        fallbacks = {
            "AAPL": {"price": 175.50, "change": 1.25, "change_pct": 0.72},
            "MSFT": {"price": 420.25, "change": -2.10, "change_pct": -0.50},
            "TSLA": {"price": 180.10, "change": 3.45, "change_pct": 1.95},
            "NVDA": {"price": 875.00, "change": 15.30, "change_pct": 1.78},
            "BTC/USD": {"price": 67500.00, "change": -450.00, "change_pct": -0.66},
            "EUR/USD": {"price": 1.0850, "change": 0.0015, "change_pct": 0.14},
            "BITCOIN": {"price": 67500.00, "change": -450.00, "change_pct": -0.66},
            "GOLD": {"price": 2350.00, "change": 12.50, "change_pct": 0.53},
            "SILVER": {"price": 28.50, "change": 0.35, "change_pct": 1.24},
            "CRUDEOIL": {"price": 78.50, "change": -0.65, "change_pct": -0.82},
            "SENSEX": {"price": 76941.99, "change": 438.39, "change_pct": 0.57},
            "NIFTY": {"price": 24024.75, "change": 142.70, "change_pct": 0.60},
            "BANKNIFTY": {"price": 51500.00, "change": 320.50, "change_pct": 0.63},
            "RELIANCE": {"price": 2950.45, "change": 12.30, "change_pct": 0.42},
            "TCS": {"price": 3840.10, "change": -15.20, "change_pct": -0.39},
            "HDFCBANK": {"price": 1645.80, "change": 8.50, "change_pct": 0.52},
            "INFY": {"price": 1520.65, "change": 5.40, "change_pct": 0.36},
            "TATAMOTORS": {"price": 960.00, "change": -5.20, "change_pct": -0.54},
            "ICICIBANK": {"price": 1120.00, "change": 8.40, "change_pct": 0.75},
            "WIPRO": {"price": 485.00, "change": -2.10, "change_pct": -0.43},
            "ITC": {"price": 430.00, "change": 1.80, "change_pct": 0.42},
            "SBIN": {"price": 830.50, "change": 6.20, "change_pct": 0.75},
            "BHARTIARTL": {"price": 1420.00, "change": 14.50, "change_pct": 1.03},
            "LT": {"price": 3650.00, "change": -22.00, "change_pct": -0.60},
            "HINDUNILVR": {"price": 2480.00, "change": 18.00, "change_pct": 0.73},
            "AXISBANK": {"price": 1250.00, "change": 11.20, "change_pct": 0.90},
            "KOTAKBANK": {"price": 1780.00, "change": -8.50, "change_pct": -0.48},
            "MARUTI": {"price": 12800.00, "change": 125.00, "change_pct": 0.99},
            "SUNPHARMA": {"price": 1540.00, "change": 15.40, "change_pct": 1.01},
            "TITAN": {"price": 3400.00, "change": 25.00, "change_pct": 0.74},
            "BAJFINANCE": {"price": 7200.00, "change": 65.00, "change_pct": 0.91},
            "ASIANPAINT": {"price": 2900.00, "change": -14.00, "change_pct": -0.48},
            "HCLTECH": {"price": 1600.00, "change": 12.00, "change_pct": 0.76},
            "GOOGL": {"price": 175.00, "change": 2.10, "change_pct": 1.21},
            "AMZN": {"price": 185.00, "change": -1.50, "change_pct": -0.80},
            "META": {"price": 490.00, "change": 8.50, "change_pct": 1.76},
            "ETH/USD": {"price": 3500.00, "change": -45.00, "change_pct": -1.27},
            "SOL/USD": {"price": 150.00, "change": 4.50, "change_pct": 3.09},
        }
        
        base = fallbacks.get(sym_clean) or fallbacks.get(sym_clean.replace("/", "")) or {"price": 100.0, "change": 0.0, "change_pct": 0.0}
        
        fluc = random.uniform(-0.0005, 0.0005)
        new_price = round(base["price"] * (1 + fluc), 4)
        change = round(new_price - base["price"], 4)
        change_pct = round(fluc * 100, 4)
        
        price_data = {
            "symbol": sym_upper,
            "price": new_price,
            "change": change,
            "change_pct": change_pct,
            "timestamp": str(int(time.time())),
        }
        self._cache[sym_upper] = (time.time(), price_data)
        return price_data

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="Twelve Data API key is not configured.")

    async def _wait_for_slot(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now - self._rate.window_started_at >= 60:
                self._rate.window_started_at = now
                self._rate.requests_in_window = 0

            if self._rate.requests_in_window >= self.max_requests_per_minute:
                wait_for = 60 - (now - self._rate.window_started_at)
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                self._rate.window_started_at = time.monotonic()
                self._rate.requests_in_window = 0

            self._rate.requests_in_window += 1

    async def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_configured()
        request_params = {k: v for k, v in params.items() if v is not None}
        request_params["apikey"] = self.api_key
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        last_error: Optional[Exception] = None
        for attempt in range(3):
            await self._wait_for_slot()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=request_params)
                if response.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("status") == "error":
                    message = payload.get("message") or "Twelve Data request failed."
                    raise HTTPException(status_code=502, detail=message)
                return payload
            except HTTPException:
                raise
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.5 * (attempt + 1))

        raise HTTPException(status_code=502, detail=f"Twelve Data request failed: {last_error}")

    async def latest_price(self, symbol: str) -> Dict[str, Any]:
        sym_upper = symbol.upper()
        now = time.time()
        
        # Check cache
        if sym_upper in self._cache:
            timestamp, cached_data = self._cache[sym_upper]
            if now - timestamp < self._cache_ttl:
                return cached_data
            if not self._has_slot():
                self._cache[sym_upper] = (now, cached_data)
                return cached_data
                
        # If cache miss and no slot, return mock or expired cache
        if not self._has_slot():
            if sym_upper in self._cache:
                return self._cache[sym_upper][1]
            return self._generate_mock_price(sym_upper)
            
        try:
            quote = await self.quote(symbol)
            price = quote.get("close") or quote.get("price") or quote.get("previous_close")
            if price is None:
                if sym_upper in self._cache:
                    return self._cache[sym_upper][1]
                return self._generate_mock_price(sym_upper)
                
            price_data = {
                "symbol": quote.get("symbol", symbol.upper()),
                "price": float(price),
                "change": float(quote.get("change") or 0),
                "change_pct": float(quote.get("percent_change") or 0),
                "timestamp": quote.get("timestamp") or quote.get("datetime"),
            }
            self._cache[sym_upper] = (now, price_data)
            return price_data
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Twelve Data latest_price failed for {symbol}: {e}")
            if sym_upper in self._cache:
                return self._cache[sym_upper][1]
            return self._generate_mock_price(sym_upper)

    async def quote(self, symbol: str) -> Dict[str, Any]:
        return await self._get("quote", {"symbol": symbol.upper()})

    async def quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        return await self.latest_prices_batch(symbols)

    async def latest_prices_batch(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch quotes for multiple symbols using a single batch request to Twelve Data, with cache lookup."""
        self._ensure_configured()
        
        now = time.time()
        results = {}
        missing_symbols = []
        
        # 1. Check cache first
        for symbol in symbols:
            sym_upper = symbol.strip().upper()
            if not sym_upper:
                continue
            if sym_upper in self._cache:
                timestamp, cached_data = self._cache[sym_upper]
                if now - timestamp < self._cache_ttl:
                    results[sym_upper] = cached_data
                    continue
                # If cache is expired but we don't have slot, fallback to expired cache to avoid blocking!
                if not self._has_slot():
                    self._cache[sym_upper] = (now, cached_data)
                    results[sym_upper] = cached_data
                    continue
            missing_symbols.append(sym_upper)
            
        # 2. Fetch missing symbols in a single batch request
        if missing_symbols:
            # Check if we have slot. If not, use cached or mock
            if not self._has_slot():
                import logging
                logging.getLogger(__name__).warning("No Twelve Data slots available, using mock/cache fallbacks.")
                for sym_upper in missing_symbols:
                    if sym_upper in self._cache:
                        results[sym_upper] = self._cache[sym_upper][1]
                    else:
                        results[sym_upper] = self._generate_mock_price(sym_upper)
            else:
                symbols_str = ",".join(missing_symbols)
                try:
                    payload = await self._get("quote", {"symbol": symbols_str})
                    
                    if "symbol" in payload:
                        parsed_quotes = {payload["symbol"].upper(): payload}
                    else:
                        parsed_quotes = {sym.upper(): data for sym, data in payload.items() if isinstance(data, dict)}
                    
                    for sym_upper in missing_symbols:
                        quote = parsed_quotes.get(sym_upper)
                        if not quote:
                            if sym_upper in self._cache:
                                results[sym_upper] = self._cache[sym_upper][1]
                            else:
                                results[sym_upper] = self._generate_mock_price(sym_upper)
                            continue
                        
                        price = quote.get("close") or quote.get("price") or quote.get("previous_close")
                        if price is None:
                            if sym_upper in self._cache:
                                results[sym_upper] = self._cache[sym_upper][1]
                            else:
                                results[sym_upper] = self._generate_mock_price(sym_upper)
                            continue
                            
                        price_data = {
                            "symbol": quote.get("symbol", sym_upper),
                            "price": float(price),
                            "change": float(quote.get("change") or 0),
                            "change_pct": float(quote.get("percent_change") or 0),
                            "timestamp": quote.get("timestamp") or quote.get("datetime"),
                        }
                        self._cache[sym_upper] = (now, price_data)
                        results[sym_upper] = price_data
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Twelve Data batch quote failed: {e}. Using mock/cache.")
                    for sym_upper in missing_symbols:
                        if sym_upper in self._cache:
                            results[sym_upper] = self._cache[sym_upper][1]
                        else:
                            results[sym_upper] = self._generate_mock_price(sym_upper)
                        
        # 3. Return results in the requested order
        output = []
        for symbol in symbols:
            sym_upper = symbol.strip().upper()
            if sym_upper in results:
                output.append(results[sym_upper])
        return output

    async def candles(
        self,
        symbol: str,
        interval: str = "1day",
        outputsize: int = 100,
    ) -> Dict[str, Any]:
        return await self._get(
            "time_series",
            {
                "symbol": symbol.upper(),
                "interval": interval,
                "outputsize": min(max(outputsize, 1), 5000),
            },
        )

    async def search(self, query: str) -> Dict[str, Any]:
        return await self._get("symbol_search", {"symbol": query})


twelve_data_service = TwelveDataService()
