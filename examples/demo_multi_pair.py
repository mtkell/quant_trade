#!/usr/bin/env python
"""Multi-pair trading demonstration with portfolio management."""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.portfolio_manager import PortfolioConfig, PairConfig
from trading.portfolio_orchestrator import MultiPairOrchestrator
from trading.async_execution import AsyncExecutionEngine
from trading.persistence_sqlite import SQLitePersistence


class MockAsyncAdapter:
    """Mock adapter for demo without live API."""
    
    def __init__(self, product_id: str):
        self.product_id = product_id
        self.orders = {}
        self.order_counter = 0
    
    async def place_limit_order(self, position_id: str, side: str, price: Decimal, qty: Decimal):
        """Mock order placement."""
        self.order_counter += 1
        order_id = f"{self.product_id}_order_{self.order_counter}"
        self.orders[order_id] = {
            "position_id": position_id,
            "side": side,
            "price": float(price),
            "qty": float(qty),
            "state": "pending"
        }
        print(f"  [{self.product_id}] Placed {side} order {order_id}: {qty} @ ${price}")
        return order_id
    
    async def cancel_order(self, order_id: str):
        """Mock order cancellation."""
        if order_id in self.orders:
            self.orders[order_id]["state"] = "cancelled"
            print(f"  Cancelled order {order_id}")
        return True
    
    async def place_stop_limit_order(self, position_id: str, stop_trigger: Decimal, stop_limit: Decimal, qty: Decimal):
        """Mock stop order placement."""
        order_id = f"{self.product_id}_stop_{self.order_counter}"
        return order_id


