import asyncio
import base64
import hashlib
import hmac
import json
import random
import time
from decimal import Decimal
from typing import Optional

import aiohttp

from .execution import ExchangeAdapter


class AsyncCoinbaseAPIError(Exception):
    pass


class AsyncRateLimitError(AsyncCoinbaseAPIError):
    """Raised when rate limit is hit and backoff is exhausted."""
    pass


class AsyncCoinbaseAdapter:
    """Async Coinbase adapter using aiohttp with non-blocking rate-limit backoff.

    Features:
    - Non-blocking async/await using aiohttp.
    - Request signing (CB-ACCESS-* headers) per Coinbase Pro style.
    - Rate-limit-aware backoff: respects `CB-RateLimit-Reset` header.
    - Jittered exponential backoff for 429 (rate-limit) responses.
    - Automatic connection pooling and session reuse.

    Usage:
        async with AsyncCoinbaseAdapter(...) as adapter:
            order_id = await adapter.place_limit_buy(...)
    """

    def __init__(self, api_key: str, secret: str, passphrase: str, *, base_url: str = "https://api.exchange.coinbase.com", product_id: str = "BTC-USD", timeout: int = 10, max_backoff_seconds: float = 60.0):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.base_url = base_url.rstrip("/")
        self.product_id = product_id
        self.timeout = timeout
        self.max_backoff_seconds = max_backoff_seconds
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _sign(self, method: str, request_path: str, body: Optional[str]) -> dict:
        timestamp = str(time.time())
        body = body or ""
        message = timestamp + method.upper() + request_path + body
        try:
            key = base64.b64decode(self.secret)
        except Exception:
            raise AsyncCoinbaseAPIError("Secret must be base64-encoded for signing")
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
        """Compute jittered exponential backoff."""
        delay = base * (2 ** attempt)
        delay = min(delay, max_backoff)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0, delay + jitter)

    @staticmethod
    def _get_rate_limit_reset(headers: dict) -> Optional[float]:
        """Extract CB-RateLimit-Reset header (Unix timestamp)."""
        if "CB-RateLimit-Reset" in headers:
            try:
                return float(headers["CB-RateLimit-Reset"])
            except (ValueError, TypeError):
                return None
        return None

    async def _request(self, method: str, path: str, body: Optional[dict] = None, params: Optional[dict] = None, attempt: int = 0):
        """Execute a request with async rate-limit backoff and retry."""
        if not self.session:
            raise AsyncCoinbaseAPIError("Session not initialized; use 'async with' context manager")

        request_path = path if path.startswith("/") else f"/{path}"
        body_str = json.dumps(body) if body is not None else ""
        headers = self._sign(method, request_path, body_str)
        url = f"{self.base_url}{request_path}"

        try:
            async with self.session.request(method, url, headers=headers, data=body_str if body else None, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                # Handle rate limit (429) with async backoff
                if resp.status == 429:
                    reset_ts = self._get_rate_limit_reset(resp.headers)
                    if reset_ts is not None:
                        # Async sleep until rate limit reset
                        delay = max(0, reset_ts - time.time())
                        if delay > 0:
                            await asyncio.sleep(delay)
                            return await self._request(method, path, body=body, params=params, attempt=attempt + 1)
                    else:
                        # Fallback: jittered exponential backoff
                        if attempt >= 5:
                            raise AsyncRateLimitError("Rate limited and max backoff attempts exceeded")
                        backoff = self._jittered_backoff(attempt, base=1.0, max_backoff=self.max_backoff_seconds)
                        await asyncio.sleep(backoff)
                        return await self._request(method, path, body=body, params=params, attempt=attempt + 1)

                # Handle other errors
                if not (200 <= resp.status < 300):
                    text = await resp.text()
                    raise AsyncCoinbaseAPIError(f"{resp.status}: {text}")

                # Parse response
                text = await resp.text()
                if text:
                    return json.loads(text)
                return None

        except asyncio.TimeoutError as e:
            raise AsyncCoinbaseAPIError(f"Request timeout: {e}")
        except aiohttp.ClientError as e:
            raise AsyncCoinbaseAPIError(f"Request failed: {e}")

    async def place_limit_buy(self, client_id: str, price: Decimal, qty: Decimal, product_id: Optional[str] = None) -> str:
        """Place a limit buy order asynchronously."""
        product = product_id or self.product_id
        body = {
            "type": "limit",
            "side": "buy",
            "product_id": product,
            "price": str(price),
            "size": str(qty),
            "time_in_force": "GTC",
        }
        res = await self._request("POST", "/orders", body=body)
        return res.get("id")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order asynchronously."""
        path = f"/orders/{order_id}"
        try:
            await self._request("DELETE", path)
            return True
        except AsyncCoinbaseAPIError:
            return False

    async def place_stop_limit(self, client_id: str, trigger: Decimal, limit: Decimal, qty: Decimal, product_id: Optional[str] = None) -> str:
        """Place a stop-limit sell order asynchronously."""
        product = product_id or self.product_id
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
        res = await self._request("POST", "/orders", body=body)
        return res.get("id")
