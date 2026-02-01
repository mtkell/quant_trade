"""Async event loop with periodic reconciliation and trade listener.

Demonstrates integration of AsyncExecutionEngine with real async operations:
- Periodic reconciliation (every N seconds)
- Mock trade listener (publishes last_trade_price)
- Stop-timeout handler
"""
import asyncio
from decimal import Decimal
from typing import AsyncIterator, Callable, Optional


class PeriodicReconciler:
    """Periodically reconcile open positions and orders."""

    def __init__(self, interval_seconds: float = 60.0):
        self.interval = interval_seconds

    async def run(self, on_reconcile: Callable) -> None:
        """Run periodic reconciliation.
        
        Args:
            on_reconcile: Async callback invoked every interval_seconds
        """
        while True:
            try:
                await on_reconcile()
            except Exception:
                # In production: log the error
                pass
            await asyncio.sleep(self.interval)


class MockTradeListener:
    """Mock WebSocket-like trade listener that publishes trade prices."""

    def __init__(self, interval_seconds: float = 1.0, initial_price: Decimal = Decimal('50000')):
        self.interval = interval_seconds
        self.price = initial_price
        self.price_delta = Decimal('10')  # price change per event

    async def stream_trades(self) -> AsyncIterator[Decimal]:
        """Yield simulated trade prices."""
        while True:
            # Simulate price movement (up/down randomly)
            import random
            delta = self.price_delta if random.random() > 0.5 else -self.price_delta
            self.price = max(Decimal('0'), self.price + delta)
            yield self.price
            await asyncio.sleep(self.interval)


class EventLoopRunner:
    """Orchestrate async engine with periodic reconciliation and trade stream."""

    def __init__(
        self,
        engine,
        reconciler: Optional[PeriodicReconciler] = None,
        trade_listener: Optional[MockTradeListener] = None,
    ):
        self.engine = engine
        self.reconciler = reconciler or PeriodicReconciler(interval_seconds=30.0)
        self.trade_listener = trade_listener or MockTradeListener(interval_seconds=2.0)
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start the engine: reconcile, listen to trades, and handle stops.
        
        This runs three concurrent tasks:
        1. Periodic reconciliation
        2. Trade price listener (updates stops)
        3. Stop-timeout handler (replaces expired stops)
        """
        # Initialize engine
        await self.engine.startup_reconcile()

        # Run concurrent tasks
        await asyncio.gather(
            self._reconcile_loop(),
            self._trade_listener_loop(),
            self._stop_timeout_loop(),
            return_exceptions=False,
        )

    async def stop(self):
        """Signal the event loop to stop."""
        self._stop_event.set()

    async def _reconcile_loop(self):
        """Periodic reconciliation loop."""
        try:
            while not self._stop_event.is_set():
                await self.engine.startup_reconcile()
                await asyncio.sleep(self.reconciler.interval)
        except asyncio.CancelledError:
            pass

    async def _trade_listener_loop(self):
        """Listen to trade prices and update trailing stops."""
        async for price in self.trade_listener.stream_trades():
            if self._stop_event.is_set():
                break
            # Update trailing stop based on latest trade
            await self.engine.on_trade(last_trade_price=price)

    async def _stop_timeout_loop(self):
        """Periodically check for stop-timeout conditions.
        
        In production, this would track order creation time and trigger
        aggressive replacement if not filled within timeout_seconds.
        """
        stop_timeout_check_interval = 5.0  # check every 5 seconds
        while not self._stop_event.is_set():
            try:
                # In production, check actual order age and trigger replacement if needed
                await asyncio.sleep(stop_timeout_check_interval)
            except asyncio.CancelledError:
                break
