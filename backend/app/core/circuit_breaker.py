"""
Circuit Breaker — Fault tolerance for LLM and external service calls.

States:
  CLOSED   → Normal operation, requests pass through
  OPEN     → Failures exceeded threshold, requests fail-fast
  HALF_OPEN → Recovery probe: allow limited requests to test recovery

PRD §17: Repeated crash loop triggers safe mode (DEGRADED).
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Coroutine

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("core.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is OPEN and request is rejected."""

    def __init__(self, name: str, time_until_recovery: float):
        self.name = name
        self.time_until_recovery = time_until_recovery
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Recovery in {time_until_recovery:.1f}s"
        )


class CircuitBreaker:
    """
    Async circuit breaker with configurable thresholds.

    Usage:
        breaker = CircuitBreaker("llm")
        result = await breaker.call(some_async_func, *args, **kwargs)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_timeout_seconds: float | None = None,
        half_open_max_calls: int | None = None,
    ):
        settings = get_settings()
        self.name = name
        self._failure_threshold = failure_threshold or settings.circuit_breaker_failure_threshold
        self._recovery_timeout = recovery_timeout_seconds or settings.circuit_breaker_recovery_timeout_seconds
        self._half_open_max = half_open_max_calls or settings.circuit_breaker_half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0
        self._opened_at: float = 0
        self._total_trips = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state, auto-transitioning OPEN → HALF_OPEN after timeout."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._opened_at
            if elapsed >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def stats(self) -> dict:
        """Current circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_trips": self._total_trips,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout_s": self._recovery_timeout,
        }

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function through the circuit breaker."""
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                remaining = self._recovery_timeout - (time.time() - self._opened_at)
                raise CircuitBreakerOpen(self.name, max(0, remaining))

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max:
                    raise CircuitBreakerOpen(self.name, 0)

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            current = self.state

            if current == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self._half_open_max:
                    # Recovery confirmed
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
                    logger.info(
                        "circuit_breaker_recovered",
                        name=self.name,
                    )

            self._success_count += 1
            if current == CircuitState.CLOSED:
                self._failure_count = 0  # Reset on success

    async def _on_failure(self, error: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            current = self.state

            if current == CircuitState.HALF_OPEN:
                # Recovery probe failed — re-open
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._half_open_calls = 0
                logger.warning(
                    "circuit_breaker_reopened",
                    name=self.name,
                    error=str(error),
                )
            elif self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._total_trips += 1
                logger.error(
                    "circuit_breaker_tripped",
                    name=self.name,
                    failure_count=self._failure_count,
                    total_trips=self._total_trips,
                    recovery_in_s=self._recovery_timeout,
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("circuit_breaker_reset", name=self.name)


# ── Singleton instances ──
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


def get_all_breaker_stats() -> list[dict]:
    """Get stats for all circuit breakers."""
    return [b.stats for b in _breakers.values()]
