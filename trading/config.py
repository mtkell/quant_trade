"""Configuration loader for trading system.

Supports YAML format with environment variable interpolation.
"""
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ExchangeConfig:
    """Coinbase exchange settings."""
    base_url: str = "https://api.exchange.coinbase.com"
    product_id: str = "BTC-USD"
    timeout: int = 10
    max_retries: int = 5
    max_backoff_seconds: float = 60.0


@dataclass
class StrategyConfig:
    """Trading strategy parameters."""
    trail_pct: Decimal = Decimal('0.02')  # 2% trailing stop
    stop_limit_buffer_pct: Decimal = Decimal('0.005')  # 0.5% below trigger
    min_ratchet: Decimal = Decimal('0.001')  # 0.1% minimum ratchet


@dataclass
class RateLimitConfig:
    """Rate-limit policy settings."""
    orders_per_second: int = 15
    default_per_second: int = 10


@dataclass
class PersistenceConfig:
    """Database and persistence settings."""
    db_path: str = "state.db"
    encryption_password: Optional[str] = None
    log_file: str = "trading.log"
    log_level: str = "INFO"


@dataclass
class TradingConfig:
    """Complete trading system configuration."""
    exchange: ExchangeConfig
    strategy: StrategyConfig
    rate_limit: RateLimitConfig
    persistence: PersistenceConfig

    @classmethod
    def from_yaml(cls, config_path: str) -> "TradingConfig":
        """Load configuration from YAML file with env var interpolation.
        
        Args:
            config_path: Path to YAML config file
        
        Returns:
            TradingConfig instance
        
        Example YAML:
            exchange:
              product_id: BTC-USD
              timeout: 10
            strategy:
              trail_pct: 0.02
              stop_limit_buffer_pct: 0.005
            persistence:
              db_path: "${STATE_DIR}/state.db"
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with config_file.open("r") as f:
            raw = f.read()
        
        # Interpolate environment variables: ${VAR_NAME}
        for key, value in os.environ.items():
            raw = raw.replace(f"${{{key}}}", value)
        
        data = yaml.safe_load(raw)
        
        # Build nested dataclass instances
        exchange = ExchangeConfig(**data.get("exchange", {}))
        strategy = StrategyConfig(**{
            k: Decimal(str(v)) if k.endswith("_pct") else v
            for k, v in data.get("strategy", {}).items()
        })
        rate_limit = RateLimitConfig(**data.get("rate_limit", {}))
        persistence = PersistenceConfig(**data.get("persistence", {}))
        
        return cls(
            exchange=exchange,
            strategy=strategy,
            rate_limit=rate_limit,
            persistence=persistence,
        )
    
    def to_yaml(self, output_path: str) -> None:
        """Save configuration to YAML file."""
        data = {
            "exchange": {
                "base_url": self.exchange.base_url,
                "product_id": self.exchange.product_id,
                "timeout": self.exchange.timeout,
                "max_retries": self.exchange.max_retries,
                "max_backoff_seconds": self.exchange.max_backoff_seconds,
            },
            "strategy": {
                "trail_pct": str(self.strategy.trail_pct),
                "stop_limit_buffer_pct": str(self.strategy.stop_limit_buffer_pct),
                "min_ratchet": str(self.strategy.min_ratchet),
            },
            "rate_limit": {
                "orders_per_second": self.rate_limit.orders_per_second,
                "default_per_second": self.rate_limit.default_per_second,
            },
            "persistence": {
                "db_path": self.persistence.db_path,
                "encryption_password": self.persistence.encryption_password,
                "log_file": self.persistence.log_file,
                "log_level": self.persistence.log_level,
            },
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
