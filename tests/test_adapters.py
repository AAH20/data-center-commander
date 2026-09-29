"""Tests for the adapter registry: discovery, health, capability negotiation, rate limits."""
from __future__ import annotations

import datetime as dt
import unittest

from dcc.adapters.registry import (
    AdapterCapability,
    AdapterHealth,
    AdapterInfo,
    AdapterRegistry,
    HealthStatus,
    RateLimitState,
    get_registry,
)


def _make_info(
    name: str,
    *,
    version: str = "1.0",
    capabilities: set[AdapterCapability] | None = None,
    endpoint: str = "https://example.com",
    health_check=None,
    metadata: dict | None = None,
) -> AdapterInfo:
    return AdapterInfo(
        name=name,
        version=version,
        description=f"{name} adapter",
        capabilities=frozenset(capabilities or {AdapterCapability.PRICE_LOOKUP}),
        endpoint=endpoint,
        health_check=health_check,
        metadata=metadata or {},
    )


class AdapterRegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg = AdapterRegistry()

    # -- Registration / discovery -------------------------------------------

    def test_register_and_get_info(self):
        info = _make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH})
        self.reg.register(info)
        self.assertEqual(self.reg.get_info("azure"), info)
        self.assertIsNone(self.reg.get_info("missing"))

    def test_unregister(self):
        self.reg.register(_make_info("azure"))
        self.assertTrue(self.reg.unregister("azure"))
        self.assertFalse(self.reg.unregister("azure"))
        self.assertIsNone(self.reg.get_info("azure"))

    def test_discover_all(self):
        self.reg.register(_make_info("azure"))
        self.reg.register(_make_info("gcp"))
        names = {a.name for a in self.reg.discover()}
        self.assertEqual(names, {"azure", "gcp"})

    def test_discover_by_capability(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        self.reg.register(_make_info("gcp", capabilities={AdapterCapability.SKU_SEARCH}))
        results = self.reg.discover(capability=AdapterCapability.PRICE_LOOKUP)
        self.assertEqual([a.name for a in results], ["azure"])

    def test_discover_healthy_only(self):
        self.reg.register(_make_info("azure", health_check=lambda: True))
        self.reg.register(_make_info("gcp", health_check=lambda: False))
        self.reg.check_all_health()
        results = self.reg.discover(healthy_only=True)
        self.assertEqual([a.name for a in results], ["azure"])

    # -- Capability negotiation ---------------------------------------------

    def test_negotiate_single_match(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        result = self.reg.negotiate({AdapterCapability.PRICE_LOOKUP})
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "azure")

    def test_negotiate_no_match(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        result = self.reg.negotiate({AdapterCapability.SKU_SEARCH})
        self.assertIsNone(result)

    def test_negotiate_preferred_breaks_tie(self):
        self.reg.register(_make_info("azure", capabilities={
            AdapterCapability.PRICE_LOOKUP, AdapterCapability.SKU_SEARCH,
        }))
        self.reg.register(_make_info("gcp", capabilities={
            AdapterCapability.PRICE_LOOKUP, AdapterCapability.REGION_AVAILABILITY,
        }))
        result = self.reg.negotiate(
            {AdapterCapability.PRICE_LOOKUP},
            preferred={AdapterCapability.REGION_AVAILABILITY},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "gcp")

    def test_negotiate_alphabetical_tiebreak(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        self.reg.register(_make_info("gcp", capabilities={AdapterCapability.PRICE_LOOKUP}))
        result = self.reg.negotiate({AdapterCapability.PRICE_LOOKUP})
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "azure")

    def test_supports(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        self.assertTrue(self.reg.supports("azure", AdapterCapability.PRICE_LOOKUP))
        self.assertFalse(self.reg.supports("azure", AdapterCapability.SKU_SEARCH))
        self.assertFalse(self.reg.supports("missing", AdapterCapability.PRICE_LOOKUP))

    # -- Health monitoring --------------------------------------------------

    def test_check_health_healthy(self):
        self.reg.register(_make_info("azure", health_check=lambda: True))
        health = self.reg.check_health("azure")
        self.assertEqual(health.status, HealthStatus.HEALTHY)
        self.assertEqual(health.consecutive_failures, 0)
        self.assertIsNotNone(health.last_success_at)

    def test_check_health_unhealthy(self):
        self.reg.register(_make_info("azure", health_check=lambda: False))
        health = self.reg.check_health("azure")
        self.assertEqual(health.status, HealthStatus.UNHEALTHY)
        self.assertEqual(health.consecutive_failures, 1)

    def test_check_health_exception(self):
        def boom():
            raise RuntimeError("connection refused")
        self.reg.register(_make_info("azure", health_check=boom))
        health = self.reg.check_health("azure")
        self.assertEqual(health.status, HealthStatus.UNHEALTHY)
        self.assertIn("connection refused", health.detail)

    def test_check_health_no_check_configured(self):
        self.reg.register(_make_info("azure"))
        health = self.reg.check_health("azure")
        self.assertEqual(health.status, HealthStatus.UNKNOWN)

    def test_check_health_unknown_adapter(self):
        health = self.reg.check_health("missing")
        self.assertEqual(health.status, HealthStatus.UNKNOWN)

    def test_consecutive_failures_increment(self):
        self.reg.register(_make_info("azure", health_check=lambda: False))
        self.reg.check_health("azure")
        self.reg.check_health("azure")
        health = self.reg.check_health("azure")
        self.assertEqual(health.consecutive_failures, 3)

    def test_consecutive_failures_reset_on_success(self):
        calls = []
        def flaky():
            calls.append(1)
            return len(calls) >= 3
        self.reg.register(_make_info("azure", health_check=flaky))
        self.reg.check_health("azure")
        self.reg.check_health("azure")
        health = self.reg.check_health("azure")
        self.assertEqual(health.status, HealthStatus.HEALTHY)
        self.assertEqual(health.consecutive_failures, 0)

    def test_check_all_health(self):
        self.reg.register(_make_info("azure", health_check=lambda: True))
        self.reg.register(_make_info("gcp", health_check=lambda: False))
        results = self.reg.check_all_health()
        self.assertEqual(set(results), {"azure", "gcp"})
        self.assertEqual(results["azure"].status, HealthStatus.HEALTHY)
        self.assertEqual(results["gcp"].status, HealthStatus.UNHEALTHY)

    def test_get_health(self):
        self.reg.register(_make_info("azure", health_check=lambda: True))
        self.assertIsNone(self.reg.get_health("azure"))
        self.reg.check_health("azure")
        self.assertIsNotNone(self.reg.get_health("azure"))

    # -- Rate-limit tracking ------------------------------------------------

    def test_update_rate_limit(self):
        state = self.reg.update_rate_limit("azure", limit=100, remaining=50)
        self.assertEqual(state.limit, 100)
        self.assertEqual(state.remaining, 50)
        self.assertFalse(state.is_exhausted)

    def test_rate_limit_exhausted(self):
        state = self.reg.update_rate_limit("azure", limit=100, remaining=0)
        self.assertTrue(state.is_exhausted)

    def test_rate_limit_throttled(self):
        state = self.reg.update_rate_limit("azure", retry_after_seconds=30.0)
        self.assertTrue(state.is_throttled)

    def test_rate_limit_not_throttled(self):
        state = self.reg.update_rate_limit("azure", retry_after_seconds=0)
        self.assertFalse(state.is_throttled)

    def test_record_rate_limit_from_headers_xratelimit(self):
        headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "999",
            "X-RateLimit-Reset": "1700000000",
        }
        state = self.reg.record_rate_limit_from_headers("azure", headers)
        self.assertEqual(state.limit, 1000)
        self.assertEqual(state.remaining, 999)
        self.assertIsNotNone(state.reset_at)

    def test_record_rate_limit_from_headers_ratelimit(self):
        headers = {
            "RateLimit-Limit": "500",
            "RateLimit-Remaining": "0",
            "RateLimit-Reset": "1700000000",
        }
        state = self.reg.record_rate_limit_from_headers("gcp", headers)
        self.assertEqual(state.limit, 500)
        self.assertEqual(state.remaining, 0)
        self.assertTrue(state.is_exhausted)

    def test_record_rate_limit_from_headers_retry_after(self):
        headers = {"Retry-After": "60"}
        state = self.reg.record_rate_limit_from_headers("azure", headers)
        self.assertEqual(state.retry_after_seconds, 60.0)
        self.assertTrue(state.is_throttled)

    def test_record_rate_limit_from_headers_case_insensitive(self):
        headers = {"x-ratelimit-limit": "100", "x-ratelimit-remaining": "50"}
        state = self.reg.record_rate_limit_from_headers("azure", headers)
        self.assertEqual(state.limit, 100)
        self.assertEqual(state.remaining, 50)

    def test_get_rate_limit(self):
        self.assertIsNone(self.reg.get_rate_limit("azure"))
        self.reg.update_rate_limit("azure", limit=10)
        self.assertIsNotNone(self.reg.get_rate_limit("azure"))

    # -- Snapshot ------------------------------------------------------------

    def test_snapshot(self):
        self.reg.register(_make_info("azure", capabilities={AdapterCapability.PRICE_LOOKUP}))
        self.reg.check_health("azure")
        self.reg.update_rate_limit("azure", limit=100, remaining=50)
        snap = self.reg.snapshot()
        self.assertIn("adapters", snap)
        self.assertIn("health", snap)
        self.assertIn("rate_limits", snap)
        self.assertIn("azure", snap["adapters"])
        self.assertEqual(snap["adapters"]["azure"]["capabilities"], ["price_lookup"])
        self.assertEqual(snap["health"]["azure"]["status"], "unknown")
        self.assertEqual(snap["rate_limits"]["azure"]["limit"], 100)

    # -- Singleton -----------------------------------------------------------

    def test_get_registry_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)

    # -- Thread safety smoke test -------------------------------------------

    def test_concurrent_registration(self):
        import threading
        errors = []
        def register_many(prefix: str, count: int):
            try:
                for i in range(count):
                    self.reg.register(_make_info(f"{prefix}-{i}"))
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=register_many, args=(f"t{j}", 20)) for j in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.reg.adapter_names), 100)


class RateLimitStateTests(unittest.TestCase):
    def test_is_exhausted_none_remaining(self):
        state = RateLimitState(adapter_name="x")
        self.assertFalse(state.is_exhausted)

    def test_is_throttled_none_retry(self):
        state = RateLimitState(adapter_name="x")
        self.assertFalse(state.is_throttled)


class AdapterHealthTests(unittest.TestCase):
    def test_dataclass_fields(self):
        h = AdapterHealth(
            adapter_name="azure",
            status=HealthStatus.HEALTHY,
            checked_at="2026-01-01T00:00:00+00:00",
            latency_ms=12.34,
        )
        self.assertEqual(h.adapter_name, "azure")
        self.assertEqual(h.consecutive_failures, 0)
        self.assertIsNone(h.last_success_at)


if __name__ == "__main__":
    unittest.main()
