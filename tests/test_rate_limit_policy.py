import pytest
import time

from trading.rate_limit_policy import RateLimitQuota, RateLimitState, RateLimitManager


def test_rate_limit_quota_allow_within_limit():
    quota = RateLimitQuota(requests_per_window=3, window_seconds=1)
    state = RateLimitState(quota=quota)
    
    assert state.is_allowed()
    state.record_request()
    assert state.is_allowed()
    state.record_request()
    assert state.is_allowed()
    state.record_request()
    assert not state.is_allowed()


def test_rate_limit_quota_window_reset():
    quota = RateLimitQuota(requests_per_window=2, window_seconds=0.1)
    state = RateLimitState(quota=quota)
    
    state.record_request()
    state.record_request()
    assert not state.is_allowed()
    
    # Wait for window to reset
    time.sleep(0.15)
    assert state.is_allowed()


def test_rate_limit_manager_per_endpoint():
    manager = RateLimitManager()
    
    # /orders has 15 req/sec
    for _ in range(15):
        assert manager.is_allowed("/orders")
        manager.record_request("/orders")
    
    assert not manager.is_allowed("/orders")
    
    # Other endpoints use default (10 req/sec)
    for _ in range(10):
        assert manager.is_allowed("/unknown")
        manager.record_request("/unknown")
    
    assert not manager.is_allowed("/unknown")


def test_rate_limit_manager_custom_quotas():
    quotas = {
        "/custom": RateLimitQuota(requests_per_window=2, window_seconds=1),
    }
    manager = RateLimitManager(quotas=quotas)
    
    assert manager.is_allowed("/custom")
    manager.record_request("/custom")
    assert manager.is_allowed("/custom")
    manager.record_request("/custom")
    assert not manager.is_allowed("/custom")


def test_time_until_allowed():
    quota = RateLimitQuota(requests_per_window=1, window_seconds=0.2)
    state = RateLimitState(quota=quota)
    
    state.record_request()
    assert not state.is_allowed()
    
    wait_time = state.time_until_allowed()
    assert 0 < wait_time <= 0.2


def test_wait_if_needed_allows_immediately():
    manager = RateLimitManager(
        quotas={"/test": RateLimitQuota(requests_per_window=5, window_seconds=1)}
    )
    
    # Should not wait if capacity available
    start = time.time()
    allowed = manager.wait_if_needed("/test")
    elapsed = time.time() - start
    
    assert allowed
    assert elapsed < 0.05  # should be instant


def test_wait_if_needed_waits_and_allows():
    manager = RateLimitManager(
        quotas={"/test": RateLimitQuota(requests_per_window=1, window_seconds=0.1)}
    )
    
    manager.record_request("/test")
    assert not manager.is_allowed("/test")
    
    # wait_if_needed should wait and then allow
    start = time.time()
    allowed = manager.wait_if_needed("/test", max_wait=0.2)
    elapsed = time.time() - start
    
    assert allowed
    assert elapsed >= 0.1  # waited for window to reset


def test_wait_if_needed_timeout():
    manager = RateLimitManager(
        quotas={"/test": RateLimitQuota(requests_per_window=1, window_seconds=1.0)}
    )
    
    manager.record_request("/test")
    
    # Should timeout if max_wait is too short
    start = time.time()
    allowed = manager.wait_if_needed("/test", max_wait=0.05)
    elapsed = time.time() - start
    
    assert not allowed
    assert elapsed < 0.2  # didn't wait the full second
