# Coinbase Spot Trading Engine — 5m Limit Entry, Dynamic Trailing Exit

A production-ready real-time trading system for Coinbase Spot markets featuring:

- **5-minute OHLCV candle analysis** with multi-indicator entry confirmation
- **Limit buy entries only** (no market orders)
- **Synthetic dynamic trailing exit** via stop-limit cancel/replace (ratchet-only)
- **Atomic persistence** with SQLite + restart reconciliation
- **Rate-limit policy enforcement** per endpoint
- **Optional encryption at rest** via sqlcipher
- **Async-capable architecture** with WebSocket-ready event loop
- **Structured logging** via loguru
- **Configuration-driven** (YAML)

---

## Quick Start

### 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Credentials

Set environment variables or create `~/.coinbase_config.json`:

```bash
export CB_API_KEY=your_api_key
export CB_API_SECRET=base64_encoded_secret
export CB_API_PASSPHRASE=your_passphrase
```

### 3. Configure Trading

Copy and edit `config.example.yaml`:

```bash
cp examples/config.example.yaml config.yaml
```

### 4. Run Demo

```bash
python examples/demo_trader.py
```

### 5. Run Tests

```bash
pytest -q
```

---

## Architecture

```
Execution Engine (sync/async)
├── OrderStateMachine + PositionState
│   └── Trailing ratchet logic (stops only move up)
├── Exchange Adapter (Coinbase signing + retry/backoff)
│   └── Rate-limit policy enforcement
└── Persistence (SQLite + optional encryption)
    ├── Atomic transactions
    ├── Multi-version migrations (v1: schema, v2: indices)
    └── Restart reconciliation (orphaned order detection)
```

## Core Concepts

**Entry**: Limit buy with multi-indicator confirmation (RSI, MACD, VWAP)

**Trailing Stop**: Ratchet-only logic—stops move upward, never downward

- `highest = max(highest, last_price)`
- `new_trigger = highest * (1 - trail_pct)`
- Replace only if `new_trigger > current * (1 + min_ratchet)`

**Reconciliation**: On startup, detect missing stops and replace with current trailing levels

---

## API

### ExecutionEngine (Sync)

```python
from trading.execution import ExecutionEngine
from trading.coinbase_adapter import CoinbaseAdapter
from trading.persistence_sqlite import SQLitePersistence
from trading.secrets import load_credentials

creds = load_credentials()  # from env or ~/.coinbase_config.json
adapter = CoinbaseAdapter.from_credentials(creds)
persistence = SQLitePersistence("state.db")
engine = ExecutionEngine(adapter, persistence)

# Submit entry
order_id = engine.submit_entry("entry_1", price=Decimal('50000'), qty=Decimal('0.1'))

# Handle fill
engine.handle_fill(order_id, filled_qty=Decimal('0.1'), fill_price=Decimal('50000'))

# Update trailing stop
engine.on_trade(last_trade_price=Decimal('50500'))
```

### AsyncExecutionEngine

Same API, but `async`:

```python
from trading.async_execution import AsyncExecutionEngine

engine = AsyncExecutionEngine(adapter, persistence)
await engine.startup_reconcile()
await engine.submit_entry(...)
await engine.handle_fill(...)
await engine.on_trade(...)
```

### Configuration

```python
from trading.config import TradingConfig

config = TradingConfig.from_yaml("config.yaml")
print(config.strategy.trail_pct)        # 0.02
print(config.exchange.product_id)       # BTC-USD
print(config.persistence.db_path)       # state.db
```

### Logging

```python
from trading.logging_setup import setup_logging, logger

setup_logging(log_file="trading.log", level="INFO")
logger.info("Entry placed", extra={"order_id": "123"})
```

### Rate Limiting

```python
from trading.rate_limit_policy import RateLimitManager

manager = RateLimitManager()
if manager.wait_if_needed("/orders", max_wait=60.0):
    # Make request
    pass
```

### Database Migrations

```bash
python scripts/migrate.py --db state.db list
python scripts/migrate.py --db state.db apply
python scripts/migrate.py --db state.db apply --dry-run
python scripts/migrate.py --db state.db rollback --last
```

---

## File Structure

```
quant_trade/
├── trading/
│   ├── position.py                  # PositionState + ratchet
│   ├── order_state.py               # OrderStateMachine
│   ├── execution.py                 # ExecutionEngine (sync)
│   ├── async_execution.py           # ExecutionEngine (async)
│   ├── coinbase_adapter.py          # Sync Coinbase API
│   ├── async_coinbase_adapter.py    # Async Coinbase API
│   ├── persistence_sqlite.py        # SQLite persistence
│   ├── db_migrations.py             # Schema migrations (v1, v2)
│   ├── rate_limit_policy.py         # Rate-limit enforcement
│   ├── db_encryption.py             # Sqlcipher support
│   ├── secrets.py                   # Credential management
│   ├── config.py                    # YAML configuration
│   ├── logging_setup.py             # Loguru setup
│   └── async_event_loop.py          # Event loop orchestration
├── scripts/
│   └── migrate.py                   # Migration CLI
├── examples/
│   ├── demo_trader.py               # End-to-end demo
│   └── config.example.yaml          # Example config
├── tests/
│   ├── test_*.py                    # 68+ tests
├── config.yaml                      # Your config (copy from example)
└── README.md                        # This file
```

---

## Testing

```bash
pytest -q
```

---

## GUI & Docker Usage

### Run the web GUI (dev)

