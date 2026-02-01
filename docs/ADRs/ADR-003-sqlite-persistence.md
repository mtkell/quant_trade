# ADR-003: SQLite for Persistence

**Status**: Accepted | **Date**: 2026-01-31

## Context

The system must persist state across restarts:

- Open positions (entry price, qty, highest price, current stop)
- Open orders (entry order, stop order)
- Trade history (fills, P&L)

Requirements:

- **Atomic transactions**: Multi-row updates must be all-or-nothing
- **Crash recovery**: No data corruption if process dies mid-write
- **Query flexibility**: Support different queries for reconciliation
- **Lightweight**: Run locally without external service

Options:

1. **SQLite**: File-based, ACID, no external dependency
2. **PostgreSQL**: Robust, scalable, requires external server
3. **Redis**: Fast, in-memory, not suitable for crash recovery
4. **JSON files**: Simple but no atomicity guarantees

## Decision

**Use SQLite with optional encryption (sqlcipher).**

Key features:

- **Atomic transactions**: `BEGIN IMMEDIATE` for write consistency
- **Schema migrations**: v1 (schema), v2 (indices)
- **Restart reconciliation**: Load positions + orders, check exchange status
- **Encryption at rest**: Optional sqlcipher for sensitive environments
- **Backwards compatibility**: Legacy `kv` table alongside new `positions` table

## Consequences

### Positive

- **No external dependencies**: Runs anywhere Python runs
- **ACID guarantees**: Transactions ensure atomicity
- **Simple backups**: Single `.db` file to copy
- **Query tools**: Standard sqlite3 CLI for debugging
- **Optional encryption**: sqlcipher3 for encrypted deployments
- **Schema migrations**: Version control for DB changes

### Negative

- **Single-process write**: Not suitable for multi-process workers (but okay for us)
- **No distributed consensus**: Can't run across multiple servers
- **Limited scalability**: File size limits (but not relevant for position tracking)
- **Requires schema management**: Migrations must be version-controlled

## Alternatives Considered

1. **PostgreSQL**
   - Reason for rejection: Adds operational complexity; overkill for position tracking

2. **Redis**
   - Reason for rejection: In-memory; not crash-safe without persistence layer

3. **DynamoDB / Firebase**
   - Reason for rejection: Cloud-dependent; limits offline operation

4. **JSON files with fsync**
   - Reason for rejection: Manual transaction logic; error-prone

## Schema Design

**Core tables**:

```sql
-- Positions
CREATE TABLE positions (
    position_id TEXT PRIMARY KEY,
    value TEXT NOT NULL,  -- JSON-serialized PositionState
    updated_at INTEGER
);

-- Orders
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    position_id TEXT,
    value TEXT NOT NULL,  -- JSON-serialized order dict
    state TEXT,
    created_at INTEGER,
    updated_at INTEGER
);

-- Legacy key-value for backwards compatibility
CREATE TABLE kv (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at INTEGER
);

-- Indices for efficient queries
CREATE INDEX idx_orders_position ON orders(position_id);
CREATE INDEX idx_positions_updated ON positions(updated_at);
```

## Restart Reconciliation

On startup:

```python
1. Load all positions from DB
2. For each position:
   a. Get stop_order_id from DB
   b. Query exchange: is order still open?
   c. If not found or filled → clear stop_order_id and recompute trailing stop
   d. Place new stop if missing
3. Resume normal operation
```

This ensures:

- No orphaned orders left on exchange
- Positions stay in sync with latest market prices
- System is safe to restart at any time

## Encryption

When using **sqlcipher3**:

```python
from trading.db_encryption import init_encrypted_db

# Encrypt database with password-derived key
db = init_encrypted_db("state.db", password=os.environ["DB_PASSWORD"])
```

Encrypted at rest; decrypted only in memory. Password should be:

- Strong (20+ chars)
- Stored in environment, not code
- Rotated periodically

## Backup Strategy

**Production backup** (recommended):

```bash
# Stop trading engine
kill $PID

# Copy database
cp state.db backups/state.db.$(date +%Y%m%d_%H%M%S)

# Verify integrity
sqlite3 backups/state.db.latest ".schema"

# Restart engine
python examples/demo_multi_pair.py &
```

For critical deployments: replicate to secondary storage or cloud backup.

## Performance Notes

**Typical operations** (state.db with 10-20 positions):

- `save_position()`: <5ms
- `load_position()`: <1ms
- `list_orders()`: <2ms per position

For larger datasets (1000+ positions), consider:

- Partitioning by date
- Archive old trades to separate DB
- Rebuild indices periodically

## Monitoring

```bash
# Check DB size
ls -lh state.db

# Vacuum to reclaim space
sqlite3 state.db "VACUUM;"

# Check for corruption
sqlite3 state.db "PRAGMA integrity_check;"
```

## See Also

- [ADR-004: Sync + Async Dual](./ADR-004-sync-async-dual.md)
- Module: `trading/persistence_sqlite.py`
- Module: `trading/db_migrations.py`
