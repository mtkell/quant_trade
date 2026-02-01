# ADR-004: Sync + Async Dual Implementation

**Status**: Accepted | **Date**: 2026-01-31

## Context

A trading system must handle multiple concurrent tasks:

- Placing orders (network I/O)
- Receiving WebSocket updates (network I/O)
- Updating trailing stops (computation)
- Persisting state (disk I/O)

Options for concurrency model:

1. **Synchronous only**: Simple, but blocking I/O halts the entire engine
2. **Asynchronous only**: Efficient, but higher complexity and learning curve
3. **Dual (sync + async)**: Maintain both implementations; use async in production, sync for testing

## Decision

**Implement both synchronous and asynchronous execution paths.**

- **Sync path** (`execution.py`, `coinbase_adapter.py`): Single-threaded, blocking I/O
  - Used in: single-pair demos, unit tests, simple scripts
  - Easier to debug and reason about

- **Async path** (`async_execution.py`, `async_coinbase_adapter.py`): Coroutines with async/await
  - Used in: production, multi-pair portfolio, real-time WebSocket updates
  - Higher performance, handles many pairs efficiently

Both use the same:

- `PositionState` and `OrderStateMachine` logic
- `SQLitePersistence` for state
- Configuration loading and validation

## Consequences

### Positive

- **Testing friendly**: Sync path is easier to test and debug
- **Learning curve**: Can start with sync, graduate to async
- **Flexibility**: Choose sync for simple deployments, async for complex ones
- **No duplication of logic**: Core state machine logic is shared
- **Type safety**: Both implement same abstract adapter interface

### Negative

- **Code duplication**: Exchange adapters must be implemented twice
- **Maintenance burden**: Bug fixes may need to be applied to both
- **Complexity**: Two code paths means more test coverage needed
- **Potential inconsistency**: Sync and async may drift over time

## Implementation Strategy

**Shared Core**:

```python
# These are pure logic, no I/O
position.py          # PositionState, ratchet logic
order_state.py       # OrderStateMachine
```

**Sync Path**:

```python
execution.py          # ExecutionEngine (sync)
coinbase_adapter.py   # CoinbaseAdapter (sync)
```

**Async Path**:

```python
async_execution.py           # AsyncExecutionEngine
async_coinbase_adapter.py    # AsyncCoinbaseAdapter
```

**Shared Interfaces**:

```python
# Both adapters inherit from ExchangeAdapter
class ExchangeAdapter(ABC):
    def place_limit_buy(self, ...) -> str
    def place_stop_limit(self, ...) -> str
    def cancel_order(self, ...) -> bool
    def get_order_status(self, ...) -> Optional[dict]
```

## Testing Strategy

**Unit tests** (no I/O):

- Test `PositionState.ratchet_stop()` logic
- Test `OrderStateMachine` state transitions
- Use mock adapters for both sync/async
- Same test values for both paths

**Integration tests**:

- Sync path: in-memory adapter, fast execution
- Async path: async mock adapter, event loop handling

**Example**:

```python
# Shared logic tested once
def test_ratchet_stop():
    pos = PositionState(...)
    # Same test for both sync and async

# Sync-specific test
def test_sync_adapter_places_order():
    adapter = InMemoryAdapter()
    oid = adapter.place_limit_buy("order_1", ...)
    assert adapter.orders[oid]["state"] == "open"

# Async-specific test
@pytest.mark.asyncio
async def test_async_adapter_places_order():
    adapter = MockAsyncAdapter()
    oid = await adapter.place_limit_buy("order_1", ...)
    assert adapter.orders[oid]["state"] == "open"
```

## Migration Path: Sync → Async

For users starting with sync:

1. **Phase 1**: Single pair, single market (sync demo_trader.py)
2. **Phase 2**: Switch to async_execution.py with one pair
3. **Phase 3**: Add multiple pairs via portfolio_orchestrator
4. **Phase 4**: Enable WebSocket for real-time feeds

Each phase requires minimal code changes; core logic is unchanged.

## Future: Single Async-Only Path

Once async is thoroughly battle-tested in production:

- Consider deprecating sync path
- Leverage async_execution.py + async_coinbase_adapter.py exclusively
- Remove code duplication

Timeline: 12+ months of production async operation.

## See Also

- [ADR-001: Limit Orders Only](./ADR-001-limit-orders-only.md)
- Module: `trading/execution.py` (sync)
- Module: `trading/async_execution.py` (async)
- Tests: `tests/test_execution_engine.py` (sync)
- Tests: `tests/test_async_execution_engine.py` (async)
