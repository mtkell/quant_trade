import base64
import hashlib
import hmac
import json
import random
import time
from decimal import Decimal
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .execution import ExchangeAdapter
from .secrets import CoinbaseCredentials


class CoinbaseAPIError(Exception):
    pass


class RateLimitError(CoinbaseAPIError):
    """Raised when rate limit is hit and backoff is exhausted."""
    pass


class CoinbaseAdapter(ExchangeAdapter):
    """Minimal Coinbase Pro / Exchange adapter with request signing, retries, and rate-limit backoff.

    Features:
    - Request signing (CB-ACCESS-* headers) per Coinbase Pro style.
    - Automatic retry with urllib3.Retry for 5xx errors.
    - Rate-limit-aware backoff: respects `CB-RateLimit-Reset` header and uses jittered exponential backoff.
    - Jittered exponential backoff for 429 (rate-limit) responses to avoid thundering herd.

    Notes:
    - `secret` should be the base64-encoded API secret provided by Coinbase.
    - This implementation targets the Coinbase Exchange REST API (Coinbase Pro style signing).
    - Caller must set `product_id` or pass it to methods; default is `BTC-USD`.
    """

    def __init__(self, api_key: str, secret: str, passphrase: str, *, base_url: str = "https://api.exchange.coinbase.com", product_id: str = "BTC-USD", timeout: int = 10, max_retries: int = 5, max_backoff_seconds: float = 60.0):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self.product_id = product_id
        self.timeout = timeout
        self.max_backoff_seconds = max_backoff_seconds

        self.session = requests.Session()
        retries = Retry(total=max_retries, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(["GET", "POST", "DELETE", "PUT"]))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

    @classmethod
    def from_credentials(cls, credentials: CoinbaseCredentials, **kwargs) -> "CoinbaseAdapter":
        """Create CoinbaseAdapter from CoinbaseCredentials (loaded via secrets module)."""
        return cls(
            api_key=credentials.api_key,
            secret=credentials.api_secret,
            passphrase=credentials.passphrase,
            **kwargs
        )

    def _sign(self, method: str, request_path: str, body: Optional[str]) -> dict:
        timestamp = str(time.time())
        body = body or ""
        message = timestamp + method.upper() + request_path + body
        try:
            key = base64.b64decode(self.secret)
        except Exception:
            raise CoinbaseAPIError("Secret must be base64-encoded for signing")
        signature = hmac.new(key, message.encode("utf-8"), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()
        headers = {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature_b64,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        return headers

    @staticmethod
    def _jittered_backoff(attempt: int, base: float = 1.0, max_backoff: float = 60.0) -> float:
        """Compute jittered exponential backoff.
        
        Returns delay in seconds.
        """
        # exponential: base * 2^attempt
        delay = base * (2 ** attempt)
        # cap at max_backoff
        delay = min(delay, max_backoff)
        # add jitter: ±25% to avoid thundering herd
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0, delay + jitter)

    @staticmethod
    def _get_rate_limit_reset(resp: requests.Response) -> Optional[float]:
        """Extract CB-RateLimit-Reset header (Unix timestamp when rate limit resets)."""
        if "CB-RateLimit-Reset" in resp.headers:
            try:
                return float(resp.headers["CB-RateLimit-Reset"])
            except (ValueError, TypeError):
                return None
        return None

    def _request(self, method: str, path: str, body: Optional[dict] = None, params: Optional[dict] = None, attempt: int = 0):
        request_path = path if path.startswith("/") else f"/{path}"
        body_str = json.dumps(body) if body is not None else ""
        headers = self._sign(method, request_path, body_str)
        url = f"{self.base_url}{request_path}"
        
        try:
            resp = self.session.request(method, url, headers=headers, data=body_str if body else None, params=params, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise CoinbaseAPIError(f"Request failed: {e}")

        # Handle rate limit (429) with jittered backoff
        if resp.status_code == 429:
            reset_ts = self._get_rate_limit_reset(resp)
            if reset_ts is not None:
                # Sleep until rate limit reset. Add a small epsilon to ensure we
                # don't wake slightly before the reset timestamp due to timing
                # precision differences on test hosts.
                epsilon = 0.01
                delay = reset_ts - time.time()
                if delay > 0:
                    time.sleep(delay + epsilon)
                    return self._request(method, path, body=body, params=params, attempt=attempt + 1)
            else:
                # Fallback: jittered exponential backoff
                if attempt >= 5:
                    raise RateLimitError("Rate limited and max backoff attempts exceeded")
                backoff = self._jittered_backoff(attempt, base=1.0, max_backoff=self.max_backoff_seconds)
                time.sleep(backoff)
                return self._request(method, path, body=body, params=params, attempt=attempt + 1)

        # Handle other errors
        if not resp.ok:
            raise CoinbaseAPIError(f"{resp.status_code}: {resp.text}")
        
        if resp.text:
            return resp.json()
        return None

    def place_limit_buy(self, client_id: str, price: Decimal, qty: Decimal, product_id: Optional[str] = None) -> str:
        product = product_id or self.product_id
        body = {
            "type": "limit",
            "side": "buy",
            "product_id": product,
            "price": str(price),
            "size": str(qty),
            "time_in_force": "GTC",
        }
        res = self._request("POST", "/orders", body=body)
        return res.get("id")

    def cancel_order(self, order_id: str) -> bool:
        # DELETE /orders/{id}
        path = f"/orders/{order_id}"
        try:
            self._request("DELETE", path)
            return True
        except CoinbaseAPIError:
            return False

    def place_stop_limit(self, client_id: str, trigger: Decimal, limit: Decimal, qty: Decimal, product_id: Optional[str] = None) -> str:
        product = product_id or self.product_id
        # Place a stop-limit SELL (exit). "stop": "loss" sets stop-trigger behavior.
        body = {
            "type": "limit",
            "side": "sell",
            "product_id": product,
            "price": str(limit),
            "size": str(qty),
            "stop": "loss",
            "stop_price": str(trigger),
            "time_in_force": "GTC",
        }
        res = self._request("POST", "/orders", body=body)
        return res.get("id")

    def get_order_status(self, order_id: str) -> Optional[dict]:
        try:
            res = self._request("GET", f"/orders/{order_id}")
            return res
        except CoinbaseAPIError:
            return None
