# Multi-Pair Portfolio Trading System

## Overview

The multi-pair portfolio system extends the single-pair trading engine to manage concurrent positions across 5-10+ product pairs with coordinated execution, portfolio-level risk management, and automated rebalancing.

## Architecture

### Core Components

```text
MultiPairOrchestrator (Async Coordinator)
  ├── PortfolioManager (State & Metrics)
  │   └── PairConfig (Per-pair settings)
  ├── AsyncExecutionEngine × N (One per pair)
  └── SQLitePersistence (Atomic state)
```

## Configuration

### Portfolio-Level Config

```python
PortfolioConfig(
    total_capital=Decimal('100000'),        # Starting capital
    max_position_size_pct=Decimal('5'),     # Max 5% per position
    max_positions=10,                        # Max concurrent positions
    max_correlated_exposure_pct=Decimal('20'), # Risk grouping limit
    rebalance_threshold_pct=Decimal('10'),  # Drift tolerance
    emergency_liquidation_loss_pct=Decimal('-10') # Circuit breaker
)
```

### Per-Pair Config

```python
PairConfig(
    product_id="BTC-USD",
    position_size_pct=Decimal('5'),         # 5% of portfolio
    trail_pct=Decimal('0.02'),              # 2% trailing stop
    entry_confirmation_level=2,              # 2/3 indicators
    max_entry_wait_candles=5,
    correlation_group="large_cap"
)
```

## Multi-Pair Workflow

### 1. Entry Coordination

```text
For each 5-min candle close:
  ├── Generate signal for each registered pair (async, parallel)
  ├── Collect all buy signals
  └── Submit coordinated entries (rate-limited, semaphore control)
      └── Max 3 concurrent order submissions
```

### 2. Trailing Stop Management

```text
On each price update:
  ├── For each active position:
  │   ├── highest_price = max(highest, current_price)
  │   ├── new_trigger = highest_price * (1 - trail_pct)
  │   └── Replace stop if new_trigger > current_trigger * (1 + min_ratchet)
  └── Ratchet upward only (never loosen stops)
```

### 3. Portfolio Risk Enforcement

```text
Before each order:
  ├── Check max_position_size_pct
  ├── Check max_positions count
  ├── Check max_correlated_exposure_pct
  └── Reject order if any limit violated
```

### 4. Rebalancing Detection

```text
Continuous monitoring:
  ├── Track position drift % from target
  ├── If drift > rebalance_threshold_pct:
  │   └── Recommend rebalancing action
  └── Flag positions exceeding max_position_size_pct
```

## API Reference

### PortfolioManager

```python
# Register pair
manager.register_pair(pair_config)

# Position tracking
manager.add_position(position_id, product_id, pos_state)
manager.update_position(position_id, pos_state, current_price)
manager.close_position(position_id, exit_price)

# Metrics
metrics = manager.get_portfolio_metrics()
# Returns: PortfolioMetrics(
#   total_capital, available_capital, deployed_capital,
#   active_positions, closed_positions, total_pnl, unrealized_pnl,
#   realized_pnl, total_return_pct, concentration_pct, win_rate_pct
# )

# Risk management
ok = manager.check_risk_limits()
violations = manager.check_risk_limit_violations()
rebalance_actions = manager.get_rebalance_actions()
```

### MultiPairOrchestrator

```python
# Setup
orch = MultiPairOrchestrator(portfolio_config)
orch.register_pair(pair_config, execution_engine)

# Entry coordination (async)
signals = await orch.check_all_entries(signal_generator)
order_ids = await orch.submit_coordinated_entries(entries_by_pair, max_concurrent=3)

# Price updates (async)
await orch.handle_price_update(product_id, last_price)

# Emergency procedures (async)
await orch.emergency_liquidate_pair(product_id, current_price)
await orch.emergency_liquidate_portfolio(prices_by_product)

# Status
status = orch.get_portfolio_status()
# Returns:
# {
#   'pairs_registered': 4,
#   'metrics': {...},
#   'risk_violations': [...],
#   'rebalance_needed': bool,
#   'rebalance_actions': [...]
# }
```

