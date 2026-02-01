import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from trading.coinbase_adapter import CoinbaseAdapter, RateLimitError


def test_jittered_backoff_increases_with_attempt():
    """Verify backoff increases exponentially with attempt."""
    backoff_0 = CoinbaseAdapter._jittered_backoff(0, base=1.0, max_backoff=60.0)
    backoff_2 = CoinbaseAdapter._jittered_backoff(2, base=1.0, max_backoff=60.0)
    assert backoff_2 > backoff_0


def test_jittered_backoff_respects_max():
    """Verify backoff is capped at max_backoff."""
    backoff = CoinbaseAdapter._jittered_backoff(10, base=1.0, max_backoff=5.0)
    assert backoff <= 5.0 + 5.0 * 0.25  # max + max jitter


def test_jittered_backoff_is_positive():
    """Verify backoff is always non-negative."""
    for attempt in range(5):
        backoff = CoinbaseAdapter._jittered_backoff(attempt, base=1.0, max_backoff=10.0)
        assert backoff >= 0


def test_get_rate_limit_reset_extracts_header():
    """Verify extraction of CB-RateLimit-Reset header."""
    resp = MagicMock()
    resp.headers = {"CB-RateLimit-Reset": "1234567890.5"}
    reset_ts = CoinbaseAdapter._get_rate_limit_reset(resp)
    assert reset_ts == 1234567890.5


def test_get_rate_limit_reset_returns_none_if_absent():
    """Verify None is returned if header is missing."""
    resp = MagicMock()
    resp.headers = {}
    reset_ts = CoinbaseAdapter._get_rate_limit_reset(resp)
    assert reset_ts is None


@patch("trading.coinbase_adapter.requests.Session.request")
def test_rate_limit_backoff_with_reset_header(mock_request):
    """Verify adapter sleeps until reset time when rate limited."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", max_backoff_seconds=60.0)

    now = time.time()
    reset_ts = now + 0.1  # reset in 100ms

    # Mock: first call returns 429 with reset header, second call succeeds
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429
    rate_limit_resp.ok = False
    rate_limit_resp.headers = {"CB-RateLimit-Reset": str(reset_ts)}
    rate_limit_resp.text = "Rate limited"

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.ok = True
    success_resp.text = '{"id": "order1"}'
    success_resp.json.return_value = {"id": "order1"}

    mock_request.side_effect = [rate_limit_resp, success_resp]

    start = time.time()
    result = adapter._request("POST", "/orders", body={"test": "body"})
    elapsed = time.time() - start

    assert result == {"id": "order1"}
    assert elapsed >= 0.1  # should have slept at least 100ms


@patch("trading.coinbase_adapter.requests.Session.request")
def test_rate_limit_backoff_without_reset_header_uses_jitter(mock_request):
    """Verify adapter uses jittered backoff if reset header is absent."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", max_backoff_seconds=1.0)

    # Mock: first call returns 429 without reset header, second call succeeds
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429
    rate_limit_resp.ok = False
    rate_limit_resp.headers = {}
    rate_limit_resp.text = "Rate limited"

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.ok = True
    success_resp.text = '{"id": "order2"}'
    success_resp.json.return_value = {"id": "order2"}

    mock_request.side_effect = [rate_limit_resp, success_resp]

    start = time.time()
    result = adapter._request("POST", "/orders", body={"test": "body"})
    elapsed = time.time() - start

    assert result == {"id": "order2"}
    # should have slept for jittered backoff (attempt=0 -> base 2^0 = 1.0, but capped at max_backoff)
    # with jitter, could be anywhere from 0.75 to 1.25 seconds; we'll just verify it's nonzero and reasonable
    assert elapsed > 0.1  # at least some backoff


@patch("trading.coinbase_adapter.requests.Session.request")
def test_rate_limit_raises_after_max_attempts(mock_request):
    """Verify RateLimitError is raised if rate limit is not lifted after max backoff attempts."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", max_backoff_seconds=0.01)

    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429
    rate_limit_resp.ok = False
    rate_limit_resp.headers = {}
    rate_limit_resp.text = "Rate limited"

    mock_request.return_value = rate_limit_resp

    with pytest.raises(RateLimitError):
        adapter._request("POST", "/orders", body={"test": "body"})


@patch("trading.coinbase_adapter.requests.Session.request")
def test_normal_errors_still_raised(mock_request):
    """Verify non-429 errors are raised immediately."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")

    error_resp = MagicMock()
    error_resp.status_code = 400
    error_resp.ok = False
    error_resp.text = "Bad request"

    mock_request.return_value = error_resp

    from trading.coinbase_adapter import CoinbaseAPIError
    with pytest.raises(CoinbaseAPIError, match="400"):
        adapter._request("POST", "/orders", body={"test": "body"})


@patch("trading.coinbase_adapter.requests.Session.request")
def test_place_limit_buy_calls_request(mock_request):
    """Verify place_limit_buy constructs correct request and calls _request."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test", product_id="BTC-USD")

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.ok = True
    success_resp.text = '{"id": "o123"}'
    success_resp.json.return_value = {"id": "o123"}

    mock_request.return_value = success_resp

    order_id = adapter.place_limit_buy(client_id="c1", price=Decimal("50000"), qty=Decimal("0.1"))
    assert order_id == "o123"


@patch("trading.coinbase_adapter.requests.Session.request")
def test_cancel_order_returns_true_on_success(mock_request):
    """Verify cancel_order returns True on successful cancellation."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.ok = True
    success_resp.text = ""

    mock_request.return_value = success_resp

    result = adapter.cancel_order("o123")
    assert result is True


@patch("trading.coinbase_adapter.requests.Session.request")
def test_cancel_order_returns_false_on_error(mock_request):
    """Verify cancel_order returns False on error."""
    adapter = CoinbaseAdapter(api_key="test", secret="dGVzdA==", passphrase="test")

    error_resp = MagicMock()
    error_resp.status_code = 404
    error_resp.ok = False
    error_resp.text = "Not found"

    mock_request.return_value = error_resp

    result = adapter.cancel_order("invalid_id")
    assert result is False
