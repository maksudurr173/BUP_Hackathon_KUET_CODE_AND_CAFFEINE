"""Circuit breaker implementation for external LLM provider calls.

Prevents cascading failures, protects external quotas, and orchestrates
automated failover to safe fallback modes when external dependencies degrade.
"""

import time
import threading
from enum import Enum
from typing import Dict, Any
from gridwise.app.errors import LLMUnavailableException


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class LLMCircuitBreaker:
    """Thread-safe circuit breaker for external LLM calls."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        half_open_limit: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_limit = half_open_limit

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0
            return self._state

    def can_execute(self) -> bool:
        """Returns True if execution is permitted; raises or returns False if OPEN."""
        curr_state = self.state
        return curr_state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Records a successful execution, updating state appropriately."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_limit:
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._half_open_successes = 0
            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0

    def record_failure(self, error: Exception) -> None:
        """Records a failed execution, tripping the circuit if threshold is reached."""
        with self._lock:
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                # Any failure during half-open immediately returns circuit to OPEN
                self._state = CircuitState.OPEN
                self._half_open_successes = 0
            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN

    def trip_manually(self) -> None:
        """Forcefully trips the circuit breaker to OPEN (e.g. on security incident)."""
        with self._lock:
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()
            self._half_open_successes = 0

    def reset_manually(self) -> None:
        """Manually resets the circuit breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._half_open_successes = 0

    def get_status(self) -> Dict[str, Any]:
        """Returns current state metrics without exposing sensitive internals."""
        with self._lock:
            return {
                "state": self.state.value,
                "consecutive_failures": self._consecutive_failures,
                "half_open_successes": self._half_open_successes,
                "last_failure_elapsed_seconds": (
                    round(time.time() - self._last_failure_time, 2)
                    if self._last_failure_time > 0 else None
                )
            }


# Global LLM circuit breaker instance
llm_circuit_breaker = LLMCircuitBreaker()
