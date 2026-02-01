"""Secrets management: load API credentials from environment or config file.

Priority order:
1. Environment variables: CB_API_KEY, CB_API_SECRET
2. Config file: ~/.coinbase_config.json or custom path via ENV CB_CONFIG_PATH
"""
import json
import os
from pathlib import Path
from typing import Optional, NamedTuple


class CoinbaseCredentials(NamedTuple):
    api_key: str
    api_secret: str


def load_credentials(
    config_path: Optional[str] = None,
) -> CoinbaseCredentials:
    """Load Coinbase credentials from env or config file.
    
    Args:
        config_path: Optional override path to config file. If not provided,
                     checks CB_CONFIG_PATH env var, then ~/.coinbase_config.json
    
    Returns:
        CoinbaseCredentials with api_key, api_secret
    
    Raises:
        ValueError: If credentials are not found or incomplete
    """
    # Try environment variables first (highest priority)
    api_key = os.getenv("CB_API_KEY")
    api_secret = os.getenv("CB_API_SECRET")
    
    if api_key and api_secret:
        return CoinbaseCredentials(api_key=api_key, api_secret=api_secret)
    
    # Try config file
    if config_path is None:
        config_path = os.getenv("CB_CONFIG_PATH")
    if config_path is None:
        config_path = str(Path.home() / ".coinbase_config.json")
    
    config_file = Path(config_path)
    if config_file.exists():
        try:
            with config_file.open("r") as f:
                cfg = json.load(f)
            api_key = cfg.get("api_key") or api_key
            api_secret = cfg.get("api_secret") or api_secret
        except Exception as e:
            raise ValueError(f"Failed to load config from {config_path}: {e}")
    
    if not api_key or not api_secret:
        raise ValueError(
            "Missing Coinbase credentials. Provide via:\n"
            "  - Environment: CB_API_KEY, CB_API_SECRET\n"
            f"  - Config file: {config_path}\n"
            "  - CB_CONFIG_PATH env var to override config location"
        )
    
    return CoinbaseCredentials(api_key=api_key, api_secret=api_secret)


def save_config(
    config_path: str,
    api_key: str,
    api_secret: str,
) -> None:
    """Save credentials to a config file for later use.
    
    WARNING: Stores secrets in plaintext. Ensure proper file permissions (600).
    
    Args:
        config_path: Path to save config file
        api_key: Coinbase API key
        api_secret: Base64-encoded API secret
    """
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
    }
    cfg_file = Path(config_path)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    
    with cfg_file.open("w") as f:
        json.dump(config, f, indent=2)
    
    # Restrict permissions to owner only (Unix-like systems)
    try:
        cfg_file.chmod(0o600)
    except Exception:
        pass  # Windows doesn't support chmod; skip silently
