"""API rate limiting: per-tenant, per-endpoint, and per-user rate limits.

This module provides a sliding-window rate limiter suitable for the
Data Center Commander HTTP API. It enforces three independent dimensions:

- **Per-tenant**: each tenant UUID gets its own rate-limit bucket so one
  tenant cannot starve others.
- **Per-endpoint**: each API route can have its own limit (e.g. expensive
  analytics queries vs. cheap health checks).
- **Per-user**: each authenticated user (API key or session) gets their own
  limit within a tenant.

The limiter is in-memory and thread-safe. For multi-process deployments,
subclass :class:`RateLimiter` and override the storage methods to use a
shared backend (e.g. Redis).

Usage
-----

.. code-block:: python

    from dcc.security.rate_limit import RateLimiter, RateLimit

    limiter = RateLimiter()

    # Check a request
    check = limiter.check_rate_limit(
        tenant_id="dcc00000-0000-4000-8000-000000000001",
        endpoint="/v1/analytics",
        user_id="user-42",
    )
    if not check.allowed:
        # Return 429 with Retry-After header
        response = {"error": "rate_limit_exceeded", "retry_after": check.retry_after}
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = [
    "RateLimiter",
    "RateLimit",
    "RateLimitExceeded",
    "RateLimitConfig",
    "RateLimitStatus",
    "default_rate_limit_config",
    "get_rate_limiter",
    "reset_rate_limiter",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Immutable rate-limit configuration for a single scope.

    Parameters
    ----------
    requests:
        Maximum number of requests allowed within ``window_seconds``.
    window_seconds:
        Sliding window duration in seconds.
    burst:
        Optional burst capacity. When > ``requests``, the first ``burst``
        requests in a window are always allowed even if the sustained rate
        is exceeded. Defaults to ``requests``.
    """

    requests: int
    window_seconds: float
    burst: int = 0

    def __post_init__(self) -> None:
        if self.requests < 1:
            raise ValueError("requests must be >= 1")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if self.burst < 0:
            raise ValueError("burst must be >= 0")
        if self.burst < self.requests:
            object.__setattr__(self, "burst", self.requests)


