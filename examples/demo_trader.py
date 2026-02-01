"""End-to-end demo of the trading system.

Shows:
1. Loading credentials from environment
2. Creating adapters and persistence
3. Submitting entry orders
4. Handling fills
5. Tracking trailing stops
6. Structured logging
"""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path so we can import trading module
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.async_execution import AsyncExecutionEngine
from trading.async_coinbase_adapter import AsyncCoinbaseAdapter
from trading.persistence_sqlite import SQLitePersistence
from trading.secrets import load_credentials
from trading.config import TradingConfig
from trading.logging_setup import setup_logging, logger


async def main():
    """Run the demo trading system."""
    # Step 1: Setup logging
    setup_logging(log_file="trading.log", level="INFO", enable_console=True)
    logger.info("=== Trading System Demo ===")
    
    # Step 2: Load configuration
    config_file = Path(__file__).parent.parent / "config.yaml"
    if config_file.exists():
        config = TradingConfig.from_yaml(str(config_file))
        logger.info(f"Loaded config from {config_file}")
    else:
        from trading.config import ExchangeConfig, StrategyConfig, RateLimitConfig, PersistenceConfig
        config = TradingConfig(
            exchange=ExchangeConfig(),
            strategy=StrategyConfig(),
            rate_limit=RateLimitConfig(),
            persistence=PersistenceConfig(),
        )
        logger.info("Using default configuration")
    
    # Step 3: Load credentials
    try:
        creds = load_credentials()
        logger.info("Credentials loaded successfully")
    except ValueError as e:
        logger.error(f"Failed to load credentials: {e}")
        logger.info("Set environment variables: CB_API_KEY, CB_API_SECRET, CB_API_PASSPHRASE")
        return
    
    # Step 4: Create async adapter with credentials
    adapter = AsyncCoinbaseAdapter(
        api_key=creds.api_key,
        secret=creds.api_secret,
        passphrase=creds.passphrase,
        product_id=config.exchange.product_id,
        timeout=config.exchange.timeout,
    )
    logger.info(f"Adapter created for {config.exchange.product_id}")
    
    # Step 5: Create persistence layer
    db_path = Path(config.persistence.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    persistence = SQLitePersistence(str(db_path))
    logger.info(f"Database: {db_path}")
    
    # Step 6: Create async execution engine
    engine = AsyncExecutionEngine(
        adapter=adapter,
        persistence=persistence,
        trail_pct=config.strategy.trail_pct,
        stop_limit_buffer_pct=config.strategy.stop_limit_buffer_pct,
        min_ratchet=config.strategy.min_ratchet,
    )
    logger.info("Execution engine initialized")
    
    # Step 7: Startup reconciliation
    await engine.startup_reconcile()
    logger.info("Reconciliation complete")
    
    # Step 8: Demo entry order (using a mock scenario)
    # In production, entry signal would come from strategy logic
    demo_price = Decimal('50000')
    demo_qty = Decimal('0.001')
    
    logger.info(f"Submitting entry order: price={demo_price} qty={demo_qty}")
    try:
        # Note: This will fail without valid Coinbase credentials
        # In production, this would be called by the strategy when signal fires
        # order_id = await engine.submit_entry(
        #     client_id="demo_entry",
        #     price=demo_price,
        #     qty=demo_qty,
        # )
        # logger.info(f"Entry order submitted: {order_id}")
        
        # Simulate a fill
        # await engine.handle_fill(
        #     order_id=order_id,
        #     filled_qty=demo_qty,
        #     fill_price=demo_price,
        # )
        # logger.info(f"Order filled at {demo_price}")
        
        logger.info("(Skipped live order submission - use real credentials to trade)")
        
        # Step 9: Simulate price updates and trailing stop ratchets
        logger.info("Simulating price updates...")
        prices = [demo_price + Decimal('100') * i for i in range(1, 4)]
        for price in prices:
            logger.info(f"Price update: {price}")
            # await engine.on_trade(last_trade_price=price)
            # In demo, just log
        
        logger.info("=== Demo Complete ===")
        logger.info("Configuration summary:")
        logger.info(f"  Product: {config.exchange.product_id}")
        logger.info(f"  Trail %: {config.strategy.trail_pct}")
        logger.info(f"  Stop Buffer %: {config.strategy.stop_limit_buffer_pct}")
        logger.info(f"  Database: {config.persistence.db_path}")
        logger.info(f"  Log Level: {config.persistence.log_level}")
        
    except Exception as e:
        logger.error(f"Demo error: {e}", exc_info=True)
        raise
    finally:
        persistence.close()


if __name__ == "__main__":
    asyncio.run(main())
