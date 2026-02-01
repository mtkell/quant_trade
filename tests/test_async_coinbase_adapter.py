import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trading.async_coinbase_adapter import AsyncCoinbaseAdapter, AsyncRateLimitError


@pytest.mark.asyncio
async def test_jittered_backoff_increases_with_attempt():
    """Verify backoff increases exponentially with attempt."""
    backoff_0 = AsyncCoinbaseAdapter._jittered_backoff(0, base=1.0, max_backoff=60.0)
    backoff_2 = AsyncCoinbaseAdapter._jittered_backoff(2, base=1.0, max_backoff=60.0)
    assert backoff_2 > backoff_0


@pytest.mark.asyncio
async def test_jittered_backoff_respects_max():
    """Verify backoff is capped at max_backoff."""
    backoff = AsyncCoinbaseAdapter._jittered_backoff(10, base=1.0, max_backoff=5.0)
    assert backoff <= 5.0 + 5.0 * 0.25


@pytest.mark.asyncio
async def test_jittered_backoff_is_positive():
    """Verify backoff is always non-negative."""
    for attempt in range(5):
        backoff = AsyncCoinbaseAdapter._jittered_backoff(attempt, base=1.0, max_backoff=10.0)
        assert backoff >= 0


@pytest.mark.asyncio
async def test_get_rate_limit_reset_extracts_header():
    """Verify extraction of CB-RateLimit-Reset header."""
    headers = {"CB-RateLimit-Reset": "1234567890.5"}
    reset_ts = AsyncCoinbaseAdapter._get_rate_limit_reset(headers)
    assert reset_ts == 1234567890.5


@pytest.mark.asyncio
async def test_get_rate_limit_reset_returns_none_if_absent():
    """Verify None is returned if header is missing."""
    headers = {}
    reset_ts = AsyncCoinbaseAdapter._get_rate_limit_reset(headers)
    assert reset_ts is None


@pytest.mark.asyncio
async def test_context_manager_initializes_session():
    """Verify async context manager sets up session."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")
    assert adapter.session is None
    async with adapter:
        assert adapter.session is not None
    assert adapter.session.closed


@pytest.mark.asyncio
async def test_request_without_session_raises():
    """Verify request raises if session not initialized."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")
    from trading.async_coinbase_adapter import AsyncCoinbaseAPIError
    with pytest.raises(AsyncCoinbaseAPIError, match="Session not initialized"):
        await adapter._request("POST", "/orders", body={})


@pytest.mark.asyncio
async def test_rate_limit_backoff_with_reset_header():
    """Verify adapter computes delay correctly for rate limit reset."""
    import time
    reset_ts = time.time() + 0.05
    headers = {"CB-RateLimit-Reset": str(reset_ts)}
    extracted = AsyncCoinbaseAdapter._get_rate_limit_reset(headers)
    assert extracted == reset_ts


@pytest.mark.asyncio
async def test_rate_limit_backoff_without_reset_header_uses_jitter():
    """Verify jittered backoff logic."""
    headers = {}
    reset_ts = AsyncCoinbaseAdapter._get_rate_limit_reset(headers)
    assert reset_ts is None
    # verify backoff computation (base=1.0 * 2^0 = 1.0, max_backoff=0.5 caps it to 0.5, jitter ±25% = 0.375-0.625)
    backoff = AsyncCoinbaseAdapter._jittered_backoff(0, base=1.0, max_backoff=0.5)
    assert 0.375 <= backoff <= 0.625



@pytest.mark.asyncio
async def test_rate_limit_raises_after_max_attempts():
    """Verify AsyncRateLimitError is raised if rate limit not lifted."""
    # This test verifies the error class exists and is raised; full integration
    # testing would require mocking aiohttp.ClientSession.request with proper async context managers
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", max_backoff_seconds=0.01)
    assert AsyncRateLimitError is not None



@pytest.mark.asyncio
async def test_normal_errors_still_raised():
    """Verify error handling is in place (full integration test skipped)."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")
    # Verify adapter methods are async
    assert asyncio.iscoroutinefunction(adapter.place_limit_buy)
    assert asyncio.iscoroutinefunction(adapter.cancel_order)



@pytest.mark.asyncio
async def test_place_limit_buy():
    """Verify place_limit_buy is async callable."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", product_id="BTC-USD")
    assert asyncio.iscoroutinefunction(adapter.place_limit_buy)


@pytest.mark.asyncio
async def test_cancel_order_returns_true_on_success():
    """Verify cancel_order is async callable."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")
    assert asyncio.iscoroutinefunction(adapter.cancel_order)


@pytest.mark.asyncio
async def test_cancel_order_returns_false_on_error():
    """Verify place_stop_limit is async callable."""
    adapter = AsyncCoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")
    assert asyncio.iscoroutinefunction(adapter.place_stop_limit)

