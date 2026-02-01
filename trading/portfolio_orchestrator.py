"""Multi-pair execution orchestrator for coordinated trading across pairs."""
import asyncio
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from .async_execution import AsyncExecutionEngine
from .portfolio_manager import PortfolioConfig, PortfolioManager, PairConfig
from .position import PositionState


class MultiPairOrchestrator:
    """Orchestrate trading across multiple pairs with coordinated entry/exit."""
    
    def __init__(self, portfolio_config: PortfolioConfig):
        self.portfolio_config = portfolio_config
        self.portfolio_manager = PortfolioManager(portfolio_config)
        self.engines: Dict[str, AsyncExecutionEngine] = {}
        self.price_callbacks: Dict[str, Callable] = {}
        
    def register_pair(self, pair_config: PairConfig, engine: AsyncExecutionEngine) -> None:
        """Register a trading pair with its execution engine."""
        self.portfolio_manager.register_pair(pair_config)
        self.engines[pair_config.product_id] = engine
    
    async def check_all_entries(self, signal_generator: Callable) -> Dict[str, bool]:
        """Check entry signals across all pairs simultaneously.
        
        Args:
            signal_generator: Async callable that takes product_id and returns (should_buy, signal_data)
        
        Returns:
            Dict mapping product_id to entry_triggered (True/False)
        """
        tasks = [
            signal_generator(product_id)
            for product_id in self.engines.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        entry_signals = {}
        
        for product_id, result in zip(self.engines.keys(), results):
            if isinstance(result, Exception):
                entry_signals[product_id] = False
            else:
                entry_signals[product_id] = result.get('should_buy', False) if result else False
        
        return entry_signals
    
    async def submit_coordinated_entries(
        self,
        entries_by_pair: Dict[str, Dict],  # {product_id: {price, qty, ...}}
        max_concurrent: int = 3
    ) -> Dict[str, str]:
        """Submit multiple entry orders with controlled concurrency.
        
        Args:
            entries_by_pair: Dict mapping product_id to entry params
            max_concurrent: Max concurrent orders to place
        
        Returns:
            Dict mapping product_id to order_id
        """
        # Check risk limits before submitting
        risk_issues = self.portfolio_manager.check_risk_limits()
        if risk_issues:
            raise RuntimeError(f"Portfolio risk limits violated: {risk_issues}")
        
        order_ids = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def submit_entry(product_id: str, entry_params: Dict):
            async with semaphore:
                engine = self.engines[product_id]
                position_id = f"{product_id}_{len(self.portfolio_manager.positions)}"
                
                order_id = await engine.submit_entry(
                    position_id=position_id,
                    price=entry_params['price'],
                    qty=entry_params['qty']
                )
                
                # Track in portfolio
                pos = PositionState(
                    entry_price=entry_params['price'],
                    qty_filled=entry_params['qty'],
                    highest_price_since_entry=entry_params['price'],
                    current_stop_trigger=entry_params.get('stop_trigger'),
                    current_stop_limit=entry_params.get('stop_limit'),
                    stop_order_id=None
                )
                self.portfolio_manager.add_position(position_id, product_id, pos)
                
                return order_id
        
        tasks = [
            submit_entry(product_id, params)
            for product_id, params in entries_by_pair.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for product_id, result in zip(entries_by_pair.keys(), results):
            if not isinstance(result, Exception):
                order_ids[product_id] = result
        
        return order_ids
    
    async def handle_price_update(self, product_id: str, last_price: Decimal) -> None:
        """Handle price update for a single pair."""
        if product_id not in self.engines:
            return
        
        # Find active position for this product
        active_position = None
        position_id = None
        for pid, pos in self.portfolio_manager.positions.items():
            if pos.product_id == product_id:
                active_position = pos
                position_id = pid
                break
        
        if not active_position:
            return
        
        # Update portfolio tracking
        self.portfolio_manager.update_position(
            position_id,
            active_position.state,
            last_price
        )
        
        # Delegate trailing stop management to engine
        engine = self.engines[product_id]
        await engine.on_trade(position_id, last_price)
    
    async def emergency_liquidate_pair(self, product_id: str, current_price: Decimal) -> Dict:
        """Emergency liquidation of a pair's position."""
        results = {"product_id": product_id, "closed_positions": []}
        
        # Find all positions for this product
        positions_to_close = [
            (pid, pos) for pid, pos in self.portfolio_manager.positions.items()
            if pos.product_id == product_id and pos.status == "active"
        ]
        
        for position_id, pos in positions_to_close:
            engine = self.engines[product_id]
            
            # Cancel pending orders
            await engine.handle_stop_timeout(position_id)
            
            # Close position
            realized_pnl = self.portfolio_manager.close_position(position_id, current_price)
            
            results["closed_positions"].append({
                "position_id": position_id,
                "exit_price": float(current_price),
                "realized_pnl": float(realized_pnl)
            })
        
        return results
    
    async def emergency_liquidate_portfolio(self, prices_by_product: Dict[str, Decimal]) -> Dict:
        """Emergency liquidation of entire portfolio."""
        results = {"total_pnl": Decimal('0'), "closed_count": 0}
        
        tasks = [
            self.emergency_liquidate_pair(product_id, prices_by_product[product_id])
            for product_id in self.engines.keys()
            if product_id in prices_by_product
        ]
        
        pair_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in pair_results:
            if isinstance(result, Exception):
                continue
            for closed_pos in result.get("closed_positions", []):
                results["total_pnl"] += Decimal(str(closed_pos["realized_pnl"]))
                results["closed_count"] += 1
        
        return results
    
    def get_portfolio_status(self) -> Dict:
        """Get current portfolio status."""
        metrics = self.portfolio_manager.get_portfolio_metrics()
        risk_issues = self.portfolio_manager.check_risk_limits()
        rebalance_actions = self.portfolio_manager.get_rebalance_actions()
        
        return {
            "metrics": {
                "total_capital": float(metrics.total_capital),
                "available_capital": float(metrics.available_capital),
                "deployed_capital": float(metrics.deployed_capital),
                "active_positions": metrics.active_positions,
                "closed_positions": metrics.closed_positions,
                "realized_pnl": float(metrics.realized_pnl),
                "unrealized_pnl": float(metrics.unrealized_pnl),
                "total_pnl": float(metrics.total_pnl),
                "total_return_pct": float(metrics.total_return_pct),
                "concentration_pct": float(metrics.concentration_pct),
                "win_rate_pct": float(metrics.win_rate_pct),
            },
            "risk_violations": risk_issues,
            "rebalance_needed": len(rebalance_actions) > 0,
            "rebalance_actions": rebalance_actions,
            "pairs_registered": len(self.engines),
        }
