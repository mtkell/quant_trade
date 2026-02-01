"""
Coinbase Spot Trading Engine.

A production-ready real-time trading system for Coinbase Spot markets featuring:
- 5-minute OHLCV candle analysis with multi-indicator entry confirmation
- Limit buy entries only (no market orders)
- Synthetic dynamic trailing exit via stop-limit cancel/replace (ratchet-only)
- Atomic persistence with SQLite + restart reconciliation
- Rate-limit policy enforcement per endpoint
- Optional encryption at rest via sqlcipher
- Async-capable architecture with WebSocket-ready event loop
- Structured logging via loguru
- Configuration-driven (YAML)

Core Modules:
    position: Position state and trailing ratchet logic
    order_state: Order state machine for entry/exit lifecycle
    execution: Synchronous execution engine with exchange adapter
    async_execution: Asynchronous execution engine
    persistence_sqlite: Atomic persistence and restart reconciliation
    rate_limit_policy: API rate limiting
    coinbase_adapter: Coinbase API integration
    config: Configuration loading and validation
    secrets: Credential management

Example:
    >>> from trading.execution import ExecutionEngine
    >>> from trading.coinbase_adapter import CoinbaseAdapter
    >>> from trading.persistence_sqlite import SQLitePersistence
    >>> from trading.secrets import load_credentials
    >>>
    >>> creds = load_credentials()
    >>> adapter = CoinbaseAdapter.from_credentials(creds)
    >>> persistence = SQLitePersistence("state.db")
    >>> engine = ExecutionEngine(adapter, persistence)
"""

__version__ = "0.1.0"
__all__ = [
    "position",
    "order_state",
    "execution",
    "async_execution",
    "persistence_sqlite",
    "rate_limit_policy",
    "coinbase_adapter",
    "async_coinbase_adapter",
    "config",
    "secrets",
    "portfolio_manager",
    "portfolio_orchestrator",
    "pnl",
]
