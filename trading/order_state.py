"""
Order state machine for entry and exit lifecycle.

Manages the lifecycle of buy entry orders and tracks position state changes
as fills are received. Integrates with PositionState for stop ratcheting logic.

State Transitions:
    ENTRY ORDER:
        NEW → OPEN → PARTIALLY_FILLED / FILLED → CANCELLED

    STOP ORDER:
        NEW → OPEN → STOP_TRIGGERED / CANCELLED

Typical Flow:
    1. Create OSM, call place_entry() → entry_order in OPEN state
    2. Receive fill(s) → on_fill() updates order state, creates PositionState
    3. Receive trade prices → on_trade() ratchets stop if needed
    4. Stop triggers → external actor cancels and places new stop or market sells

Examples:
    >>> from decimal import Decimal
    >>> osm = OrderStateMachine()
    >>> entry = osm.place_entry("order_123", Decimal("50000"), Decimal("1"))
    >>> osm.on_fill("order_123", Decimal("0.5"), Decimal("50010"))
    >>> osm.on_fill("order_123", Decimal("0.5"), Decimal("50020"))
    >>> should_replace, stop_prices = osm.on_trade(
    ...     Decimal("51000"),
    ...     trail_pct=Decimal("0.02"),
    ...     stop_limit_buffer_pct=Decimal("0.005"),
    ...     min_ratchet=Decimal("0.001")
    ... )
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto
from typing import Optional, Tuple

from .position import PositionState


class OrderSide(Enum):
    """Order side: BUY or SELL."""

    BUY = auto()
    SELL = auto()


class OrderState(Enum):
    """Order lifecycle states."""

    NEW = auto()  # Just created
    OPEN = auto()  # Submitted to exchange
    PARTIALLY_FILLED = auto()  # Some fills received
    FILLED = auto()  # Fully filled
    CANCELLED = auto()  # Cancelled by user or timeout
    STOP_PLACED = auto()  # Stop order placed
    STOP_TRIGGERED = auto()  # Stop was triggered


@dataclass
class Order:
    """Represents a single order (entry, stop, etc).

    Attributes:
        order_id: Exchange-assigned order ID
        side: BUY or SELL
        price: Original order price
        qty: Original order quantity
        filled: Cumulative fill quantity (may be less than qty)
        state: Current OrderState
    """

    order_id: str
    side: OrderSide
    price: Decimal
    qty: Decimal
    filled: Decimal = Decimal("0")
    state: OrderState = OrderState.NEW


class OrderStateMachine:
    """Minimal execution/state machine integrating PositionState.

    Responsibilities:
    - Track entry limit order state through fills
    - Initialize and update PositionState on first fill
    - Compute trailing stop levels via PositionState.ratchet_stop()
    - Provide stop timeout recovery mechanism

    Attributes:
        entry_order: The current entry Order (or None if not placed)
        position: The active PositionState (or None if no fills yet)

    Note:
        This is a state container; callers are responsible for persistence
        and exchange order lifecycle management.
    """

    def __init__(self) -> None:
        """Initialize empty state machine."""
        self.entry_order: Optional[Order] = None
        self.position: Optional[PositionState] = None

    def place_entry(self, order_id: str, price: Decimal, qty: Decimal) -> Order:
        """Place a limit buy entry order.

        Args:
            order_id: Exchange-assigned order ID
            price: Buy price
            qty: Buy quantity

        Returns:
            The created Order object
        """
        self.entry_order = Order(
            order_id=order_id,
            side=OrderSide.BUY,
            price=price,
            qty=qty,
            state=OrderState.OPEN,
        )
        return self.entry_order

    def on_fill(self, order_id: str, filled_qty: Decimal, fill_price: Decimal) -> None:
        """Process a fill/execution on the entry order.

        On first fill, creates a PositionState with entry price set to fill_price.
        On subsequent fills, updates position with weighted average entry price.

        Args:
            order_id: Order ID being filled
            filled_qty: Quantity filled in this execution
            fill_price: Price of this execution

        Raises:
            ValueError: If order_id does not match current entry_order
        """
        # apply fill to entry order
        if not self.entry_order or self.entry_order.order_id != order_id:
            raise ValueError("Unknown order_id")

        self.entry_order.filled += filled_qty
        if self.entry_order.filled < self.entry_order.qty:
            self.entry_order.state = OrderState.PARTIALLY_FILLED
        else:
            self.entry_order.state = OrderState.FILLED

        # initialize position on first fill or update qty
        if self.position is None:
            self.position = PositionState(
                entry_price=fill_price,
                qty_filled=self.entry_order.filled,
                highest_price_since_entry=fill_price,
            )
        else:
            # update qty and entry price weighted average (simple approach)
            prev_qty = self.position.qty_filled
            total_qty = prev_qty + filled_qty
            self.position.entry_price = (
                self.position.entry_price * prev_qty + fill_price * filled_qty
            ) / total_qty
            self.position.qty_filled = total_qty

    def on_trade(
        self,
        last_trade_price: Decimal,
        trail_pct: Decimal,
        stop_limit_buffer_pct: Decimal,
        min_ratchet: Decimal,
    ) -> Tuple[bool, Optional[Tuple[Decimal, Decimal]]]:
        """Handle a market trade update; ratchet stop if needed.

        Args:
            last_trade_price: Latest trade price in market
            trail_pct: Trailing stop percentage
            stop_limit_buffer_pct: Buffer between trigger and limit
            min_ratchet: Minimum ratchet threshold

        Returns:
            Tuple of (should_replace_stop, (trigger, limit) or None)
                - should_replace_stop: True if stop needs replacement
                - (trigger, limit): New stop prices if replacement needed
        """
        if self.position is None:
            return False, None

        changed = self.position.ratchet_stop(
            last_trade_price=last_trade_price,
            trail_pct=trail_pct,
            stop_limit_buffer_pct=stop_limit_buffer_pct,
            min_ratchet=min_ratchet,
        )
        if changed:
            return True, (
                self.position.current_stop_trigger,
                self.position.current_stop_limit,
            )
        return False, None

    def stop_timeout_replacement(
        self, aggressive_price_delta_pct: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Return a more aggressive replacement stop for timed-out orders.

        When a stop order fails to execute within stop_timeout_seconds,
        this method computes a replacement with a tighter trigger (closer to market).

        The new trigger is: highest * (1 - aggressive_price_delta_pct)

        Args:
            aggressive_price_delta_pct: More aggressive trailing percentage
                                       (smaller than the normal trail_pct)

        Returns:
            Tuple of (new_trigger, new_limit)

        Raises:
            RuntimeError: If no active position exists

        Note:
            This method enforces the ratchet-only invariant: it will never
            decrease the trigger below current_stop_trigger.
        """
        if self.position is None:
            raise RuntimeError("No active position")

        # make replacement by moving trigger closer to market by `aggressive_price_delta_pct`
        highest = self.position.highest_price_since_entry
        new_trigger = highest * (Decimal(1) - aggressive_price_delta_pct)
        # ensure we don't lower trigger
        if self.position.current_stop_trigger and new_trigger <= self.position.current_stop_trigger:
            new_trigger = self.position.current_stop_trigger

        new_limit = new_trigger * (Decimal(1) - Decimal("0.001"))
        # update internal record but do not decrease trigger
        if new_trigger > (self.position.current_stop_trigger or Decimal("0")):
            self.position.current_stop_trigger = new_trigger
            self.position.current_stop_limit = new_limit

        return new_trigger, new_limit
        base_trigger = highest * (Decimal(1) - Decimal("0.0"))
        new_trigger = highest * (Decimal(1) - aggressive_price_delta_pct)
        # ensure we don't lower trigger
        if self.position.current_stop_trigger and new_trigger <= self.position.current_stop_trigger:
            new_trigger = self.position.current_stop_trigger

        new_limit = new_trigger * (Decimal(1) - Decimal("0.001"))
        # update internal record but do not decrease trigger
        if new_trigger > (self.position.current_stop_trigger or Decimal("0")):
            self.position.current_stop_trigger = new_trigger
            self.position.current_stop_limit = new_limit

        return new_trigger, new_limit
