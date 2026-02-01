# Operational Tools Documentation

The trading system includes three command-line tools for production monitoring and management of open positions and orders.

## Installation

All tools require the trading database to be initialized with the migration system:

```bash
python scripts/migrate.py --db state.db apply
```

## Tool 1: Position Status CLI

Monitor open positions, view position details, and track price movements.

### Usage

**List all open positions:**
```bash
python scripts/position_status.py --db state.db list
```

Output shows:
- Position ID
- Filled Quantity
- Entry Price
- Highest Price Since Entry (for trailing stop reference)
- Current Stop Trigger Price
- Position Status (OPEN/CLOSED)

**Show detailed position information:**
```bash
python scripts/position_status.py --db state.db show <position_id>
```

Output includes:
- Position status and entry/exit details
- Current trailing stop trigger and limit prices
- Stop order ID (for exchange reference)
- List of related orders (entry, stop, force exits)

### Examples

```bash
# List all positions
python scripts/position_status.py --db state.db list

# View BTC position details
python scripts/position_status.py --db state.db show BTC_001
```

## Tool 2: Order Manager CLI

Manage orders, cancel pending orders, and manually force position exits.

### Usage

**List all orders across positions:**
```bash
python scripts/order_manager.py --db state.db list
```

Output shows orders grouped by position with:
- Order ID
- Order Type (entry, stop, force_sell)
- Current State (pending, filled, cancelled)
- Fill Price and Quantity

**Cancel an order (mark as cancelled in DB):**
```bash
python scripts/order_manager.py --db state.db cancel <order_id>
```

**Note:** This marks the order as cancelled in the local database. You must also cancel the order on the Coinbase exchange using their API.

**Force-exit a position at a specific price:**
```bash
python scripts/order_manager.py --db state.db force-exit <position_id> <exit_price>
```

This action:
1. Records a force_sell order at the specified price
2. Closes the position (sets qty_filled to 0)
3. Reports realized P&L

### Examples

```bash
# List all orders
python scripts/order_manager.py --db state.db list

# Cancel a pending stop order
python scripts/order_manager.py --db state.db cancel stop_order_123

# Manually exit a position at $51,000
python scripts/order_manager.py --db state.db force-exit BTC_001 51000
```

## Tool 3: Trade History Reporter

Analyze fills, calculate P&L, and track trading performance.

### Usage

**View P&L summary across all trades:**
```bash
python scripts/trade_history.py --db state.db summary
```

Output shows:
- Total number of trades
- Total realized and unrealized P&L
- Win rate (% of profitable trades)
- Average return per trade

**List all entry and exit fills:**
```bash
python scripts/trade_history.py --db state.db list
```

Output shows:
- All entry fills (buy orders marked as filled)
- All exit fills (sell/force_sell orders marked as filled)
- Fill price, quantity, and timestamp for each

**View detailed history for a single position:**
```bash
python scripts/trade_history.py --db state.db position <position_id>
```

Output includes:
- Position entry price and quantity
- Highest price since entry
- Current stop trigger
- Realized P&L (if position has exits)
- All orders for the position with states

### Examples

```bash
# View trading summary
python scripts/trade_history.py --db state.db summary

# List all fills
python scripts/trade_history.py --db state.db list

# View detailed history for BTC position
python scripts/trade_history.py --db state.db position BTC_001
```

## Typical Workflows

### Monitor and Adjust a Position

```bash
# 1. List open positions
python scripts/position_status.py --db state.db list

# 2. View details of a position
python scripts/position_status.py --db state.db show BTC_001

# 3. Check orders for the position
python scripts/order_manager.py --db state.db list

# 4. If needed, cancel an order
python scripts/order_manager.py --db state.db cancel order_123

# 5. If needed, manually exit the position
python scripts/order_manager.py --db state.db force-exit BTC_001 51000
```

### Review Trading Performance

```bash
# 1. View summary stats
python scripts/trade_history.py --db state.db summary

# 2. List all fills
python scripts/trade_history.py --db state.db list

# 3. Analyze a specific position
python scripts/trade_history.py --db state.db position BTC_001
```

### Emergency Position Closure

If a position needs to be closed immediately (e.g., due to market conditions):

```bash
# Use current market price to force exit
python scripts/order_manager.py --db state.db force-exit BTC_001 <current_price>

# Verify position is closed
python scripts/position_status.py --db state.db show BTC_001
```

## Database Integration

All tools read directly from the SQLite database:
- **Positions table:** `positions(position_id, value, updated_at)`
- **Orders table:** `orders(order_id, position_id, value, state, created_at, updated_at)`

Changes made by these tools (order cancellation, position closure) are immediately persisted to the database.

## Important Notes

1. **Order Cancellation:** The `cancel` command only updates the database record. You must also cancel the order on the Coinbase exchange using their API to prevent unintended fills.

2. **Force Exit P&L:** The reported P&L for force exits assumes the order fills at the specified price. Actual fills may differ due to market conditions.

3. **Partial Fills:** The tools display quantities as recorded in the database. If an order was partially filled, qty_filled will reflect the total amount filled.

4. **Timestamps:** All timestamps are stored in the database. Some operations (like manual force exits) may have empty timestamps.

## Testing

All operational tools are tested in `tests/test_operational_tools.py`:

```bash
python -m pytest tests/test_operational_tools.py -v
```

This runs 15 tests covering:
- Position listing and detail queries
- Order listing, cancellation, and state updates
- P&L calculation and aggregation
- Full position lifecycle integration
