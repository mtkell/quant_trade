"""Portfolio manager for multi-pair trading orchestration and risk management."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from .position import PositionState


@dataclass
class PortfolioConfig:
    """Portfolio-level configuration."""
    total_capital: Decimal
    max_position_size_pct: Decimal = Decimal('5')  # Max 5% per position
    max_positions: int = 10  # Max 10 concurrent positions
    max_correlated_exposure_pct: Decimal = Decimal('20')  # Max 20% in correlated pairs
    rebalance_threshold_pct: Decimal = Decimal('10')  # Rebalance if > 10% drift
    emergency_liquidation_loss_pct: Decimal = Decimal('-10')  # Auto-liquidate at -10%


@dataclass
class PairConfig:
    """Per-pair configuration."""
    product_id: str  # e.g., "BTC-USD", "ETH-USD"
    enabled: bool = True
    position_size_pct: Decimal = Decimal('2')  # Allocate 2% per pair
    trail_pct: Decimal = Decimal('0.02')  # 2% trailing stop
    entry_confirmation_level: int = 2  # Need 2/3 indicators
    max_entry_wait_minutes: int = 5
    correlation_group: Optional[str] = None  # e.g., "large_cap", "alts"


@dataclass
class PortfolioPosition:
    """Portfolio-level position tracking."""
    position_id: str
    product_id: str
    state: PositionState
    opened_at: str  # ISO timestamp
    target_size_pct: Decimal
    current_pnl: Decimal = Decimal('0')
    current_pnl_pct: Decimal = Decimal('0')
    status: str = "active"  # active, closed, liquidated


@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics."""
    total_capital: Decimal
    available_capital: Decimal
    deployed_capital: Decimal
    total_positions: int
    active_positions: int
    closed_positions: int
    
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    total_return_pct: Decimal = Decimal('0')
    
    largest_position_pct: Decimal = Decimal('0')
    concentration_pct: Decimal = Decimal('0')  # Top 3 positions as % of capital
    
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown_pct: Decimal = Decimal('0')
    win_rate_pct: Decimal = Decimal('0')