def default_rate_limit_config() -> dict[str, RateLimitConfig]:
    """Return sensible default rate-limit configurations keyed by endpoint.

    These defaults are intentionally conservative for a read-only operations
    dashboard. Adjust as needed for production workloads.
    """
    return {
        # Health and readiness: generous but not unlimited
        "/healthz": RateLimitConfig(requests=60, window_seconds=60),
        "/readyz": RateLimitConfig(requests=60, window_seconds=60),
        # Standard read endpoints
        "/v1/overview": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/topology": RateLimitConfig(requests=60, window_seconds=60),
        "/v1/assets": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/facilities": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/workflows": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/connectors": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/capacity": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/evidence": RateLimitConfig(requests=120, window_seconds=60),
        "/v1/costs": RateLimitConfig(requests=60, window_seconds=60),
        # Expensive analytics: tighter limit
        "/v1/analytics": RateLimitConfig(requests=30, window_seconds=60),
        # Pricing endpoints (external API calls)
        "/v1/pricing/azure-retail": RateLimitConfig(requests=30, window_seconds=60),
        "/v1/pricing/google-cloud-retail": RateLimitConfig(requests=30, window_seconds=60),
        # Placement scenarios (write endpoint)
        "/v1/placement/scenarios": RateLimitConfig(requests=30, window_seconds=60),
        # Static assets: generous
        "/assets/": RateLimitConfig(requests=300, window_seconds=60),
        # Root page
        "/": RateLimitConfig(requests=120, window_seconds=60),
    }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded.

    Attributes
    ----------
    retry_after:
        Seconds the client should wait before retrying.
    limit:
        The :class:`RateLimitConfig` that was exceeded.
    """

    def __init__(self, retry_after: float, limit: RateLimitConfig) -> None:
        self.retry_after = retry_after
        self.limit = limit
        super().__init__(
            f"Rate limit exceeded: {limit.requests} requests per "
            f"{limit.window_seconds}s. Retry after {retry_after:.1f}s."
        )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitStatus:
    """Result of a rate-limit check.

    Attributes
    ----------
    allowed:
        True if the request may proceed.
    remaining:
        Number of requests remaining in the current window.
    reset_at:
        Unix timestamp when the current window resets.
    retry_after:
        Seconds to wait before retrying (only meaningful when ``allowed`` is
        False).
    limit:
        The configuration that was checked.
    """

    allowed: bool
    remaining: int
    reset_at: float
    retry_after: float
    limit: RateLimitConfig


# ---------------------------------------------------------------------------
# Sliding-window counter
# ---------------------------------------------------------------------------


@dataclass
class _Window:
    """Sliding-window counter for a single rate-limit bucket."""

    timestamps: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune(self, now: float, window_seconds: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - window_seconds
        # Timestamps are appended in order, so we can stop at the first
        # one that is still within the window.
        idx = 0
        for i, ts in enumerate(self.timestamps):
            if ts > cutoff:
                idx = i
                break
        else:
            # All timestamps are outside the window
            self.timestamps.clear()
            return
        if idx > 0:
            del self.timestamps[:idx]

    def check_and_record(
        self,
        now: float,
        config: RateLimitConfig,
    ) -> RateLimitStatus:
        """Check if a request is allowed and record it if so.

        This method is thread-safe.
        """
        with self.lock:
            self._prune(now, config.window_seconds)
            count = len(self.timestamps)

            if count < config.requests:
                # Under the sustained limit — allow
                self.timestamps.append(now)
                remaining = config.requests - count - 1
                reset_at = self.timestamps[0] + config.window_seconds if self.timestamps else now + config.window_seconds
                return RateLimitStatus(
                    allowed=True,
                    remaining=remaining,
                    reset_at=reset_at,
                    retry_after=0.0,
                    limit=config,
                )

            if count < config.burst:
                # Over sustained limit but within burst — allow
                self.timestamps.append(now)
                remaining = config.burst - count - 1
                reset_at = self.timestamps[0] + config.window_seconds if self.timestamps else now + config.window_seconds
                return RateLimitStatus(
                    allowed=True,
                    remaining=remaining,
                    reset_at=reset_at,
                    retry_after=0.0,
                    limit=config,
                )

            # Over limit — deny
            retry_after = self.timestamps[0] + config.window_seconds - now
            if retry_after < 0:
                retry_after = 0.0
            return RateLimitStatus(
                allowed=False,
                remaining=0,
                reset_at=self.timestamps[0] + config.window_seconds,
                retry_after=retry_after,
                limit=config,
            )

    def peek(self, now: float, config: RateLimitConfig) -> RateLimitStatus:
        """Check status without recording a request."""
        with self.lock:
            self._prune(now, config.window_seconds)
            count = len(self.timestamps)
            allowed = count < config.burst
            remaining = max(0, config.burst - count)
            reset_at = self.timestamps[0] + config.window_seconds if self.timestamps else now + config.window_seconds
            retry_after = 0.0
            if not allowed:
                retry_after = max(0.0, self.timestamps[0] + config.window_seconds - now)
            return RateLimitStatus(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after,
                limit=config,
            )


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Thread-safe sliding-window rate limiter.

    Enforces per-tenant, per-endpoint, and per-user rate limits. Each
    combination of (tenant, endpoint, user) gets its own independent
    sliding-window counter.

    The limiter is in-memory. For multi-process deployments, subclass and
    override :meth:`_get_window` and :meth:`_cleanup` to use a shared
    backend.

    Parameters
    ----------
    config:
        Mapping of endpoint path to :class:`RateLimitConfig`. If omitted,
        uses :func:`default_rate_limit_config`.
    default_limit:
        Fallback configuration for endpoints not present in ``config``.
        Defaults to 60 requests per 60 seconds.
    cleanup_interval:
        Seconds between automatic cleanup of stale entries. Set to 0 to
        disable automatic cleanup. Defaults to 300.
    clock:
        Callable returning the current Unix timestamp. Injectable for
        testing. Defaults to :func:`time.time`.
    """

    def __init__(
        self,
        config: Optional[dict[str, RateLimitConfig]] = None,
        *,
        default_limit: Optional[RateLimitConfig] = None,
        cleanup_interval: float = 300.0,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._config: dict[str, RateLimitConfig] = dict(config) if config else default_rate_limit_config()
        self._default_limit = default_limit or RateLimitConfig(requests=60, window_seconds=60)
        self._cleanup_interval = cleanup_interval
        self._clock = clock or time.time

        # Nested dict: tenant_id -> endpoint -> user_id -> _Window
        self._windows: dict[str, dict[str, dict[str, _Window]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._lock = threading.Lock()
        self._last_cleanup: float = self._clock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_rate_limit(
        self,
        tenant_id: str,
        endpoint: str,
        user_id: str = "",
    ) -> RateLimitStatus:
        """Check if a request is allowed and record it if so.

        Parameters
        ----------
        tenant_id:
            The tenant UUID. Required.
        endpoint:
            The request path (e.g. ``"/v1/analytics"``).
        user_id:
            Optional user identifier (API key ID, session ID, etc.).
            If empty, only per-tenant and per-endpoint limits apply.

        Returns
        -------
        RateLimitStatus
            The result of the rate-limit check.
        """
        now = self._clock()
        self._maybe_cleanup(now)

        config = self._resolve_config(endpoint)
        window = self._get_window(tenant_id, endpoint, user_id)
        return window.check_and_record(now, config)

    def check_rate_limit_or_raise(
        self,
        tenant_id: str,
        endpoint: str,
        user_id: str = "",
    ) -> RateLimitStatus:
        """Check rate limit and raise :class:`RateLimitExceeded` if denied."""
        status = self.check_rate_limit(tenant_id, endpoint, user_id)
        if not status.allowed:
            raise RateLimitExceeded(status.retry_after, status.limit)
        return status

    def get_status(
        self,
        tenant_id: str,
        endpoint: str,
        user_id: str = "",
    ) -> RateLimitStatus:
        """Get current rate-limit status without consuming a request."""
        now = self._clock()
        config = self._resolve_config(endpoint)
        window = self._get_window(tenant_id, endpoint, user_id)
        return window.peek(now, config)

    def reset(
        self,
        tenant_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """Reset rate-limit counters.

        Parameters are optional filters. With no arguments, all counters
        are cleared. Returns the number of windows cleared.
        """
        with self._lock:
            if tenant_id is None:
                count = sum(
                    len(users)
                    for endpoints in self._windows.values()
                    for users in endpoints.values()
                )
                self._windows.clear()
                return count

            if tenant_id not in self._windows:
                return 0

            if endpoint is None:
                count = sum(
                    len(users)
                    for users in self._windows[tenant_id].values()
                )
                del self._windows[tenant_id]
                return count

            if endpoint not in self._windows[tenant_id]:
                return 0

            if user_id is None:
                count = len(self._windows[tenant_id][endpoint])
                del self._windows[tenant_id][endpoint]
                return count

            if user_id in self._windows[tenant_id][endpoint]:
                del self._windows[tenant_id][endpoint][user_id]
                return 1
            return 0

    def set_endpoint_config(
        self,
        endpoint: str,
        config: RateLimitConfig,
    ) -> None:
        """Override the rate-limit configuration for an endpoint at runtime."""
        with self._lock:
            self._config[endpoint] = config

    def get_endpoint_config(self, endpoint: str) -> RateLimitConfig:
        """Get the effective rate-limit configuration for an endpoint."""
        return self._resolve_config(endpoint)

    @property
    def config(self) -> dict[str, RateLimitConfig]:
        """Return a copy of the current endpoint configuration mapping."""
        return dict(self._config)

    # ------------------------------------------------------------------
    # Integration helper for HTTP handlers
    # ------------------------------------------------------------------

    def check_http_request(
        self,
        tenant_id: str,
        path: str,
        user_id: str = "",
    ) -> tuple[bool, dict[str, str]]:
        """Convenience method for HTTP request handlers.

        Returns a tuple of (allowed, headers). When ``allowed`` is False,
        ``headers`` contains ``Retry-After`` and ``X-RateLimit-*`` headers
        suitable for a 429 response.
        """
        status = self.check_rate_limit(tenant_id, path, user_id)
        headers = {
            "X-RateLimit-Limit": str(status.limit.burst),
            "X-RateLimit-Remaining": str(status.remaining),
            "X-RateLimit-Reset": str(int(status.reset_at)),
        }
        if not status.allowed:
            headers["Retry-After"] = str(max(1, int(status.retry_after) + 1))
            return False, headers
        return True, headers

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _resolve_config(self, endpoint: str) -> RateLimitConfig:
        """Resolve the rate-limit config for an endpoint path.

        Supports prefix matching: if the exact path is not found, the
        longest matching prefix in the config is used. Falls back to
        ``default_limit`` if nothing matches.
        """
        # Exact match first
        if endpoint in self._config:
            return self._config[endpoint]

        # Prefix match (longest prefix wins)
        best_prefix = ""
        best_config: Optional[RateLimitConfig] = None
        for key, cfg in self._config.items():
            if key.endswith("/") and endpoint.startswith(key):
                if len(key) > len(best_prefix):
                    best_prefix = key
                    best_config = cfg

        if best_config is not None:
            return best_config

        return self._default_limit

    def _get_window(
        self,
        tenant_id: str,
        endpoint: str,
        user_id: str,
    ) -> _Window:
        """Get or create the sliding-window counter for a given scope."""
        with self._lock:
            user_windows = self._windows[tenant_id][endpoint]
            if user_id not in user_windows:
                user_windows[user_id] = _Window()
            return user_windows[user_id]

    def _maybe_cleanup(self, now: float) -> None:
        """Periodically remove stale window entries to prevent memory leaks."""
        if self._cleanup_interval <= 0:
            return
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        self._cleanup(now)

    def _cleanup(self, now: float) -> None:
        """Remove windows that have no recent activity.

        A window is considered stale if its oldest timestamp is older than
        twice the maximum window duration across all configs.
        """
        max_window = max(
            cfg.window_seconds for cfg in self._config.values()
        ) if self._config else 60.0
        max_window = max(max_window, self._default_limit.window_seconds)
        stale_threshold = now - (2 * max_window)

        with self._lock:
            empty_tenants: list[str] = []
            for tenant_id, endpoints in self._windows.items():
                empty_endpoints: list[str] = []
                for endpoint, users in endpoints.items():
                    empty_users: list[str] = []
                    for user_id, window in users.items():
                        with window.lock:
                            if not window.timestamps or window.timestamps[-1] < stale_threshold:
                                empty_users.append(user_id)
                    for user_id in empty_users:
                        del users[user_id]
                    if not users:
                        empty_endpoints.append(endpoint)
                for endpoint in empty_endpoints:
                    del endpoints[endpoint]
                if not endpoints:
                    empty_tenants.append(tenant_id)
            for tenant_id in empty_tenants:
                del self._windows[tenant_id]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_limiter: Optional[RateLimiter] = None
_default_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get the process-wide default rate limiter instance."""
    global _default_limiter
    if _default_limiter is None:
        with _default_limiter_lock:
            if _default_limiter is None:
                _default_limiter = RateLimiter()
    return _default_limiter


def reset_rate_limiter() -> None:
    """Reset the process-wide default rate-limiter instance."""
    global _default_limiter
    with _default_limiter_lock:
        _default_limiter = None