Start the GUI server (use the project's venv):

```powershell
.venv\Scripts\activate
.venv\Scripts\python.exe web/gui_server.py
```

Open a browser at: [http://127.0.0.1:8080](http://127.0.0.1:8080)

Protected actions (place entry, cancel order, emergency liquidation) are guarded by basic auth if `GUI_USER` and `GUI_PASS` environment variables are set. In the browser UI you'll be prompted for `user:pass` when invoking protected actions.

### Docker

Build and run with Docker:

```bash
docker build -t quant_trade:latest .
docker run --rm -it \
    -v $(pwd)/state:/app/state \
    -e CB_API_KEY -e CB_API_SECRET -e CB_API_PASSPHRASE \
    -e GUI_USER -e GUI_PASS \
    quant_trade:latest
```

Use Podman with `Containerfile` similarly:

```bash
podman build -t quant_trade:latest -f Containerfile .
podman run --rm -it -v $(pwd)/state:/app/state -e CB_API_KEY -e CB_API_SECRET -e CB_API_PASSPHRASE -e GUI_USER -e GUI_PASS quant_trade:latest
```

Or use `docker-compose`:

```bash
docker compose up --build
```

## Testing

```bash
pytest -q
```

---

## Operational Tools

Three command-line tools for production monitoring and management:

### Position Status CLI

View open positions and detailed position information:

```bash
# List all open positions
python scripts/position_status.py --db state.db list

# Show detailed position info
python scripts/position_status.py --db state.db show BTC_001
```

### Order Manager CLI

Manage orders, cancel pending orders, and force-exit positions:

```bash
# List all orders
python scripts/order_manager.py --db state.db list

# Cancel an order (must also cancel on exchange)
python scripts/order_manager.py --db state.db cancel order_123

# Force-exit a position at a specific price
python scripts/order_manager.py --db state.db force-exit BTC_001 51000
```

### Trade History Reporter

Analyze fills and track P&L:
```bash
# View P&L summary
python scripts/trade_history.py --db state.db summary

# List all entry and exit fills
python scripts/trade_history.py --db state.db list

# View position-specific history
python scripts/trade_history.py --db state.db position BTC_001
```

See [OPERATIONAL_TOOLS.md](OPERATIONAL_TOOLS.md) for detailed usage and workflows.

---

## Multi-Pair Portfolio Management

Expand from single-position trading to manage concurrent positions across 5-10+ product pairs:

### Features

- **Multi-pair registration** with per-pair configurations
- **Portfolio-level risk management** (max position size %, concentration limits, emergency liquidation)
- **Coordinated async execution** (parallel signal checking, rate-limited order placement)
- **Automated trailing stop ratcheting** per pair
- **Portfolio metrics** (capital allocation, P&L aggregation, win-rate tracking)
- **Rebalancing detection** with drift-based recommendations

### Quick Start

```bash
# Run multi-pair demonstration
python examples/demo_multi_pair.py

# Monitor portfolio status
python scripts/portfolio_dashboard.py summary
python scripts/portfolio_dashboard.py concentration
python scripts/portfolio_dashboard.py pairs
```

### Configuration

```python
from trading.portfolio_manager import PortfolioConfig, PairConfig

# Portfolio-level constraints
portfolio = PortfolioConfig(
    total_capital=Decimal('100000'),
    max_position_size_pct=Decimal('5'),     # Max 5% per position
    max_positions=10,                        # Up to 10 concurrent
    max_correlated_exposure_pct=Decimal('20'), # Risk grouping
    rebalance_threshold_pct=Decimal('10'),  # Drift tolerance
    emergency_liquidation_loss_pct=Decimal('-10') # Circuit breaker
)

# Per-pair configuration
btc_config = PairConfig(
    product_id="BTC-USD",
    position_size_pct=Decimal('5'),
    trail_pct=Decimal('0.02'),
    correlation_group="large_cap"
)
```

### Multi-Pair Orchestration

```python
from trading.portfolio_orchestrator import MultiPairOrchestrator

# Setup orchestrator
orch = MultiPairOrchestrator(portfolio)
orch.register_pair(btc_config, btc_engine)
orch.register_pair(eth_config, eth_engine)

# Check all entries in parallel
signals = await orch.check_all_entries(signal_generator)

# Submit coordinated orders with rate limiting
order_ids = await orch.submit_coordinated_entries(
    entries_by_pair,
    max_concurrent=3  # Max 3 orders at a time
)

# Get aggregated portfolio status
status = orch.get_portfolio_status()
# Returns: metrics, risk violations, rebalancing needs
```

See [docs/MULTI_PAIR_PORTFOLIO.md](docs/MULTI_PAIR_PORTFOLIO.md) for complete API documentation.

---

## Production Checklist

- [ ] Coinbase API key (read + order permissions only)
- [ ] Test with sandbox API first
- [ ] Configure rate-limit quotas
- [ ] Enable encryption: `persistence.encryption_password` in config
- [ ] Set up database backups
- [ ] Test reconciliation with mock order
- [ ] Monitor logs for orphaned orders
- [ ] Use async event loop for real-time feeds

---

## Troubleshooting

**Missing credentials**: Set `CB_API_KEY`, `CB_API_SECRET`, `CB_API_PASSPHRASE` env vars or create `~/.coinbase_config.json`

**Rate limited**: Adapter retries automatically; check `rate_limit_policy.py` quotas and config

**Orphaned orders**: Reconciliation detects & replaces missing stops; check logs

---

## Support

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for design rules and [examples/demo_trader.py](examples/demo_trader.py) for usage examples.
