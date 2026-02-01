# ADR-006: Configuration-Driven Strategy

**Status**: Accepted | **Date**: 2026-01-31

## Context

Trading strategy parameters vary by:

- Market conditions (bull vs bear)
- Risk appetite (conservative vs aggressive)
- Trading style (scalp vs swing)
- Asset pair (BTC vs altcoins)

Hard-coding parameters forces recompilation or fork creation. Externalized configuration allows:

- Live parameter tuning (with caution)
- Per-pair customization
- Strategy backtesting with different configs
- A/B testing of parameters

Options:

1. **Hard-coded defaults**: Fast, but inflexible
2. **Environment variables**: Works, but scales poorly
3. **YAML/TOML config files**: Human-readable, version-controllable
4. **Database configs**: Updatable at runtime, complex queries

## Decision

**Use YAML configuration files as the primary method, with environment variable overrides.**

Config structure:

```yaml
# config.yaml
exchange:
  product_id: BTC-USD
  timeout: 10

strategy:
  trail_pct: 0.02          # 2% trailing stop
  stop_limit_buffer_pct: 0.005
  min_ratchet: 0.001       # 0.1% minimum ratchet

indicators:
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26

portfolio:
  max_positions: 3
  max_position_size_usd: 5000
```

Per-pair overrides supported:

```yaml
pairs:
  - product_id: BTC-USD
    trail_pct: 0.01        # Tighter for BTC
  - product_id: ETH-USD
    trail_pct: 0.03        # Wider for ETH
```

## Consequences

### Positive

- **Non-technical updates**: Business users can adjust parameters
- **Version control**: Config changes tracked in Git
- **Reproducible**: Same config → same behavior
- **Safe defaults**: Example configs provided (conservative, aggressive, paper)
- **Multi-pair flexibility**: Different configs per trading pair
- **Env var override**: Production secrets via environment

### Negative

- **Complexity**: More files to manage
- **Typo risk**: YAML syntax errors will fail at startup
- **Schema validation**: Must catch invalid configs early
- **Hot reload not supported**: Must restart to apply config changes
- **Version mismatch**: Old configs may incompatible with new code

## Configuration Files

**Location**: `config.yaml` in project root or via `CONFIG_PATH` env var

**Precedence**:

1. Command-line arguments (if implemented)
2. Environment variables (e.g., `STRATEGY_TRAIL_PCT=0.01`)
3. YAML file values
4. Hard-coded defaults in code

**Example configs provided**:

- `examples/config.example.yaml` - Baseline template
- `examples/config.conservative.yaml` - Low-risk, long-term holds
- `examples/config.aggressive.yaml` - High-frequency, tight stops
- `examples/config.paper.yaml` - Paper trading / backtesting

## Validation & Defaults

**Validation at load time**:

```python
from trading.config import load_config

config = load_config("config.yaml")
# Raises ConfigError if:
# - File not found
# - Invalid YAML syntax
# - Missing required fields
# - Values out of sensible ranges
```

**Sensibility checks**:

```python
if config.strategy.trail_pct <= 0 or config.strategy.trail_pct > 0.5:
    raise ConfigError("trail_pct must be between 0 and 50%")

if config.strategy.max_entry_wait_candles < 1:
    raise ConfigError("max_entry_wait_candles must be >= 1")

if config.portfolio.max_positions < 1:
    raise ConfigError("max_positions must be >= 1")
```

## Environment Variable Overrides

Useful for deployment and secrets:

```bash
# Override YAML values via environment
export STRATEGY_TRAIL_PCT=0.025
export STRATEGY_STOP_LIMIT_BUFFER_PCT=0.01
export EXCHANGE_TIMEOUT=15

# Or set via .env file (not committed)
# Then: python -m dotenv run examples/demo_trader.py
```

## Multi-Pair Configuration

For portfolio_orchestrator:

```yaml
pairs:
  - product_id: BTC-USD
    entry_amount_usd: 5000
    strategy:
      trail_pct: 0.01
      stop_limit_buffer_pct: 0.005

  - product_id: ETH-USD
    entry_amount_usd: 3000
    strategy:
      trail_pct: 0.02
      stop_limit_buffer_pct: 0.01

  - product_id: SOL-USD
    entry_amount_usd: 2000
    strategy:
      trail_pct: 0.03
      stop_limit_buffer_pct: 0.015
```

Each pair can have independent parameters; orchestrator manages allocation.

## Schema Documentation

Config schema documented in `docs/CONFIG_SCHEMA.md`:

- All fields with types
- Valid ranges
- Default values
- Examples for each field

Generated via:

```bash
python -m trading.config --schema > docs/CONFIG_SCHEMA.md
```

## Runtime Updates (Future)

Currently: config is read once at startup.

Future enhancement: config reload without restart

- Watch for config file changes
- Validate new config
- Apply updates to running orchestrator
- Useful for parameter tuning without restarts

Requires:

- Config change event system
- Atomic param updates during order processing
- Audit log of config changes

## Testing with Different Configs

Unit tests can parametrize over configs:

```python
import pytest

configs = [
    "conservative",   # Wide stops
    "aggressive",     # Tight stops
    "paper"          # Low amounts
]

@pytest.mark.parametrize("config_name", configs)
def test_entry_with_config(config_name):
    config = load_config(f"examples/config.{config_name}.yaml")
    engine = ExecutionEngine(adapter, persistence, config)
    # Test with each config variant
```

## See Also

- Module: `trading/config.py`
- File: `examples/config.example.yaml`
- File: `examples/config.conservative.yaml`
- File: `examples/config.aggressive.yaml`
- File: `examples/config.paper.yaml`
- [ADR-001: Limit Orders Only](./ADR-001-limit-orders-only.md)
