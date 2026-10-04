"""Data Center Commander — Caching Layer.

In-memory TTL cache for API responses and external price fetches.
Thread-safe with automatic eviction.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    """A cached value with expiration."""

    value: T
    expires_at: float
    created_at: float = field(default_factory=time.monotonic)


class TTLCache(Generic[T]):
    """Thread-safe TTL cache with LRU eviction.

    Complexity: O(1) get/set, O(N) eviction (amortized).
    """

    def __init__(
        self,
        default_ttl_seconds: float = 60.0,
        max_size: int = 1000,
        cleanup_interval_seconds: float = 300.0,
    ) -> None:
        self._store: dict[str, CacheEntry[T]] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl_seconds
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval_seconds
        self._last_cleanup = time.monotonic()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        """Get value from cache. Returns None if expired or missing."""
        with self._lock:
            self._maybe_cleanup()
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    def set(self, key: str, value: T, ttl_seconds: float | None = None) -> None:
        """Set value in cache with optional custom TTL."""
        with self._lock:
            self._maybe_cleanup()
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            self._store[key] = CacheEntry(
                value=value,
                expires_at=time.monotonic() + ttl,
            )
            # Evict oldest if over capacity
            if len(self._store) > self._max_size:
                self._evict_oldest()

    def invalidate(self, key: str) -> bool:
        """Remove key from cache. Returns True if key existed."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }

    def _maybe_cleanup(self) -> None:
        """Periodically remove expired entries."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]

    def _evict_oldest(self) -> None:
        """Evict oldest entries when cache is full."""
        if not self._store:
            return
        # Remove 10% oldest entries
        sorted_items = sorted(self._store.items(), key=lambda x: x[1].created_at)
        to_remove = max(1, len(sorted_items) // 10)
        for key, _ in sorted_items[:to_remove]:
            del self._store[key]


def cached(
    cache: TTLCache[T],
    key_func: Callable[..., str] | None = None,
    ttl_seconds: float | None = None,
) -> Callable:
    """Decorator for caching function results.

    Usage:
        @cached(price_cache, ttl_seconds=300)
        def fetch_azure_prices(...):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default key: function name + hashed arguments
                key_data = json.dumps(
                    {"args": args, "kwargs": kwargs}, sort_keys=True, default=str
                )
                key = f"{func.__name__}:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


@dataclass
class CircuitState:
    """Circuit breaker state."""

    failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False


class CircuitBreaker:
    """Circuit breaker pattern for external API calls.

    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._state = CircuitState()
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds
        self._half_open_max_calls = half_open_max_calls
        self._half_open_calls = 0
        self._lock = threading.Lock()

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker."""
        with self._lock:
            if self._state.is_open:
                if time.monotonic() - self._state.last_failure_time > self._recovery_timeout:
                    self._state.is_open = False
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")

            if self._half_open_calls >= self._half_open_max_calls:
                raise CircuitBreakerOpenError("Circuit breaker HALF_OPEN limit reached")

            if not self._state.is_open:
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self) -> None:
        with self._lock:
            self._state.failures = 0
            self._state.is_open = False
            self._half_open_calls = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._state.failures += 1
            self._state.last_failure_time = time.monotonic()
            if self._state.failures >= self._failure_threshold:
                self._state.is_open = True

    @property
    def state(self) -> str:
        if self._state.is_open:
            return "OPEN"
        if self._half_open_calls > 0:
            return "HALF_OPEN"
        return "CLOSED"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass
