import asyncio
import inspect
from decimal import Decimal
from typing import Optional

from .order_state import OrderStateMachine
from .position import PositionState


class AsyncExecutionEngine:
    """Async variant of ExecutionEngine that works with async adapters.

    Adapter methods are expected to be awaitable (async). Persistence is
    assumed to be sync; calls are run in threadpool via ``asyncio.to_thread``.
    """

    def __init__(self, adapter, persistence, *, trail_pct: Decimal = Decimal('0.02'), stop_limit_buffer_pct: Decimal = Decimal('0.005'), min_ratchet: Decimal = Decimal('0')):
        self.adapter = adapter
        self.persistence = persistence
        self.osm = OrderStateMachine()
        self.trail_pct = trail_pct
        self.stop_limit_buffer_pct = stop_limit_buffer_pct
        self.min_ratchet = min_ratchet

    async def startup_reconcile(self):
        pos = await asyncio.to_thread(self.persistence.load_position)
        if not pos:
            return
        self.osm.position = pos

        # Ensure stop order exists; if not, place replacement
        try:
            oid = self.osm.position.stop_order_id
            if oid:
                # adapter.get_order_status may be async or sync
                status = None
                if inspect.iscoroutinefunction(getattr(self.adapter, 'get_order_status', None)):
                    status = await self.adapter.get_order_status(oid)
                else:
                    status = await asyncio.to_thread(self.adapter.get_order_status, oid)

                if status is None or status.get('state') not in ('open', 'pending'):
                    self.osm.position.stop_order_id = None
                    await asyncio.to_thread(self.persistence.save_position, self.osm.position)
            else:
                if self.osm.position.current_stop_trigger and self.osm.position.current_stop_limit:
                    if inspect.iscoroutinefunction(getattr(self.adapter, 'place_stop_limit', None)):
                        new_oid = await self.adapter.place_stop_limit(client_id='reconcile', trigger=self.osm.position.current_stop_trigger, limit=self.osm.position.current_stop_limit, qty=self.osm.position.qty_filled)
                    else:
                        new_oid = await asyncio.to_thread(self.adapter.place_stop_limit, 'reconcile', self.osm.position.current_stop_trigger, self.osm.position.current_stop_limit, self.osm.position.qty_filled)
                    self.osm.position.stop_order_id = new_oid
                    await asyncio.to_thread(self.persistence.save_position, self.osm.position)
        except Exception:
            # don't fail startup; in production log the error
            pass

    async def submit_entry(self, client_id: str, price: Decimal, qty: Decimal) -> str:
        if inspect.iscoroutinefunction(getattr(self.adapter, 'place_limit_buy', None)):
            oid = await self.adapter.place_limit_buy(client_id=client_id, price=price, qty=qty)
        else:
            oid = await asyncio.to_thread(self.adapter.place_limit_buy, client_id, price, qty)
        self.osm.place_entry(order_id=oid, price=price, qty=qty)
        return oid

    async def handle_fill(self, order_id: str, filled_qty: Decimal, fill_price: Decimal) -> None:
        self.osm.on_fill(order_id=order_id, filled_qty=filled_qty, fill_price=fill_price)
        if self.osm.position:
            # compute initial stop
            self.osm.position.ratchet_stop(last_trade_price=fill_price, trail_pct=self.trail_pct, stop_limit_buffer_pct=self.stop_limit_buffer_pct, min_ratchet=self.min_ratchet)
            await asyncio.to_thread(self.persistence.save_position, self.osm.position)

            if self.osm.position.current_stop_trigger and not self.osm.position.stop_order_id:
                if inspect.iscoroutinefunction(getattr(self.adapter, 'place_stop_limit', None)):
                    oid = await self.adapter.place_stop_limit(client_id=order_id, trigger=self.osm.position.current_stop_trigger, limit=self.osm.position.current_stop_limit, qty=self.osm.position.qty_filled)
                else:
                    oid = await asyncio.to_thread(self.adapter.place_stop_limit, order_id, self.osm.position.current_stop_trigger, self.osm.position.current_stop_limit, self.osm.position.qty_filled)
                self.osm.position.stop_order_id = oid
                await asyncio.to_thread(self.persistence.save_position, self.osm.position)

    async def on_trade(self, last_trade_price: Decimal):
        changed, stop = self.osm.on_trade(last_trade_price=last_trade_price, trail_pct=self.trail_pct, stop_limit_buffer_pct=self.stop_limit_buffer_pct, min_ratchet=self.min_ratchet)
        if changed and stop:
            old_oid = self.osm.position.stop_order_id
            if old_oid:
                if inspect.iscoroutinefunction(getattr(self.adapter, 'cancel_order', None)):
                    await self.adapter.cancel_order(old_oid)
                else:
                    await asyncio.to_thread(self.adapter.cancel_order, old_oid)

            if inspect.iscoroutinefunction(getattr(self.adapter, 'place_stop_limit', None)):
                new_oid = await self.adapter.place_stop_limit(client_id=old_oid or 'stop', trigger=stop[0], limit=stop[1], qty=self.osm.position.qty_filled)
            else:
                new_oid = await asyncio.to_thread(self.adapter.place_stop_limit, old_oid or 'stop', stop[0], stop[1], self.osm.position.qty_filled)

            self.osm.position.stop_order_id = new_oid
            await asyncio.to_thread(self.persistence.save_position, self.osm.position)

    async def handle_stop_timeout(self, aggressive_price_delta_pct: Decimal):
        new_trigger, new_limit = self.osm.stop_timeout_replacement(aggressive_price_delta_pct=aggressive_price_delta_pct)
        old_oid = self.osm.position.stop_order_id if self.osm.position else None
        if old_oid:
            if inspect.iscoroutinefunction(getattr(self.adapter, 'cancel_order', None)):
                await self.adapter.cancel_order(old_oid)
            else:
                await asyncio.to_thread(self.adapter.cancel_order, old_oid)

        if inspect.iscoroutinefunction(getattr(self.adapter, 'place_stop_limit', None)):
            new_oid = await self.adapter.place_stop_limit(client_id=old_oid or 'stop', trigger=new_trigger, limit=new_limit, qty=self.osm.position.qty_filled)
        else:
            new_oid = await asyncio.to_thread(self.adapter.place_stop_limit, old_oid or 'stop', new_trigger, new_limit, self.osm.position.qty_filled)
        self.osm.position.stop_order_id = new_oid
        await asyncio.to_thread(self.persistence.save_position, self.osm.position)
