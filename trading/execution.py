"""
Synchronous execution engine for spot trading.

Provides order lifecycle management, position tracking, and automatic stop ratcheting.
Uses abstract adapter pattern to support multiple exchanges.
"""

import json
from abc import ABC, abstractmethod
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .order_state import OrderStateMachine
from .position import PositionState
from .logging_setup import logger


class ExchangeAdapter(ABC):
    """Abstract exchange adapter for placing/canceling orders and checking status.

    All price/qty values use Decimal for precision and consistency.
    """

    @abstractmethod
    def place_limit_buy(self, client_id: str, price: Decimal, qty: Decimal) -> str:
        """Place a limit buy order.

        Args:
            client_id: Client-assigned order ID for tracking
            price: Buy price as Decimal
            qty: Quantity to buy as Decimal

        Returns:
            Exchange order ID
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.

        Args:
            order_id: Exchange order ID to cancel

        Returns:
            True if cancelled successfully, False otherwise
        """
        pass

    @abstractmethod
    def place_stop_limit(
        self, client_id: str, trigger: Decimal, limit: Decimal, qty: Decimal
    ) -> str:
        """Place a stop-limit sell order.

        Args:
            client_id: Client-assigned order ID for tracking
            trigger: Stop trigger price as Decimal
            limit: Limit price as Decimal (usually below trigger)
            qty: Quantity to sell as Decimal

        Returns:
            Exchange order ID
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get current order status.

        Args:
            order_id: Exchange order ID

        Returns:
            Dict with order details or None if not found
        """
        pass


class InMemoryAdapter(ExchangeAdapter):
    """A simple adapter used for tests that records calls and lets tests drive fills."""

    def __init__(self):
        self.orders = {}
        self.next_id = 1

    def _gen_id(self) -> str:
        oid = f"m{self.next_id}"
        self.next_id += 1
        return oid

    def place_limit_buy(self, client_id: str, price: Decimal, qty: Decimal) -> str:
        oid = self._gen_id()
        self.orders[oid] = {
            "type": "limit",
            "client_id": client_id,
            "price": str(price),
            "qty": str(qty),
            "state": "open",
        }
        return oid

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id]["state"] = "cancelled"
            return True
        return False

    def place_stop_limit(
        self, client_id: str, trigger: Decimal, limit: Decimal, qty: Decimal
    ) -> str:
        oid = self._gen_id()
        self.orders[oid] = {
            "type": "stop_limit",
            "client_id": client_id,
            "trigger": str(trigger),
            "limit": str(limit),
            "qty": str(qty),
            "state": "open",
        }
        return oid

    def get_order_status(self, order_id: str) -> Optional[dict]:
        return self.orders.get(order_id)


class FilePersistence:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save_position(self, pos: PositionState) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(pos.to_dict(), f, indent=2)
        tmp.replace(self.path)

    def load_position(self) -> Optional[PositionState]:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return PositionState.from_dict(d)


