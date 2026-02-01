# ADR-001: Limit Orders Only

**Status**: Accepted | **Date**: 2026-01-31

## Context

When entering a position, we need to decide between:

1. **Limit orders**: Place at a specific price; may not fill
2. **Market orders**: Immediate execution at market price; unpredictable fill price

In a real-time trading system, particularly for entry, there are tradeoffs:

- **Market orders**: Guaranteed fill but no price control (slippage risk)
- **Limit orders**: Price control but no fill guarantee (may miss opportunity)

## Decision

**Use limit buy orders exclusively for entries.**

Entry logic:

1. Wait for signal confirmation (RSI, MACD, VWAP)
2. Place limit buy at a predetermined price
3. If not filled within `max_entry_wait_candles`, cancel and await next signal
4. For exits, use synthetic market orders via stop-limit (with wider buffer)

## Consequences

### Positive

- **Price control**: Know exact entry price before order fills
- **Predictable slippage**: No market impact surprise
- **Risk management**: Can set position size and stop based on known entry
- **Backtesting friendly**: Deterministic order fills
- **Avoids flash crashes**: Won't buy at panic prices

### Negative

- **Fill uncertainty**: Signal may occur but order not fill before cancel timeout
- **Opportunity cost**: Might miss quick moves if limit price becomes outdated
- **Wider spreads**: May need to place limit slightly better to get filled
- **Complexity**: Must manage timeout logic and retry mechanism

## Alternatives Considered

1. **Market orders for entry**
   - Reason for rejection: No price control; unpredictable slippage in volatile markets

2. **Hybrid approach** (market on high-conviction signals)
   - Reason for rejection: Adds complexity; trading rules should be consistent

3. **Trailing entry orders** (moving limit price upward)
   - Reason for rejection: Over-optimization; limit orders with timeout is sufficient

## Implications for Other Systems

- **Position sizing**: Can be calculated precisely before order fill (using limit price)
- **Stop placement**: Must happen after fill confirmation, not before
- **Backtesting**: All fills use limit price, no market impact estimation needed
- **Live trading**: May miss some quick moves, but reduces risk significantly

## See Also

- [ADR-002: Ratchet-Only Trailing Stops](./ADR-002-ratchet-only-stops.md)
- Config: `max_entry_wait_candles` (default: 10 candles = 50 minutes)
