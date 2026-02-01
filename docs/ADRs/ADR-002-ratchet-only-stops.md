# ADR-002: Ratchet-Only Trailing Stops

**Status**: Accepted | **Date**: 2026-01-31

## Context

Once a position is entered, we need an exit mechanism. Options:

1. **Fixed stops**: Stop at a set distance below entry (simple, low management)
2. **Trailing stops**: Move stop upward as price rises (lets winners run, reduces loss)
3. **Bidirectional stops**: Allow stop to move up OR down based on some condition

The key challenge with trailing stops: should they move downward if price drops below the stop level,
or should they only move upward (ratchet)?

## Decision

**Use ratchet-only trailing stops: once placed, stops only move upward, never downward.**

Implementation:

- `highest_price_since_entry` tracks the best price seen
- `current_stop_trigger = highest * (1 - trail_pct)`
- Stop only replaces if `new_trigger > current_trigger + min_ratchet`

## Consequences

### Positive

- **Simple invariant**: "Stops never move down" is easy to reason about and test
- **Risk monotonically decreases**: As price rises, potential loss is reduced
- **Prevents stop whipsaws**: Brief pullback won't lower the stop
- **Deterministic behavior**: No "smart" logic needed for when to lower stops
- **Testable**: Fixed rules make unit tests clear

### Negative

- **May exit too early**: On pullbacks, even if price later recovers
- **Less aggressive**: Could profit from wider trailing ranges
- **Leaves money on table**: Can't adjust stops downward if thesis changes

## Alternatives Considered

1. **Allow stops to move both directions** (e.g., based on volatility)
   - Reason for rejection: Adds complexity and state machine risk; hard to test

2. **Use indicator-driven exits** (e.g., moving average crossover)
   - Reason for rejection: Violates copilot-instructions invariant (trailing stop only)

3. **Dynamic trail_pct based on volatility**
   - Reason for rejection: Can be done via config; simpler to start with fixed trail_pct

## Implementation Details

**The ratchet logic** (in `position.py`):

```python
def ratchet_stop(self, last_trade_price, trail_pct, min_ratchet):
    # Update highest
    self.highest_price_since_entry = max(
        self.highest_price_since_entry,
        last_trade_price
    )

    # Compute new stop based on highest
    new_trigger = self.highest_price_since_entry * (1 - trail_pct)

    # Only replace if improvement exceeds min_ratchet
    if new_trigger > self.current_stop_trigger * (1 + min_ratchet):
        self.current_stop_trigger = new_trigger
        return True  # signal to replace stop order

    return False  # no change needed
```

**Key properties**:

- `new_trigger >= previous_trigger` (ratchet-only)
- Threshold check prevents excessive order replacement
- `min_ratchet` (e.g., 0.1%) avoids micromanagement

## Configuration

From `pyproject.toml`:

```python
trail_pct = 0.02  # 2% trailing distance from highest
stop_limit_buffer_pct = 0.005  # 0.5% buffer between trigger and limit
min_ratchet = 0.001  # 0.1% minimum improvement to ratchet
```

## Testing

Tests in `tests/test_trailing_ratchet.py`:

- Verify stops move upward on price increases
- Verify stops don't move downward on price decreases
- Verify min_ratchet threshold is respected
- Verify buffer between trigger and limit

## See Also

- [ADR-001: Limit Orders Only](./ADR-001-limit-orders-only.md)
- [ADR-005: Decimal Precision](./ADR-005-decimal-precision.md)
- Module: `trading/position.py`