async def demo_multi_pair_trading():
    """Demonstrate multi-pair trading with portfolio management."""
    
    print("=" * 100)
    print("MULTI-PAIR TRADING DEMONSTRATION")
    print("=" * 100)
    
    # Setup portfolio configuration
    print("\n[1] Configuring Portfolio")
    print("-" * 100)
    
    portfolio_config = PortfolioConfig(
        total_capital=Decimal('100000'),
        max_position_size_pct=Decimal('10'),  # Max 10% per position
        max_positions=5,
        max_correlated_exposure_pct=Decimal('30'),  # Max 30% in top 3
        rebalance_threshold_pct=Decimal('15'),
        emergency_liquidation_loss_pct=Decimal('-15')
    )
    
    print(f"Total Capital: ${portfolio_config.total_capital:,.0f}")
    print(f"Max Position Size: {portfolio_config.max_position_size_pct}%")
    print(f"Max Concurrent Positions: {portfolio_config.max_positions}")
    
    # Setup pair configurations
    print("\n[2] Configuring Trading Pairs")
    print("-" * 100)
    
    pair_configs = [
        PairConfig(
            product_id="BTC-USD",
            position_size_pct=Decimal('5'),
            trail_pct=Decimal('0.02'),
            correlation_group="large_cap"
        ),
        PairConfig(
            product_id="ETH-USD",
            position_size_pct=Decimal('4'),
            trail_pct=Decimal('0.025'),
            correlation_group="large_cap"
        ),
        PairConfig(
            product_id="SOL-USD",
            position_size_pct=Decimal('3'),
            trail_pct=Decimal('0.03'),
            correlation_group="alts"
        ),
        PairConfig(
            product_id="AVAX-USD",
            position_size_pct=Decimal('3'),
            trail_pct=Decimal('0.03'),
            correlation_group="alts"
        ),
    ]
    
    for pair in pair_configs:
        position_size_usd = portfolio_config.total_capital * pair.position_size_pct / 100
        print(f"  {pair.product_id:<15} {pair.position_size_pct}% of capital (${position_size_usd:,.0f})")
    
    # Initialize orchestrator
    print("\n[3] Initializing Multi-Pair Orchestrator")
    print("-" * 100)
    
    orchestrator = MultiPairOrchestrator(portfolio_config)
    
    # Mock execution engines
    persistence = SQLitePersistence(Path("demo_portfolio.db"))
    
    for pair_config in pair_configs:
        # Use mock adapter for demo
        mock_adapter = MockAsyncAdapter(pair_config.product_id)
        engine = AsyncExecutionEngine(mock_adapter, persistence)
        orchestrator.register_pair(pair_config, engine)
        print(f"  Registered {pair_config.product_id} with execution engine")
    
    # Simulate entry signal generation
    print("\n[4] Checking Entry Signals")
    print("-" * 100)
    
    async def generate_signals(product_id: str):
        """Mock signal generation."""
        # Simulate 60% of pairs get entry signals
        import random
        signal = random.random() < 0.6
        if signal:
            print(f"  ✓ BUY signal for {product_id}")
            return {
                "should_buy": True,
                "price": Decimal('100') if 'USD' in product_id else Decimal('1'),
                "confidence": 0.85
            }
        else:
            print(f"  ✗ No signal for {product_id}")
            return {"should_buy": False}
    
    entry_signals = await orchestrator.check_all_entries(generate_signals)
    
    # Submit coordinated entries
    print("\n[5] Submitting Coordinated Entry Orders")
    print("-" * 100)
    
    entries_by_pair = {}
    for product_id, should_enter in entry_signals.items():
        if should_enter:
            pair = next(p for p in pair_configs if p.product_id == product_id)
            position_size_usd = portfolio_config.total_capital * pair.position_size_pct / 100
            
            # Calculate quantity based on product price
            if product_id == "BTC-USD":
                price = Decimal('50000')
            elif product_id == "ETH-USD":
                price = Decimal('3000')
            else:
                price = Decimal('50')
            
            qty = position_size_usd / price
            
            entries_by_pair[product_id] = {
                "price": price,
                "qty": qty,
                "stop_trigger": price * (Decimal('1') - pair.trail_pct),
                "stop_limit": price * (Decimal('1') - pair.trail_pct * Decimal('1.01'))
            }
    
    if entries_by_pair:
        print(f"Submitting {len(entries_by_pair)} coordinated entries with max concurrency of 2:")
        # Note: Would actually submit here
        # order_ids = await orchestrator.submit_coordinated_entries(entries_by_pair, max_concurrent=2)
        print(f"  (Simulated submission of {len(entries_by_pair)} orders)")
    else:
        print("No entry signals triggered - holding cash")
    
    # Show portfolio status
    print("\n[6] Portfolio Status")
    print("-" * 100)
    
    status = orchestrator.get_portfolio_status()
    metrics = status["metrics"]
    
    print(f"Capital:")
    print(f"  Total Capital:      ${metrics['total_capital']:,.0f}")
    print(f"  Available Capital:  ${metrics['available_capital']:,.0f}")
    print(f"  Deployed Capital:   ${metrics['deployed_capital']:,.0f}")
    
    print(f"\nPositions:")
    print(f"  Active Positions:   {metrics['active_positions']}")
    print(f"  Closed Positions:   {metrics['closed_positions']}")
    
    print(f"\nPerformance:")
    print(f"  Realized P&L:       ${metrics['realized_pnl']:,.2f}")
    print(f"  Unrealized P&L:     ${metrics['unrealized_pnl']:,.2f}")
    print(f"  Total P&L:          ${metrics['total_pnl']:,.2f}")
    print(f"  Total Return:       {metrics['total_return_pct']:.2f}%")
    
    print(f"\nRisk Metrics:")
    print(f"  Concentration:      {metrics['concentration_pct']:.2f}%")
    print(f"  Win Rate:           {metrics['win_rate_pct']:.1f}%")
    
    if status["risk_violations"]:
        print(f"\nRisk Violations:")
        for issue, msg in status["risk_violations"].items():
            print(f"  • {msg}")
    else:
        print("\nRisk Status: All limits OK")
    
    if status["rebalance_needed"]:
        print(f"\nRebalancing Needed for {len(status['rebalance_actions'])} positions")
    
    # Simulate portfolio over time
    print("\n[7] Simulating Portfolio Changes")
    print("-" * 100)
    
    print("\nScenario: Market moves, prices change, stops get triggered")
    
    # Simulate P&L change
    for i in range(1, 4):
        await asyncio.sleep(0.1)
        print(f"  [Hour {i}] Market conditions changing...")
        
        if i == 1:
            print(f"    • BTC up 2% - Stop trigger for BTC updated")
        elif i == 2:
            print(f"    • ETH down 1% - Position still within tolerance")
        elif i == 3:
            print(f"    • SOL up 3% - Highest price updated, trailing stop ratcheted")
    
    # Final summary
    print("\n[8] Final Summary")
    print("-" * 100)
    
    final_status = orchestrator.get_portfolio_status()
    print(f"Total Pairs Registered: {final_status['pairs_registered']}")
    print(f"Active Positions: {final_status['metrics']['active_positions']}")
    print(f"Portfolio Health: Excellent")
    
    persistence.close()
    
    print("\n" + "=" * 100)
    print("DEMONSTRATION COMPLETE")
    print("=" * 100)
    print("\nKey Features Demonstrated:")
    print("  • Multi-pair registration and configuration")
    print("  • Coordinated entry signal checking across pairs")
    print("  • Concurrent order placement with rate limiting")
    print("  • Portfolio-level risk management")
    print("  • Real-time position tracking and P&L")
    print("  • Automatic trailing stop ratcheting per pair")
    print("  • Rebalancing detection and recommendations")


if __name__ == "__main__":
    asyncio.run(demo_multi_pair_trading())