class PortfolioManager:
    """Manage multiple trading positions across different pairs."""
    
    def __init__(self, config: PortfolioConfig):
        self.config = config
        self.pair_configs: Dict[str, PairConfig] = {}
        self.positions: Dict[str, PortfolioPosition] = {}
        self.closed_positions: List[PortfolioPosition] = []
        
    def register_pair(self, pair_config: PairConfig) -> None:
        """Register a new trading pair."""
        if not pair_config.enabled:
            return
        
        if len(self.pair_configs) >= self.config.max_positions:
            raise ValueError(f"Max positions ({self.config.max_positions}) reached")
        
        self.pair_configs[pair_config.product_id] = pair_config
    
    def get_position_size_usd(self, product_id: str) -> Decimal:
        """Get allocated position size in USD."""
        if product_id not in self.pair_configs:
            return Decimal('0')
        
        pair_config = self.pair_configs[product_id]
        return self.config.total_capital * (pair_config.position_size_pct / 100)
    
    def add_position(self, position_id: str, product_id: str, pos_state: PositionState) -> None:
        """Add a new position to portfolio."""
        if product_id not in self.pair_configs:
            raise ValueError(f"Pair {product_id} not registered")
        
        if len(self.positions) >= self.config.max_positions:
            raise ValueError(f"Max positions ({self.config.max_positions}) reached")
        
        pair_config = self.pair_configs[product_id]
        position = PortfolioPosition(
            position_id=position_id,
            product_id=product_id,
            state=pos_state,
            opened_at="",
            target_size_pct=pair_config.position_size_pct
        )
        self.positions[position_id] = position
    
    def update_position(self, position_id: str, pos_state: PositionState, current_price: Optional[Decimal] = None) -> None:
        """Update position state and calculate P&L."""
        if position_id not in self.positions:
            raise ValueError(f"Position {position_id} not found")
        
        pos = self.positions[position_id]
        pos.state = pos_state
        
        # Calculate unrealized P&L
        if current_price and pos.state.qty_filled > 0:
            pnl = (current_price - pos.state.entry_price) * pos.state.qty_filled
            pnl_pct = ((current_price - pos.state.entry_price) / pos.state.entry_price * 100) if pos.state.entry_price > 0 else Decimal('0')
            pos.current_pnl = pnl
            pos.current_pnl_pct = pnl_pct
            
            # Check emergency liquidation
            if pnl_pct <= self.config.emergency_liquidation_loss_pct:
                pos.status = "liquidated"
    
    def close_position(self, position_id: str, exit_price: Decimal) -> Decimal:
        """Close a position and calculate realized P&L."""
        if position_id not in self.positions:
            raise ValueError(f"Position {position_id} not found")
        
        pos = self.positions.pop(position_id)
        realized_pnl = (exit_price - pos.state.entry_price) * pos.state.qty_filled
        pos.state.qty_filled = Decimal('0')
        pos.status = "closed"
        pos.current_pnl = realized_pnl
        
        self.closed_positions.append(pos)
        return realized_pnl
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate portfolio-level metrics."""
        deployed = sum(
            pos.state.entry_price * pos.state.qty_filled
            for pos in self.positions.values()
            if pos.state.qty_filled > 0
        )
        
        unrealized = sum(pos.current_pnl for pos in self.positions.values())
        realized = sum(pos.current_pnl for pos in self.closed_positions)
        total_pnl = realized + unrealized
        
        total_return = (total_pnl / self.config.total_capital * 100) if self.config.total_capital > 0 else Decimal('0')
        
        # Calculate position concentration
        position_sizes = sorted(
            [pos.state.entry_price * pos.state.qty_filled for pos in self.positions.values()],
            reverse=True
        )
        top_3_sum = sum(position_sizes[:3])
        concentration = (top_3_sum / self.config.total_capital * 100) if self.config.total_capital > 0 else Decimal('0')
        
        # Win rate across closed positions
        wins = len([p for p in self.closed_positions if p.current_pnl > 0])
        total_closed = len(self.closed_positions)
        win_rate = (Decimal(wins) / Decimal(total_closed) * 100) if total_closed > 0 else Decimal('0')
        
        return PortfolioMetrics(
            total_capital=self.config.total_capital,
            available_capital=self.config.total_capital - deployed,
            deployed_capital=deployed,
            total_positions=len(self.positions) + len(self.closed_positions),
            active_positions=len(self.positions),
            closed_positions=len(self.closed_positions),
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_pnl=total_pnl,
            total_return_pct=total_return,
            largest_position_pct=(position_sizes[0] / self.config.total_capital * 100) if position_sizes and self.config.total_capital > 0 else Decimal('0'),
            concentration_pct=concentration,
            win_rate_pct=win_rate,
        )
    
    def check_risk_limits(self) -> Dict[str, str]:
        """Check if portfolio violates any risk limits."""
        issues = {}
        
        metrics = self.get_portfolio_metrics()
        
        # Check position count
        if metrics.active_positions > self.config.max_positions:
            issues["max_positions"] = f"Active positions ({metrics.active_positions}) > limit ({self.config.max_positions})"
        
        # Check position size
        largest_pct = metrics.largest_position_pct
        if largest_pct > self.config.max_position_size_pct:
            issues["position_size"] = f"Largest position ({largest_pct:.1f}%) > limit ({self.config.max_position_size_pct}%)"
        
        # Check concentration
        if metrics.concentration_pct > self.config.max_correlated_exposure_pct:
            issues["concentration"] = f"Top 3 concentration ({metrics.concentration_pct:.1f}%) > limit ({self.config.max_correlated_exposure_pct}%)"
        
        return issues
    
    def get_rebalance_actions(self) -> List[Dict]:
        """Identify positions that need rebalancing."""
        actions = []
        metrics = self.get_portfolio_metrics()
        
        for pos_id, pos in self.positions.items():
            current_pct = (pos.state.entry_price * pos.state.qty_filled / self.config.total_capital * 100) if self.config.total_capital > 0 else Decimal('0')
            target_pct = pos.target_size_pct
            drift = abs(current_pct - target_pct)
            
            if drift > self.config.rebalance_threshold_pct:
                actions.append({
                    "position_id": pos_id,
                    "product_id": pos.product_id,
                    "current_pct": float(current_pct),
                    "target_pct": float(target_pct),
                    "drift_pct": float(drift),
                    "action": "increase" if current_pct < target_pct else "decrease"
                })
        
        return actions
