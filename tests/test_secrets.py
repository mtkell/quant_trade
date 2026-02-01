import json
import os
from pathlib import Path
import pytest

from trading.secrets import CoinbaseCredentials, load_credentials, save_config


def test_load_credentials_from_env(monkeypatch):
    """Load credentials from environment variables."""
    monkeypatch.setenv("CB_API_KEY", "test_key")
    monkeypatch.setenv("CB_API_SECRET", "dGVzdF9zZWNyZXQ=")  # base64
    
    creds = load_credentials()
    assert creds.api_key == "test_key"
    assert creds.api_secret == "dGVzdF9zZWNyZXQ="


def test_load_credentials_from_config_file(tmp_path, monkeypatch):
    """Load credentials from config file."""
    # Clear environment to ensure file is used
    monkeypatch.delenv("CB_API_KEY", raising=False)
    monkeypatch.delenv("CB_API_SECRET", raising=False)
    monkeypatch.delenv("CB_CONFIG_PATH", raising=False)
    
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "api_key": "file_key",
        "api_secret": "ZmlsZV9zZWNyZXQ=",
    }))
    
    creds = load_credentials(config_path=str(config_file))
    assert creds.api_key == "file_key"
    assert creds.api_secret == "ZmlsZV9zZWNyZXQ="


def test_env_overrides_config_file(tmp_path, monkeypatch):
    """Environment variables take precedence over config file."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "api_key": "file_key",
        "api_secret": "ZmlsZV9zZWNyZXQ=",
    }))
    
    monkeypatch.setenv("CB_API_KEY", "env_key")
    monkeypatch.setenv("CB_API_SECRET", "ZW52X3NlY3JldA==")
    
    creds = load_credentials(config_path=str(config_file))
    assert creds.api_key == "env_key"
    assert creds.api_secret == "ZW52X3NlY3JldA=="


def test_load_credentials_missing_raises(monkeypatch):
    """Raise ValueError if credentials are missing."""
    monkeypatch.delenv("CB_API_KEY", raising=False)
    monkeypatch.delenv("CB_API_SECRET", raising=False)
    monkeypatch.delenv("CB_CONFIG_PATH", raising=False)
    
    with pytest.raises(ValueError, match="Missing Coinbase credentials"):
        load_credentials(config_path="/nonexistent/path.json")


def test_save_and_load_config(tmp_path):
    """Save config and load it back."""
    config_file = tmp_path / "saved.json"
    
    save_config(
        config_path=str(config_file),
        api_key="saved_key",
        api_secret="c2F2ZWRfc2VjcmV0"
    )
    
    assert config_file.exists()
    creds = load_credentials(config_path=str(config_file))
    assert creds.api_key == "saved_key"
    assert creds.api_secret == "c2F2ZWRfc2VjcmV0"


def test_credentials_namedtuple():
    """CoinbaseCredentials is a namedtuple with expected fields."""
    creds = CoinbaseCredentials(
        api_key="k",
        api_secret="s"
    )
    assert creds.api_key == "k"
    assert creds.api_secret == "s"
