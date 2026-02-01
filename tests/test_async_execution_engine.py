import asyncio
from decimal import Decimal
import pytest

from trading.async_execution import AsyncExecutionEngine
from trading.execution import FilePersistence


class AsyncInMemoryAdapter:
    def __init__(self):
        self.orders = {}
        self.next_id = 1

    def _gen(self):
        oid = f"a{self.next_id}"
        self.next_id += 1
        return oid

    async def place_limit_buy(self, client_id: str, price: Decimal, qty: Decimal):
        oid = self._gen()
        self.orders[oid] = {"type": "limit", "price": str(price), "qty": str(qty), "state": "open"}
        return oid

    async def place_stop_limit(self, client_id: str, trigger: Decimal, limit: Decimal, qty: Decimal):
        oid = self._gen()
        self.orders[oid] = {"type": "stop_limit", "trigger": str(trigger), "limit": str(limit), "qty": str(qty), "state": "open"}
        return oid

    async def cancel_order(self, order_id: str):
        if order_id in self.orders:
            self.orders[order_id]["state"] = "cancelled"
            return True
        return False

    async def get_order_status(self, order_id: str):
        return self.orders.get(order_id)


@pytest.mark.asyncio
async def test_async_engine_places_initial_stop(tmp_path):
    db = tmp_path / "pos.json"
    persistence = FilePersistence(db)
    adapter = AsyncInMemoryAdapter()
    engine = AsyncExecutionEngine(adapter=adapter, persistence=persistence)

    await engine.startup_reconcile()

    oid = await engine.submit_entry(client_id="c1", price=Decimal('100.0'), qty=Decimal('0.1'))
    # simulate a fill
    await engine.handle_fill(order_id=oid, filled_qty=Decimal('0.1'), fill_price=Decimal('100.0'))

    # ensure a stop was placed
    # there should be at least one stop order in adapter.orders
    stops = [o for o in adapter.orders.values() if o.get('type') == 'stop_limit']
    assert len(stops) == 1

    # persistence should contain position with stop_order_id
    pos = persistence.load_position()
    assert pos is not None
    assert pos.current_stop_trigger is not None
    assert pos.stop_order_id is not None