## Execution Model

### Async Signal Generation

```python
async def generate_signals(product_id: str):
    # Return immediately with signal or no-signal
    return {"should_buy": True, "price": Decimal('50000'), ...}

# Called in parallel for all pairs
signals = await orchestrator.check_all_entries(generate_signals)
# Result: {"BTC-USD": True, "ETH-USD": False, ...}
```

### Coordinated Entry Submission

```python
entries_by_pair = {
    "BTC-USD": {"price": 50000, "qty": 1.0, ...},
    "ETH-USD": {"price": 3000, "qty": 16.66, ...},
}

# Submits up to N concurrent orders (default=3)
order_ids = await orchestrator.submit_coordinated_entries(
    entries_by_pair,
    max_concurrent=3
)
```

### Price-Driven Trailing Stops

```python
# Called on WebSocket price tick
await orchestrator.handle_price_update("BTC-USD", Decimal('51500'))

# Internally:
# 1. highest_price = max(44000, 51500) = 51500
# 2. new_trigger = 51500 * (1 - 0.02) = 50470
# 3. If 50470 > 50000 * 1.01 (min_ratchet):
#      Replace old stop with new stop-limit order
```

## Risk Management

### Position Size Limits

```python
# Per-position maximum
max_position_usd = total_capital * (max_position_size_pct / 100)

# Enforced at order submission
# Rejects entries that would exceed limit
```

### Concentration Limits

```python
# Max exposure in top N correlated positions
# Example: top 3 positions can't exceed 30% of capital

# Enforced per correlation_group
# E.g., "large_cap" group can't exceed 30%
```

### Emergency Liquidation

```python
# Triggered if portfolio falls below
# entry_capital * (1 + emergency_liquidation_loss_pct)
# Default: -10% loss threshold

# Closes all positions immediately at market price
await orchestrator.emergency_liquidate_portfolio(prices)
```

## Monitoring Tools

### Portfolio Dashboard

```bash
# Summary view
python scripts/portfolio_dashboard.py summary

# Capital allocation and position counts
# Total: $100,000 | Deployed: $45,000 | Available: $55,000
# Active Positions: 3 | Closed: 12 | Win Rate: 62%

# Concentration analysis
python scripts/portfolio_dashboard.py concentration

# Ranked positions with cumulative exposure
# BTC-USD: $15,000 (15%)
# ETH-USD: $12,000 (27% cumulative)
# SOL-USD: $8,000 (35% cumulative)

# Per-pair comparison
python scripts/portfolio_dashboard.py pairs

# Status by product_id
# BTC-USD: 1 active, $15k deployed, 2.3% return
# ETH-USD: 1 active, $12k deployed, -1.2% return
```

## Testing

```bash
# Run portfolio tests
pytest tests/test_portfolio_manager.py -v

# Run full suite (103 tests)
pytest tests/ -q
```

## Example: Multi-Pair Trading

See `examples/demo_multi_pair.py` for a complete demonstration including:

1. Portfolio configuration (5-10 pairs)
2. Per-pair setup (different position sizes, trails)
3. Coordinated entry signal generation
4. Concurrent order submission
5. Portfolio status monitoring
6. Risk enforcement

## State Persistence

All portfolio state is persisted to SQLite:

```text
portfolio.db
├── positions (product_id, qty, entry_price, state, ...)
├── orders (product_id, order_id, type, state, ...)
├── history (product_id, action, price, qty, timestamp)
└── (auto-reconciled on restart)
```

## Restart Reconciliation

On restart:

1. Load all positions from database
2. Load all open orders from database
3. Verify orders exist on exchange
4. Cancel orphaned orders
5. Resume trailing stops and entry checks

## Next Steps

- [ ] WebSocket price feeds for real-time trailing stops
- [ ] Correlation matrix for dynamic risk grouping
- [ ] Advanced rebalancing strategies
- [ ] Portfolio backtester with multi-pair stats
- [ ] Performance attribution by pair
- [ ] Slippage and fee modeling
- [ ] Machine learning signal fusion across pairs
