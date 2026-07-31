"""WebSocket stream manager for real-time market data broadcasting."""

import asyncio
import json
import logging
import time
from typing import Dict, List, Set, Any

from fastapi import WebSocket, WebSocketDisconnect
from app.services.twelve_data_service import twelve_data_service

logger = logging.getLogger(__name__)

class MarketStreamManager:
    """Manages active WebSocket connections and broadcasts synchronized real-time market ticks."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self.default_symbols: Set[str] = {
            "RELIANCE",
            "TCS",
            "HDFCBANK",
            "INFY",
            "SENSEX",
            "NIFTY",
            "TATAMOTORS",
            "ICICIBANK",
            "BTC/USD",
            "AAPL",
            "GOOGL",
            "AMZN",
            "META"
        }
        self._running = False
        self._task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and initialize default subscriptions."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set(self.default_symbols)
        logger.info(f"WebSocket client connected. Total connected: {len(self.active_connections)}")

        # Send initial snapshot immediately upon connection
        try:
            initial_quotes = await twelve_data_service.latest_prices_batch(list(self.default_symbols))
            await websocket.send_json({
                "type": "tick",
                "data": initial_quotes,
                "timestamp": int(time.time())
            })
        except Exception as e:
            logger.warning(f"Error sending initial WebSocket snapshot: {e}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection and clean up subscriptions."""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket client disconnected. Total connected: {len(self.active_connections)}")

    async def handle_message(self, websocket: WebSocket, message_text: str) -> None:
        """Process subscription or control messages from client."""
        try:
            payload = json.loads(message_text)
            action = payload.get("action")
            symbols = payload.get("symbols", [])

            if not isinstance(symbols, list):
                symbols = [symbols] if isinstance(symbols, str) else []

            clean_symbols = {sym.strip().upper() for sym in symbols if sym and isinstance(sym, str)}

            if action == "subscribe" and clean_symbols:
                if websocket in self.subscriptions:
                    self.subscriptions[websocket].update(clean_symbols)
                else:
                    self.subscriptions[websocket] = set(self.default_symbols) | clean_symbols
                
                # Fetch and send immediate quote for newly subscribed symbols
                try:
                    new_quotes = await twelve_data_service.latest_prices_batch(list(clean_symbols))
                    await websocket.send_json({
                        "type": "tick",
                        "data": new_quotes,
                        "timestamp": int(time.time())
                    })
                except Exception as e:
                    logger.warning(f"Error fetching newly subscribed symbol quotes: {e}")

            elif action == "unsubscribe" and clean_symbols:
                if websocket in self.subscriptions:
                    self.subscriptions[websocket] -= clean_symbols

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received over WebSocket: {message_text}")
        except Exception as e:
            logger.warning(f"Error handling WebSocket message: {e}")

    async def start_broadcasting(self) -> None:
        """Background loop broadcasting real-time ticks every 1 second."""
        if self._running:
            return
        self._running = True
        logger.info("Starting real-time MarketStreamManager broadcast loop...")

        while self._running:
            try:
                if self.active_connections:
                    # Gather all unique symbols across all connected clients
                    all_symbols = set(self.default_symbols)
                    for sym_set in self.subscriptions.values():
                        all_symbols.update(sym_set)

                    if all_symbols:
                        quotes = await twelve_data_service.latest_prices_batch(list(all_symbols))
                        payload = {
                            "type": "tick",
                            "data": quotes,
                            "timestamp": int(time.time())
                        }

                        # Broadcast identical payload to all active clients
                        for ws in list(self.active_connections):
                            try:
                                await ws.send_json(payload)
                            except (WebSocketDisconnect, RuntimeError):
                                self.disconnect(ws)
                            except Exception as e:
                                logger.warning(f"Error sending tick to WebSocket client: {e}")
                                self.disconnect(ws)

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in MarketStreamManager broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    def stop_broadcasting(self) -> None:
        """Stop background ticker."""
        self._running = False
        if self._task:
            self._task.cancel()

market_stream_manager = MarketStreamManager()
