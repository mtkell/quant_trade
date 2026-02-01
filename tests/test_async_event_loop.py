"""Test async event loop integration with mock engine."""
import asyncio
from decimal import Decimal

import pytest

from trading.async_event_loop import EventLoopRunner, PeriodicReconciler, MockTradeListener


class MockAsyncEngine:
    """Mock async engine for testing event loop."""
    
    def __init__(self):
        self.reconcile_count = 0
        self.trade_prices = []
        self.stop_timeout_count = 0
    
    async def startup_reconcile(self):
        self.reconcile_count += 1
    
    async def on_trade(self, last_trade_price: Decimal):
        self.trade_prices.append(last_trade_price)


@pytest.mark.asyncio
async def test_event_loop_runs_without_error():
    """Event loop should run and handle basic async operations."""
    engine = MockAsyncEngine()
    reconciler = PeriodicReconciler(interval_seconds=0.05)  # fast for testing
    listener = MockTradeListener(interval_seconds=0.02)
    
    runner = EventLoopRunner(engine=engine, reconciler=reconciler, trade_listener=listener)
    
    # Run for a short time then stop
    task = asyncio.create_task(runner.start())
    await asyncio.sleep(0.1)
    await runner.stop()
    
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        task.cancel()
    except asyncio.CancelledError:
        pass
    
    # Verify engine was used
    assert engine.reconcile_count >= 1
    assert len(engine.trade_prices) >= 2


@pytest.mark.asyncio
async def test_mock_trade_listener_generates_prices():
    """Trade listener should generate price updates."""
    listener = MockTradeListener(interval_seconds=0.01, initial_price=Decimal('100'))
    
    prices = []
    async for price in listener.stream_trades():
        prices.append(price)
        if len(prices) >= 5:
            break
    
    assert len(prices) == 5
    # Prices should vary (not all the same)
    assert len(set(prices)) > 1


@pytest.mark.asyncio
async def test_periodic_reconciler_calls_callback():
    """Reconciler should call callback periodically."""
    call_count = [0]
    
    async def callback():
        call_count[0] += 1
    
    reconciler = PeriodicReconciler(interval_seconds=0.02)
    
    task = asyncio.create_task(reconciler.run(callback))
    await asyncio.sleep(0.1)
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    assert call_count[0] >= 2
