"""
Position state tracking and trailing ratchet logic.

This module provides the core PositionState dataclass which maintains:
- Entry price and quantity
- Highest price since entry (for trailing stop calculation)
- Current stop trigger and limit prices
- Stop order ID for lifecycle management

The ratchet_stop() method implements the key invariant: stops only move upward,
never downward. This ensures risk is monotonically reduced as price rises.

Examples:
    >>> from decimal import Decimal
    >>> pos = PositionState(
    ...     entry_price=Decimal("50000"),
    ...     qty_filled=Decimal("0.1"),
    ...     highest_price_since_entry=Decimal("51000")
    ... )
    >>> trigger, limit = pos.compute_new_stop(
    ...     trail_pct=Decimal("0.02"),
    ...     stop_limit_buffer_pct=Decimal("0.005")
    ... )
    >>> print(f"Trigger: {trigger}, Limit: {limit}")
    Trigger: 49980, Limit: 49745.1
"""

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Dict, Optional, Tuple

getcontext().prec = 28


@dataclass
class PositionState:
    """Tracks an active position with trailing stop logic.

    Attributes:
        entry_price: Price at which position was entered (Decimal for precision)
        qty_filled: Quantity filled for this position (Decimal)
        highest_price_since_entry: Highest price seen since entry
        current_stop_trigger: Current stop-loss trigger price (None until set)
        current_stop_limit: Current stop-loss limit price (None until set)
        stop_order_id: Exchange order ID for active stop order (None until placed)

    Invariants:
        - highest_price_since_entry >= entry_price
        - current_stop_trigger is non-decreasing (ratchet-only)
        - current_stop_limit is always <= current_stop_trigger
    """

    entry_price: Decimal
    qty_filled: Decimal
    highest_price_since_entry: Decimal
    current_stop_trigger: Optional[Decimal] = None
    current_stop_limit: Optional[Decimal] = None
    stop_order_id: Optional[str] = None

    def compute_new_stop(
        self, trail_pct: Decimal, stop_limit_buffer_pct: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Compute new stop trigger and limit from current highest price.

        The trigger is set to: highest * (1 - trail_pct)
        The limit is set to: trigger * (1 - stop_limit_buffer_pct)

        This creates a trailing stop that follows the price upward as new highs
        are reached, with a buffer between the trigger and limit to ensure
        the stop-limit can execute.

        Args:
            trail_pct: Trailing percentage below highest price (e.g., Decimal("0.02") for 2%)
            stop_limit_buffer_pct: Buffer between trigger and limit (e.g., Decimal("0.005") for 0.5%)

        Returns:
            Tuple of (new_trigger, new_limit)

        Example:
            >>> pos = PositionState(
            ...     entry_price=Decimal("50000"),
            ...     qty_filled=Decimal("1"),
            ...     highest_price_since_entry=Decimal("51000")
            ... )
            >>> trigger, limit = pos.compute_new_stop(
            ...     Decimal("0.02"), Decimal("0.005")
            ... )
            >>> print(f"{trigger}, {limit}")
            49980.0, 49745.1
        """
        highest = self.highest_price_since_entry
        new_trigger = highest * (Decimal(1) - trail_pct)
        new_limit = new_trigger * (Decimal(1) - stop_limit_buffer_pct)
        return (new_trigger, new_limit)

    def ratchet_stop(
        self,
        last_trade_price: Decimal,
        trail_pct: Decimal,
        stop_limit_buffer_pct: Decimal,
        min_ratchet: Decimal,
    ) -> bool:
        """Attempt to ratchet the stop based on a new last trade price.

        This method:
        1. Updates highest_price_since_entry if new price is higher
        2. Computes a new stop level using compute_new_stop()
        3. Only replaces the stop if the new trigger exceeds current by min_ratchet
        4. Never lowers the stop trigger (ratchet-only invariant)

        Args:
            last_trade_price: Latest market trade price (Decimal)
            trail_pct: Trailing percentage (e.g., Decimal("0.02"))
            stop_limit_buffer_pct: Buffer between trigger and limit
            min_ratchet: Minimum improvement threshold before ratcheting
                        (e.g., Decimal("0.001") for 0.1% improvement)

        Returns:
            True if a stop order replacement is required (either initial placement or ratchet),
            False otherwise (no change needed)

        Note:
            This method mutates internal state. Always persist after calling.
        """
        # Update highest seen
        if last_trade_price > self.highest_price_since_entry:
            self.highest_price_since_entry = last_trade_price

        new_trigger, new_limit = self.compute_new_stop(trail_pct, stop_limit_buffer_pct)

        # If we have no current stop, place one immediately.
        if self.current_stop_trigger is None:
            self.current_stop_trigger = new_trigger
            self.current_stop_limit = new_limit
            return True

        # Never move stop down.
        if new_trigger <= self.current_stop_trigger:
            return False

        # Only ratchet when improvement exceeds the min_ratchet fraction.
        threshold = self.current_stop_trigger * (Decimal(1) + min_ratchet)
        if new_trigger > threshold:
            self.current_stop_trigger = new_trigger
            self.current_stop_limit = new_limit
            return True

        return False

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Serialize position to dictionary for persistence.

        Returns:
            Dict with all decimal values converted to strings for JSON compatibility
        """
        return {
            "entry_price": str(self.entry_price),
            "qty_filled": str(self.qty_filled),
            "highest_price_since_entry": str(self.highest_price_since_entry),
            "current_stop_trigger": (
                str(self.current_stop_trigger) if self.current_stop_trigger is not None else None
            ),
            "current_stop_limit": (
                str(self.current_stop_limit) if self.current_stop_limit is not None else None
            ),
            "stop_order_id": self.stop_order_id,
        }

    @staticmethod
    def from_dict(d: Dict[str, Optional[str]]) -> "PositionState":
        """Deserialize position from dictionary (inverse of to_dict).

        Args:
            d: Dictionary with position data (values as strings)

        Returns:
            PositionState instance

        Raises:
            KeyError: If required keys are missing
            decimal.InvalidOperation: If values cannot be converted to Decimal
        """
        return PositionState(
            entry_price=Decimal(d["entry_price"]),
            qty_filled=Decimal(d["qty_filled"]),
            highest_price_since_entry=Decimal(d["highest_price_since_entry"]),
            current_stop_trigger=(
                Decimal(d["current_stop_trigger"])
                if d.get("current_stop_trigger") is not None
                else None
            ),
            current_stop_limit=(
                Decimal(d["current_stop_limit"])
                if d.get("current_stop_limit") is not None
                else None
            ),
            stop_order_id=d.get("stop_order_id"),
        )

    def to_dict(self) -> dict:
        return {
            "entry_price": str(self.entry_price),
            "qty_filled": str(self.qty_filled),
            "highest_price_since_entry": str(self.highest_price_since_entry),
            "current_stop_trigger": (
                str(self.current_stop_trigger) if self.current_stop_trigger is not None else None
            ),
            "current_stop_limit": (
                str(self.current_stop_limit) if self.current_stop_limit is not None else None
            ),
            "stop_order_id": self.stop_order_id,
        }

    @staticmethod
    def from_dict(d: dict) -> "PositionState":
        return PositionState(
            entry_price=Decimal(d["entry_price"]),
            qty_filled=Decimal(d["qty_filled"]),
            highest_price_since_entry=Decimal(d["highest_price_since_entry"]),
            current_stop_trigger=(
                Decimal(d["current_stop_trigger"])
                if d.get("current_stop_trigger") is not None
                else None
            ),
            current_stop_limit=(
                Decimal(d["current_stop_limit"])
                if d.get("current_stop_limit") is not None
                else None
            ),
            stop_order_id=d.get("stop_order_id"),
        )
