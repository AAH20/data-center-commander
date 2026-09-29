"""Adapter registry: discovery, health monitoring, capability negotiation, and rate-limit tracking."""
from __future__ import annotations

import datetime as dt
import enum
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class AdapterCapability(enum.Enum):
    """Capabilities that an adapter may expose."""
    PRICE_LOOKUP = "price_lookup"
    SKU_SEARCH = "sku_search"
    REGION_AVAILABILITY = "region_availability"
    COST_ESTIMATION = "cost_estimation"
    USAGE_METRICS = "usage_metrics"
    TAG_MANAGEMENT = "tag_management"
    BUDGET_ALERTS = "budget_alerts"
    RESERVATION_PRICING = "reservation_pricing"
    SPOT_PRICING = "spot_pricing"
    COMMITMENT_DISCOUNTS = "commitment_discounts"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthStatus(enum.Enum):
    """Health status of an adapter."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class AdapterHealth:
    """Result of a health check for one adapter."""
    adapter_name: str
    status: HealthStatus
    checked_at: str  # ISO-8601 UTC
    latency_ms: float
    detail: str = ""
    consecutive_failures: int = 0
    last_success_at: str | None = None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RateLimitState:
    """Tracks rate-limit state for an adapter."""
    adapter_name: str
    limit: int | None = None
    remaining: int | None = None
    reset_at: str | None = None  # ISO-8601 UTC
    retry_after_seconds: float | None = None
    updated_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())

    @property
    def is_exhausted(self) -> bool:
        return self.remaining is not None and self.remaining <= 0

    @property
    def is_throttled(self) -> bool:
        return self.retry_after_seconds is not None and self.retry_after_seconds > 0


# ---------------------------------------------------------------------------
# Adapter info
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AdapterInfo:
    """Static metadata for a registered adapter."""
    name: str
    version: str
    description: str
    capabilities: frozenset[AdapterCapability]
    endpoint: str
    health_check: Callable[[], bool] | None = None
    health_check_timeout_s: float = 5.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------

class AdapterProtocol(Protocol):
    """Protocol that concrete adapters should implement."""
    name: str
    version: str

    def health_check(self) -> bool: ...
    def supports(self, capability: AdapterCapability) -> bool: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AdapterRegistry:
    """Thread-safe registry for adapter discovery, health, capabilities, and rate limits."""

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterInfo] = {}
        self._health: dict[str, AdapterHealth] = {}
        self._rate_limits: dict[str, RateLimitState] = {}
        self._lock = threading.RLock()

    # -- Registration -------------------------------------------------------

    def register(self, info: AdapterInfo) -> None:
        """Register or replace an adapter."""
        with self._lock:
            self._adapters[info.name] = info
            # Initialize rate-limit state if absent
            if info.name not in self._rate_limits:
                self._rate_limits[info.name] = RateLimitState(adapter_name=info.name)

    def unregister(self, name: str) -> bool:
        """Remove an adapter. Returns True if it existed."""
        with self._lock:
            existed = name in self._adapters
            self._adapters.pop(name, None)
            self._health.pop(name, None)
            self._rate_limits.pop(name, None)
            return existed

    @property
    def adapter_names(self) -> list[str]:
        with self._lock:
            return sorted(self._adapters)

    def get_info(self, name: str) -> AdapterInfo | None:
        with self._lock:
            return self._adapters.get(name)

    # -- Discovery ----------------------------------------------------------

    def discover(
        self,
        capability: AdapterCapability | None = None,
        *,
        healthy_only: bool = False,
    ) -> list[AdapterInfo]:
        """Discover adapters, optionally filtered by capability and health."""
        with self._lock:
            results: list[AdapterInfo] = []
            for name, info in self._adapters.items():
                if capability is not None and capability not in info.capabilities:
                    continue
                if healthy_only:
                    health = self._health.get(name)
                    if health is None or health.status is not HealthStatus.HEALTHY:
                        continue
                results.append(info)
            return results

    # -- Capability negotiation ---------------------------------------------

    def negotiate(
        self,
        required: set[AdapterCapability],
        *,
        preferred: set[AdapterCapability] | None = None,
    ) -> AdapterInfo | None:
        """Find the best adapter that satisfies all required capabilities.

        When multiple adapters qualify, the one with the most preferred
        capabilities wins. Ties are broken alphabetically by name.
        """
        preferred = preferred or set()
        with self._lock:
            candidates: list[tuple[int, str, AdapterInfo]] = []
            for name, info in self._adapters.items():
                if not required.issubset(info.capabilities):
                    continue
                score = len(preferred & info.capabilities)
                candidates.append((score, name, info))
            if not candidates:
                return None
            candidates.sort(key=lambda t: (-t[0], t[1]))
            return candidates[0][2]

    def supports(self, adapter_name: str, capability: AdapterCapability) -> bool:
        """Check whether a named adapter supports a capability."""
        with self._lock:
            info = self._adapters.get(adapter_name)
            return info is not None and capability in info.capabilities

    # -- Health monitoring --------------------------------------------------

    def check_health(self, name: str) -> AdapterHealth:
        """Run a health check for one adapter and record the result."""
        with self._lock:
            info = self._adapters.get(name)
        if info is None:
            return AdapterHealth(
                adapter_name=name,
                status=HealthStatus.UNKNOWN,
                checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                latency_ms=0.0,
                detail="adapter not registered",
            )

        start = time.monotonic()
        status = HealthStatus.UNHEALTHY
        detail = ""
        try:
            if info.health_check is not None:
                ok = info.health_check()
                status = HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
            else:
                status = HealthStatus.UNKNOWN
                detail = "no health check configured"
        except Exception as exc:
            status = HealthStatus.UNHEALTHY
            detail = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.monotonic() - start) * 1000.0

        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        with self._lock:
            prev = self._health.get(name)
            failures = 0 if status is HealthStatus.HEALTHY else (prev.consecutive_failures + 1 if prev else 1)
            health = AdapterHealth(
                adapter_name=name,
                status=status,
                checked_at=now_iso,
                latency_ms=round(latency_ms, 2),
                detail=detail,
                consecutive_failures=failures,
                last_success_at=now_iso if status is HealthStatus.HEALTHY else (prev.last_success_at if prev else None),
            )
            self._health[name] = health
            return health

    def check_all_health(self) -> dict[str, AdapterHealth]:
        """Run health checks for every registered adapter."""
        with self._lock:
            names = list(self._adapters)
        results: dict[str, AdapterHealth] = {}
        for name in names:
            results[name] = self.check_health(name)
        return results

    def get_health(self, name: str) -> AdapterHealth | None:
        with self._lock:
            return self._health.get(name)

    def get_all_health(self) -> dict[str, AdapterHealth]:
        with self._lock:
            return dict(self._health)

    # -- Rate-limit tracking ------------------------------------------------

    def update_rate_limit(
        self,
        name: str,
        *,
        limit: int | None = None,
        remaining: int | None = None,
        reset_at: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> RateLimitState:
        """Update rate-limit state for an adapter."""
        with self._lock:
            state = self._rate_limits.get(name)
            if state is None:
                state = RateLimitState(adapter_name=name)
                self._rate_limits[name] = state
            if limit is not None:
                state.limit = limit
            if remaining is not None:
                state.remaining = remaining
            if reset_at is not None:
                state.reset_at = reset_at
            if retry_after_seconds is not None:
                state.retry_after_seconds = retry_after_seconds
            state.updated_at = dt.datetime.now(dt.timezone.utc).isoformat()
            return state

    def get_rate_limit(self, name: str) -> RateLimitState | None:
        with self._lock:
            return self._rate_limits.get(name)

    def get_all_rate_limits(self) -> dict[str, RateLimitState]:
        with self._lock:
            return dict(self._rate_limits)

    def record_rate_limit_from_headers(
        self,
        name: str,
        headers: dict[str, str],
    ) -> RateLimitState:
        """Update rate-limit state from common HTTP response headers.

        Recognises: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset,
        Retry-After (seconds), RateLimit-Limit, RateLimit-Remaining, RateLimit-Reset.
        """
        def _get(*keys: str) -> str | None:
            for k in keys:
                v = headers.get(k) or headers.get(k.lower())
                if v is not None:
                    return v
            return None

        def _int(val: str | None) -> int | None:
            if val is None:
                return None
            try:
                return int(val)
            except (TypeError, ValueError):
                return None

        def _float(val: str | None) -> float | None:
            if val is None:
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        limit = _int(_get("X-RateLimit-Limit", "RateLimit-Limit"))
        remaining = _int(_get("X-RateLimit-Remaining", "RateLimit-Remaining"))
        reset_raw = _get("X-RateLimit-Reset", "RateLimit-Reset")
        reset_at: str | None = None
        if reset_raw is not None:
            ts = _float(reset_raw)
            if ts is not None:
                reset_at = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat()
        retry_after = _float(_get("Retry-After"))
        return self.update_rate_limit(
            name,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=retry_after,
        )

    # -- Snapshot / reporting ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the registry state."""
        with self._lock:
            return {
                "adapters": {
                    name: {
                        "name": info.name,
                        "version": info.version,
                        "description": info.description,
                        "capabilities": sorted(c.value for c in info.capabilities),
                        "endpoint": info.endpoint,
                        "metadata": info.metadata,
                    }
                    for name, info in sorted(self._adapters.items())
                },
                "health": {
                    name: {
                        "status": h.status.value,
                        "checked_at": h.checked_at,
                        "latency_ms": h.latency_ms,
                        "detail": h.detail,
                        "consecutive_failures": h.consecutive_failures,
                        "last_success_at": h.last_success_at,
                    }
                    for name, h in sorted(self._health.items())
                },
                "rate_limits": {
                    name: {
                        "limit": rl.limit,
                        "remaining": rl.remaining,
                        "reset_at": rl.reset_at,
                        "retry_after_seconds": rl.retry_after_seconds,
                        "updated_at": rl.updated_at,
                        "is_exhausted": rl.is_exhausted,
                        "is_throttled": rl.is_throttled,
                    }
                    for name, rl in sorted(self._rate_limits.items())
                },
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_registry: AdapterRegistry | None = None
_default_lock = threading.Lock()


def get_registry() -> AdapterRegistry:
    """Return the process-wide default registry, creating it on first use."""
    global _default_registry
    if _default_registry is None:
        with _default_lock:
            if _default_registry is None:
                _default_registry = AdapterRegistry()
    return _default_registry
