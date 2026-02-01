"""P&L calculator for trade analysis."""
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class Fill:
    """A single order fill."""
    order_id: str
    side: str  # "buy" or "sell"
    price: Decimal
    qty: Decimal
    timestamp: int  # Unix timestamp
    
    @property
    def notional(self) -> Decimal:
        """Total notional value of the fill."""
        return self.price * self.qty


@dataclass
class TradeAnalysis:
    """Summary of a completed trade."""
    entry_price: Decimal
    entry_qty: Decimal
    exit_price: Optional[Decimal]
    exit_qty: Optional[Decimal]
    highest_price: Decimal
    lowest_price: Decimal
    realized_pnl: Decimal  # entry_notional - exit_notional
    unrealized_pnl: Optional[Decimal]  # (market_price - entry_price) * remaining_qty
    pnl_percent: Decimal
    duration_seconds: Optional[int]


def calculate_pnl(
    entry_price: Decimal,
    entry_qty: Decimal,
    exit_price: Optional[Decimal] = None,
    exit_qty: Optional[Decimal] = None,
    current_price: Optional[Decimal] = None,
) -> TradeAnalysis:
    """Calculate P&L for a trade.
    
    Args:
        entry_price: Entry fill price
        entry_qty: Quantity bought
        exit_price: Exit fill price (if closed)
        exit_qty: Quantity sold (if closed)
        current_price: Current market price (for unrealized)
    
    Returns:
        TradeAnalysis with realized and unrealized P&L
    """
    entry_notional = entry_price * entry_qty
    
    # Realized P&L from exit
    realized_pnl = Decimal('0')
    exit_qty = exit_qty or Decimal('0')
    if exit_qty > 0 and exit_price:
        exit_notional = exit_price * exit_qty
        realized_pnl = exit_notional - (entry_price * exit_qty)
    
    # Unrealized P&L on remaining position
    remaining_qty = entry_qty - exit_qty
    unrealized_pnl = None
    if remaining_qty > 0 and current_price:
        unrealized_pnl = (current_price - entry_price) * remaining_qty
    
    # Total P&L and percent
    total_pnl = realized_pnl + (unrealized_pnl or Decimal('0'))
    pnl_percent = (total_pnl / entry_notional) * Decimal('100') if entry_notional > 0 else Decimal('0')
    
    return TradeAnalysis(
        entry_price=entry_price,
        entry_qty=entry_qty,
        exit_price=exit_price,
        exit_qty=exit_qty,
        highest_price=current_price or exit_price or entry_price,
        lowest_price=entry_price,  # Could track minimum during position
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        pnl_percent=pnl_percent,
        duration_seconds=None,
    )


def aggregate_pnl(analyses: List[TradeAnalysis]) -> dict:
    """Aggregate P&L across multiple trades.
    
    Args:
        analyses: List of TradeAnalysis
    
    Returns:
        Dict with totals and statistics
    """
    if not analyses:
        return {
            "total_trades": 0,
            "total_realized_pnl": Decimal('0'),
            "total_unrealized_pnl": Decimal('0'),
            "win_count": 0,
            "loss_count": 0,
            "avg_pnl_percent": Decimal('0'),
        }
    
    total_realized = sum(a.realized_pnl for a in analyses)
    total_unrealized = sum((a.unrealized_pnl or Decimal('0')) for a in analyses)
    
    wins = len([a for a in analyses if a.realized_pnl > 0])
    losses = len([a for a in analyses if a.realized_pnl < 0])
    
    avg_pnl = sum(a.pnl_percent for a in analyses) / len(analyses) if analyses else Decimal('0')
    
    return {
        "total_trades": len(analyses),
        "total_realized_pnl": total_realized,
        "total_unrealized_pnl": total_unrealized,
        "total_pnl": total_realized + total_unrealized,
        "win_count": wins,
        "loss_count": losses,
        "win_rate_percent": (wins / len(analyses) * 100) if analyses else Decimal('0'),
        "avg_pnl_percent": avg_pnl,
    }
