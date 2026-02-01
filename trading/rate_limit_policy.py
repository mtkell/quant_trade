"""Rate-limit policy: enforce request quotas per endpoint with sliding window."""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RateLimitQuota:
    """Per-endpoint rate-limit quota."""
    requests_per_window: int  # max requests allowed in the window
    window_seconds: int       # time window in seconds


@dataclass
class RateLimitState:
    """Track request history for a single endpoint."""
    quota: RateLimitQuota
    request_times: list = field(default_factory=list)  # list of timestamps
    
    def is_allowed(self) -> bool:
        """Check if a new request is allowed under the quota."""
        now = time.time()
        # Remove requests outside the current window
        cutoff = now - self.quota.window_seconds
        self.request_times = [t for t in self.request_times if t > cutoff]
        
        # Check if we have capacity
        return len(self.request_times) < self.quota.requests_per_window
    
    def record_request(self) -> None:
        """Record a successful request."""
        self.request_times.append(time.time())
    
    def time_until_allowed(self) -> float:
        """Return seconds until next request is allowed. 0 if allowed now."""
        if self.is_allowed():
            return 0.0
        
        # Find oldest request in the window and return time until it expires
        now = time.time()
        cutoff = now - self.quota.window_seconds
        old_requests = [t for t in self.request_times if t <= cutoff]
        
        if not old_requests:
            # All requests in window; next allowed at oldest request + window
            oldest = min(self.request_times)
            return max(0, oldest + self.quota.window_seconds - now)
        
        return 0.0


class RateLimitManager:
    """Enforce rate-limit quotas per endpoint."""
    
    # Default quotas: Coinbase Pro typical limits
    DEFAULT_QUOTAS = {
        "/orders": RateLimitQuota(requests_per_window=15, window_seconds=1),  # 15 req/sec
        "/orders/{id}": RateLimitQuota(requests_per_window=15, window_seconds=1),
        "default": RateLimitQuota(requests_per_window=10, window_seconds=1),  # 10 req/sec default
    }
    
    def __init__(self, quotas: Optional[Dict[str, RateLimitQuota]] = None):
        self.quotas = quotas or self.DEFAULT_QUOTAS.copy()
        self.states: Dict[str, RateLimitState] = {}
    
    def _get_state(self, endpoint: str) -> RateLimitState:
        """Get or create rate-limit state for endpoint."""
        if endpoint not in self.states:
            quota = self.quotas.get(endpoint, self.quotas.get("default"))
            self.states[endpoint] = RateLimitState(quota=quota)
        return self.states[endpoint]
    
    def is_allowed(self, endpoint: str) -> bool:
        """Check if a request to endpoint is allowed."""
        state = self._get_state(endpoint)
        return state.is_allowed()
    
    def record_request(self, endpoint: str) -> None:
        """Record a successful request to endpoint."""
        state = self._get_state(endpoint)
        state.record_request()
    
    def time_until_allowed(self, endpoint: str) -> float:
        """Return seconds until next request is allowed."""
        state = self._get_state(endpoint)
        return state.time_until_allowed()
    
    def wait_if_needed(self, endpoint: str, max_wait: float = 60.0) -> bool:
        """Wait until request is allowed; return True if allowed, False if max_wait exceeded.
        
        Args:
            endpoint: API endpoint path
            max_wait: Maximum time to wait in seconds
        
        Returns:
            True if allowed (or waited successfully), False if timeout
        """
        start = time.time()
        while not self.is_allowed(endpoint):
            wait_time = self.time_until_allowed(endpoint)
            if wait_time > 0:
                elapsed = time.time() - start
                if elapsed + wait_time > max_wait:
                    return False
                time.sleep(min(wait_time, max_wait - elapsed))
        
        self.record_request(endpoint)
        return True
