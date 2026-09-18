"""Sliding-window token-bucket rate limiter.

Protects LLM quotas, optimization solver compute resources, and API endpoints
from exhaustion, abusive traffic spikes, and denial-of-service attacks.
"""

import time
import threading
from typing import Dict, Tuple


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter per client key."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_capacity: int = 10,
        cleanup_interval_seconds: float = 300.0
    ):
        self.rate = requests_per_minute / 60.0  # Tokens per second
        self.capacity = float(requests_per_minute + burst_capacity)
        self.cleanup_interval = cleanup_interval_seconds
        
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update_time)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def is_allowed(self, key: str) -> Tuple[bool, int, float]:
        """Checks if a request is allowed for the given key.
        
        Returns:
            (is_allowed, remaining_tokens_int, retry_after_seconds)
        """
        now = time.time()
        with self._lock:
            # Periodic cleanup of stale keys
            if now - self._last_cleanup > self.cleanup_interval:
                self._cleanup(now)

            if key not in self._buckets:
                tokens = self.capacity - 1.0
                self._buckets[key] = (tokens, now)
                return True, int(tokens), 0.0

            tokens, last_time = self._buckets[key]
            # Add replenished tokens based on elapsed time
            elapsed = now - last_time
            tokens = min(self.capacity, tokens + elapsed * self.rate)

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = (tokens, now)
                return True, int(tokens), 0.0
            else:
                self._buckets[key] = (tokens, now)
                # Calculate required wait time for 1 full token
                needed = 1.0 - tokens
                retry_after = round(needed / self.rate, 2)
                return False, 0, max(0.1, retry_after)

    def _cleanup(self, now: float) -> None:
        """Removes entries inactive for longer than 10 minutes."""
        stale_threshold = now - 600.0
        stale_keys = [k for k, (_, t) in self._buckets.items() if t < stale_threshold]
        for k in stale_keys:
            del self._buckets[k]
        self._last_cleanup = now

    def reset(self, key: str) -> None:
        """Resets the rate limit bucket for a specific key."""
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


# Global rate limiter instance
rate_limiter = TokenBucketRateLimiter()
