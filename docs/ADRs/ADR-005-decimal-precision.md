# ADR-005: Decimal for Price Precision

**Status**: Accepted | **Date**: 2026-01-31

## Context

Prices and quantities in financial systems must be precise to avoid:

- Rounding errors accumulating over many transactions
- Floating-point representation issues (e.g., 0.1 + 0.2 ≠ 0.3)
- Regulatory/audit discrepancies

Options:

1. **Float**: Fast, built-in, but imprecise for financial math
2. **Decimal**: Exact decimal arithmetic, slower but correct
3. **Integer (cents/satoshis)**: Exact, fast, but requires conversion logic
4. **String**: No calculation, prone to parsing errors

Example problem with float:

```python
# Float arithmetic
price = 0.1 + 0.2  # Result: 0.30000000000000004 ❌
final = price == 0.3  # False ❌

# Decimal arithmetic
from decimal import Decimal
price = Decimal('0.1') + Decimal('0.2')  # Result: 0.3 ✓
final = price == Decimal('0.3')  # True ✓
```

## Decision

**Use Python's `decimal.Decimal` for all prices, quantities, and stop levels.**

All monetary amounts use Decimal:

- Entry price
- Stop trigger and limit
- Order quantity
- Highest price since entry
- P&L calculations

Set precision to 28 decimal places (plenty for Bitcoin satoshi precision):

```python
from decimal import getcontext
getcontext().prec = 28
```

## Consequences

### Positive

- **Exact arithmetic**: No rounding errors or surprises
- **Regulatory compliant**: Matches accounting standards (no float surprises)
- **Debuggable**: Exact values visible in logs
- **Portable**: Same results across Python versions/platforms
- **JSON serializable**: Via `.to_dict()` using `str(decimal_value)`

### Negative

- **Slightly slower**: Decimal operations slower than float (negligible for this use case)
- **Verbose syntax**: `Decimal('50000')` vs `50000`
- **Type annotations**: More explicit type hints required
- **API friction**: Must convert exchange prices (usually floats) to Decimal

## Implementation

**Type hints**:

```python
from decimal import Decimal
from typing import Tuple

def compute_new_stop(
    self,
    trail_pct: Decimal,
    stop_limit_buffer_pct: Decimal
) -> Tuple[Decimal, Decimal]:
    ...
```

**Conversions**:

```python
# From exchange API (JSON): usually strings or floats
exchange_price: float = 50000.00
decimal_price: Decimal = Decimal(str(exchange_price))

# To persistence (JSON): convert back to string
json_value: str = str(decimal_price)
decimal_reconstructed: Decimal = Decimal(json_value)
```

**Arithmetic**:

```python
from decimal import Decimal

price = Decimal('50000')
qty = Decimal('0.1')
trail_pct = Decimal('0.02')  # 2%

# Trigger is 2% below highest
highest = Decimal('51000')
new_trigger = highest * (Decimal(1) - trail_pct)
# Result: Decimal('49980') ✓
```

## Configuration

All config values that represent money are Decimal:

```yaml
strategy:
  trail_pct: 0.02          # Will be converted to Decimal('0.02')
  stop_limit_buffer_pct: 0.005
  min_ratchet: 0.001

entry:
  limit_price: 50000       # Decimal('50000')
  qty: 0.1                 # Decimal('0.1')
```

Config loader must convert:

```python
def load_strategy_config(yaml_dict):
    return StrategyConfig(
        trail_pct=Decimal(str(yaml_dict['trail_pct'])),
        stop_limit_buffer_pct=Decimal(str(yaml_dict['stop_limit_buffer_pct'])),
        min_ratchet=Decimal(str(yaml_dict['min_ratchet']))
    )
```

## Testing

**Test with exact values**:

```python
def test_ratchet_computation():
    pos = PositionState(
        entry_price=Decimal('50000'),
        qty_filled=Decimal('1'),
        highest_price_since_entry=Decimal('51000')
    )

    trigger, limit = pos.compute_new_stop(
        trail_pct=Decimal('0.02'),
        stop_limit_buffer_pct=Decimal('0.005')
    )

    # Exact comparison possible
    assert trigger == Decimal('49980')
    assert limit == Decimal('49745.1')
```

## Exchange Integration

Coinbase API returns prices as strings (JSON):

```json
{
  "price": "50000.00",
  "size": "0.1"
}
```

Conversion in adapter:

```python
def handle_trade(self, trade_data: dict):
    price = Decimal(trade_data['price'])  # String → Decimal
    qty = Decimal(trade_data['size'])     # String → Decimal
    self.engine.on_trade(price, ...)
```

## Performance Notes

- Decimal addition/subtraction: ~1-2 microseconds (vs 0.1 for float)
- For a trading engine processing 10-100 updates/second: negligible
- Total calculation per trade update: <1ms even with 10-20 positions

Example: 100 positions × 1000 price updates/sec = 100ms CPU usage (acceptable)

## Precision Limits

28 decimal places covers:

- USD values to 0.0000000000000000000000000001¢
- BTC/crypto to 28 decimal places (beyond satoshi precision)
- More than sufficient for any trading application

If precision beyond 28 places needed: configure via `getcontext().prec`

## See Also

- [ADR-002: Ratchet-Only Stops](./ADR-002-ratchet-only-stops.md)
- Module: `trading/position.py` (uses Decimal throughout)
- Python docs: [decimal module](https://docs.python.org/3/library/decimal.html)