class ExecutionEngine:
    def __init__(
        self,
        adapter: ExchangeAdapter,
        persistence: FilePersistence,
        *,
        trail_pct: Decimal = Decimal("0.02"),
        stop_limit_buffer_pct: Decimal = Decimal("0.005"),
        min_ratchet: Decimal = Decimal("0"),
    ):
        self.adapter = adapter
        self.persistence = persistence
        self.osm = OrderStateMachine()
        self.trail_pct = trail_pct
        self.stop_limit_buffer_pct = stop_limit_buffer_pct
        self.min_ratchet = min_ratchet
        # restore if persisted
        pos = self.persistence.load_position()
        if pos:
            self.osm.position = pos
            # perform reconciliation: ensure stop order exists; if not, clear stop_order_id so engine can place a replacement
            try:
                if self.osm.position.stop_order_id:
                    status = self.adapter.get_order_status(self.osm.position.stop_order_id)
                    if status is None or status.get("state") not in ("open", "pending"):
                        # mark stop as missing so we will replace it
                        self.osm.position.stop_order_id = None
                        self.persistence.save_position(self.osm.position)
                else:
                    # no stop recorded but we have trigger/limit: place a stop
                    if (
                        self.osm.position.current_stop_trigger
                        and self.osm.position.current_stop_limit
                    ):
                        oid = self.adapter.place_stop_limit(
                            client_id="reconcile",
                            trigger=self.osm.position.current_stop_trigger,
                            limit=self.osm.position.current_stop_limit,
                            qty=self.osm.position.qty_filled,
                        )
                        self.osm.position.stop_order_id = oid
                        self.persistence.save_position(self.osm.position)
                # if we cleared the stop above, place a replacement now
                if (
                    not self.osm.position.stop_order_id
                    and self.osm.position.current_stop_trigger
                    and self.osm.position.current_stop_limit
                ):
                    oid = self.adapter.place_stop_limit(
                        client_id="reconcile",
                        trigger=self.osm.position.current_stop_trigger,
                        limit=self.osm.position.current_stop_limit,
                        qty=self.osm.position.qty_filled,
                    )
                    self.osm.position.stop_order_id = oid
                    self.persistence.save_position(self.osm.position)
            except Exception:
                # don't fail startup; log in production
                pass

    def submit_entry(self, client_id: str, price: Decimal, qty: Decimal) -> str:
        # place order via adapter and record client order
        oid = self.adapter.place_limit_buy(client_id=client_id, price=price, qty=qty)
        self.osm.place_entry(order_id=oid, price=price, qty=qty)
        logger.info(f"Entry order placed | order_id={oid} price={price} qty={qty}")
        return oid

    def handle_fill(self, order_id: str, filled_qty: Decimal, fill_price: Decimal) -> None:
        self.osm.on_fill(order_id=order_id, filled_qty=filled_qty, fill_price=fill_price)
        logger.info(
            f"Order filled | order_id={order_id} filled_qty={filled_qty} fill_price={fill_price}"
        )
        # persist position state if present
        if self.osm.position:
            # ensure initial stop is computed using configured trail settings
            # this will set current_stop_trigger/current_stop_limit if absent
            self.osm.position.ratchet_stop(
                last_trade_price=fill_price,
                trail_pct=self.trail_pct,
                stop_limit_buffer_pct=self.stop_limit_buffer_pct,
                min_ratchet=self.min_ratchet,
            )

            self.persistence.save_position(self.osm.position)

            # place initial stop if created
            if self.osm.position.current_stop_trigger and not self.osm.position.stop_order_id:
                oid = self.adapter.place_stop_limit(
                    client_id=order_id,
                    trigger=self.osm.position.current_stop_trigger,
                    limit=self.osm.position.current_stop_limit,
                    qty=self.osm.position.qty_filled,
                )
                self.osm.position.stop_order_id = oid
                self.persistence.save_position(self.osm.position)
                logger.info(
                    f"Stop order placed | stop_order_id={oid} trigger={self.osm.position.current_stop_trigger} limit={self.osm.position.current_stop_limit}"
                )

    def on_trade(
        self,
        last_trade_price: Decimal,
        trail_pct: Decimal,
        stop_limit_buffer_pct: Decimal,
        min_ratchet: Decimal,
    ):
        changed, stop = self.osm.on_trade(
            last_trade_price=last_trade_price,
            trail_pct=trail_pct,
            stop_limit_buffer_pct=stop_limit_buffer_pct,
            min_ratchet=min_ratchet,
        )
        if changed and stop:
            logger.info(
                f"Stop ratcheted | last_trade_price={last_trade_price} new_trigger={stop[0]} new_limit={stop[1]}"
            )
            # cancel old stop and place new one
            old_oid = self.osm.position.stop_order_id
            if old_oid:
                self.adapter.cancel_order(old_oid)
            new_oid = self.adapter.place_stop_limit(
                client_id=old_oid or "stop",
                trigger=stop[0],
                limit=stop[1],
                qty=self.osm.position.qty_filled,
            )
            self.osm.position.stop_order_id = new_oid
            self.persistence.save_position(self.osm.position)

    def handle_stop_timeout(self, aggressive_price_delta_pct: Decimal):
        new_trigger, new_limit = self.osm.stop_timeout_replacement(
            aggressive_price_delta_pct=aggressive_price_delta_pct
        )
        logger.warning(
            f"Stop timeout detected | old_trigger={self.osm.position.current_stop_trigger} new_trigger={new_trigger}"
        )
        # cancel old stop and place new one
        old_oid = self.osm.position.stop_order_id if self.osm.position else None
        if old_oid:
            self.adapter.cancel_order(old_oid)
        new_oid = self.adapter.place_stop_limit(
            client_id=old_oid or "stop",
            trigger=new_trigger,
            limit=new_limit,
            qty=self.osm.position.qty_filled,
        )
        self.osm.position.stop_order_id = new_oid
        self.persistence.save_position(self.osm.position)
        logger.info(f"Stop replaced with aggressive pricing | new_stop_order_id={new_oid}")
