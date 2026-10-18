"""Tests for API rate limiting: per-tenant, per-endpoint, per-user."""
from __future__ import annotations

import threading
import time
import unittest

from dcc.security.rate_limit import (
    RateLimitConfig,
    RateLimitExceeded,
    RateLimitStatus,
    RateLimiter,
    default_rate_limit_config,
    get_rate_limiter,
    reset_rate_limiter,
)


class RateLimitConfigTests(unittest.TestCase):
    def test_valid_config(self):
        cfg = RateLimitConfig(requests=10, window_seconds=60)
        self.assertEqual(cfg.requests, 10)
        self.assertEqual(cfg.window_seconds, 60)
        self.assertEqual(cfg.burst, 10)

    def test_burst_defaults_to_requests(self):
        cfg = RateLimitConfig(requests=5, window_seconds=30, burst=0)
        self.assertEqual(cfg.burst, 5)

    def test_burst_can_exceed_requests(self):
        cfg = RateLimitConfig(requests=5, window_seconds=30, burst=20)
        self.assertEqual(cfg.burst, 20)

    def test_invalid_requests(self):
        for bad in (0, -1):
            with self.subTest(requests=bad), self.assertRaises(ValueError):
                RateLimitConfig(requests=bad, window_seconds=60)

    def test_invalid_window(self):
        for bad in (0, -1, -0.5):
            with self.subTest(window=bad), self.assertRaises(ValueError):
                RateLimitConfig(requests=10, window_seconds=bad)

    def test_invalid_burst(self):
        with self.assertRaises(ValueError):
            RateLimitConfig(requests=10, window_seconds=60, burst=-1)


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_covers_key_endpoints(self):
        config = default_rate_limit_config()
        for endpoint in (
            "/healthz", "/readyz", "/v1/overview", "/v1/topology",
            "/v1/assets", "/v1/facilities", "/v1/workflows",
            "/v1/connectors", "/v1/capacity", "/v1/evidence",
            "/v1/costs", "/v1/analytics",
            "/v1/pricing/azure-retail", "/v1/pricing/google-cloud-retail",
            "/v1/placement/scenarios", "/assets/", "/",
        ):
            self.assertIn(endpoint, config, f"missing default config for {endpoint}")

    def test_analytics_has_tighter_limit_than_overview(self):
        config = default_rate_limit_config()
        self.assertLess(
            config["/v1/analytics"].requests,
            config["/v1/overview"].requests,
        )

    def test_all_configs_are_valid(self):
        for endpoint, cfg in default_rate_limit_config().items():
            self.assertGreaterEqual(cfg.requests, 1, endpoint)
            self.assertGreater(cfg.window_seconds, 0, endpoint)
            self.assertGreaterEqual(cfg.burst, cfg.requests, endpoint)


class RateLimiterBasicTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=3, window_seconds=60)},
            default_limit=RateLimitConfig(requests=10, window_seconds=60),
            cleanup_interval=0,
            clock=lambda: self.clock[0],
        )

    def test_allows_requests_under_limit(self):
        for i in range(3):
            status = self.limiter.check_rate_limit("t1", "/test")
            self.assertTrue(status.allowed, f"request {i+1} should be allowed")
            self.assertEqual(status.remaining, 2 - i)

    def test_denies_requests_over_limit(self):
        for _ in range(3):
            self.limiter.check_rate_limit("t1", "/test")
        status = self.limiter.check_rate_limit("t1", "/test")
        self.assertFalse(status.allowed)
        self.assertEqual(status.remaining, 0)
        self.assertGreater(status.retry_after, 0)

    def test_window_slides(self):
        # Use up all 3 requests
        for _ in range(3):
            self.limiter.check_rate_limit("t1", "/test")
        # 4th is denied
        self.assertFalse(self.limiter.check_rate_limit("t1", "/test").allowed)
        # Advance time past the window
        self.clock[0] += 61
        # Now allowed again
        status = self.limiter.check_rate_limit("t1", "/test")
        self.assertTrue(status.allowed)

    def test_burst_allows_temporary_overage(self):
        limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60, burst=5)},
            cleanup_interval=0,
            clock=lambda: self.clock[0],
        )
        # First 2 at sustained rate
        self.assertTrue(limiter.check_rate_limit("t1", "/test").allowed)
        self.assertTrue(limiter.check_rate_limit("t1", "/test").allowed)
        # Next 3 within burst
        for _ in range(3):
            status = limiter.check_rate_limit("t1", "/test")
            self.assertTrue(status.allowed)
        # 6th is over burst
        self.assertFalse(limiter.check_rate_limit("t1", "/test").allowed)


class RateLimiterPerTenantTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_tenants_have_independent_limits(self):
        # Exhaust tenant A
        self.assertTrue(self.limiter.check_rate_limit("tenant-a", "/test").allowed)
        self.assertTrue(self.limiter.check_rate_limit("tenant-a", "/test").allowed)
        self.assertFalse(self.limiter.check_rate_limit("tenant-a", "/test").allowed)
        # Tenant B is unaffected
        status = self.limiter.check_rate_limit("tenant-b", "/test")
        self.assertTrue(status.allowed)
        self.assertEqual(status.remaining, 1)


class RateLimiterPerEndpointTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={
                "/cheap": RateLimitConfig(requests=10, window_seconds=60),
                "/expensive": RateLimitConfig(requests=1, window_seconds=60),
            },
            cleanup_interval=0,
        )

    def test_endpoints_have_independent_limits(self):
        # Exhaust expensive endpoint
        self.assertTrue(self.limiter.check_rate_limit("t1", "/expensive").allowed)
        self.assertFalse(self.limiter.check_rate_limit("t1", "/expensive").allowed)
        # Cheap endpoint is unaffected
        status = self.limiter.check_rate_limit("t1", "/cheap")
        self.assertTrue(status.allowed)
        self.assertEqual(status.remaining, 9)


class RateLimiterPerUserTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_users_have_independent_limits(self):
        # Exhaust user-1
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test", user_id="user-1").allowed)
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test", user_id="user-1").allowed)
        self.assertFalse(self.limiter.check_rate_limit("t1", "/test", user_id="user-1").allowed)
        # user-2 is unaffected
        status = self.limiter.check_rate_limit("t1", "/test", user_id="user-2")
        self.assertTrue(status.allowed)

    def test_empty_user_id_uses_tenant_endpoint_scope(self):
        # With no user_id, the limit is per-tenant+endpoint
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test").allowed)
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test").allowed)
        self.assertFalse(self.limiter.check_rate_limit("t1", "/test").allowed)


class RateLimiterPrefixMatchingTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/assets/": RateLimitConfig(requests=5, window_seconds=60)},
            default_limit=RateLimitConfig(requests=1, window_seconds=60),
            cleanup_interval=0,
        )

    def test_prefix_match_applies(self):
        # /assets/topology.js should match /assets/ prefix
        for _ in range(5):
            status = self.limiter.check_rate_limit("t1", "/assets/topology.js")
            self.assertTrue(status.allowed)
        # 6th is denied
        self.assertFalse(self.limiter.check_rate_limit("t1", "/assets/topology.js").allowed)

    def test_unknown_endpoint_uses_default(self):
        status = self.limiter.check_rate_limit("t1", "/unknown")
        self.assertTrue(status.allowed)
        self.assertFalse(self.limiter.check_rate_limit("t1", "/unknown").allowed)


class RateLimiterStatusTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=5, window_seconds=60)},
            cleanup_interval=0,
            clock=lambda: self.clock[0],
        )

    def test_get_status_does_not_consume(self):
        status = self.limiter.get_status("t1", "/test")
        self.assertTrue(status.allowed)
        self.assertEqual(status.remaining, 5)
        # Still 5 remaining — no request consumed
        status2 = self.limiter.get_status("t1", "/test")
        self.assertEqual(status2.remaining, 5)

    def test_status_reflects_usage(self):
        self.limiter.check_rate_limit("t1", "/test")
        self.limiter.check_rate_limit("t1", "/test")
        status = self.limiter.get_status("t1", "/test")
        self.assertEqual(status.remaining, 3)


class RateLimiterResetTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_reset_all(self):
        self.limiter.check_rate_limit("t1", "/test")
        self.limiter.check_rate_limit("t2", "/test")
        count = self.limiter.reset()
        self.assertGreaterEqual(count, 2)
        # Everything is fresh
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test").allowed)
        self.assertTrue(self.limiter.check_rate_limit("t2", "/test").allowed)

    def test_reset_single_tenant(self):
        self.limiter.check_rate_limit("t1", "/test")
        self.limiter.check_rate_limit("t1", "/test")
        self.limiter.check_rate_limit("t2", "/test")
        self.limiter.reset(tenant_id="t1")
        # t1 is fresh, t2 is not
        self.assertTrue(self.limiter.check_rate_limit("t1", "/test").allowed)
        self.assertTrue(self.limiter.check_rate_limit("t2", "/test").allowed)
        self.assertFalse(self.limiter.check_rate_limit("t2", "/test").allowed)

    def test_reset_nonexistent_tenant(self):
        self.assertEqual(self.limiter.reset(tenant_id="nonexistent"), 0)


class RateLimiterConfigOverrideTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_set_endpoint_config(self):
        self.limiter.set_endpoint_config("/test", RateLimitConfig(requests=100, window_seconds=60))
        for _ in range(100):
            self.assertTrue(self.limiter.check_rate_limit("t1", "/test").allowed)
        self.assertFalse(self.limiter.check_rate_limit("t1", "/test").allowed)

    def test_get_endpoint_config(self):
        cfg = self.limiter.get_endpoint_config("/test")
        self.assertEqual(cfg.requests, 2)
        # Unknown endpoint returns default
        default = self.limiter.get_endpoint_config("/unknown")
        self.assertEqual(default.requests, 60)


class RateLimiterHttpHelperTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=2, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_allowed_request_has_no_retry_after(self):
        allowed, headers = self.limiter.check_http_request("t1", "/test")
        self.assertTrue(allowed)
        self.assertNotIn("Retry-After", headers)
        self.assertIn("X-RateLimit-Limit", headers)
        self.assertIn("X-RateLimit-Remaining", headers)
        self.assertIn("X-RateLimit-Reset", headers)

    def test_denied_request_has_retry_after(self):
        self.limiter.check_rate_limit("t1", "/test")
        self.limiter.check_rate_limit("t1", "/test")
        allowed, headers = self.limiter.check_http_request("t1", "/test")
        self.assertFalse(allowed)
        self.assertIn("Retry-After", headers)
        self.assertGreater(int(headers["Retry-After"]), 0)


class RateLimiterExceptionTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=1, window_seconds=60)},
            cleanup_interval=0,
        )

    def test_raise_on_exceeded(self):
        self.limiter.check_rate_limit("t1", "/test")
        with self.assertRaises(RateLimitExceeded) as ctx:
            self.limiter.check_rate_limit_or_raise("t1", "/test")
        self.assertGreater(ctx.exception.retry_after, 0)
        self.assertEqual(ctx.exception.limit.requests, 1)

    def test_no_raise_when_under_limit(self):
        status = self.limiter.check_rate_limit_or_raise("t1", "/test")
        self.assertTrue(status.allowed)


class RateLimiterCleanupTests(unittest.TestCase):
    def test_cleanup_removes_stale_entries(self):
        clock = [1000.0]
        limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=10, window_seconds=60)},
            cleanup_interval=0,
            clock=lambda: clock[0],
        )
        limiter.check_rate_limit("t1", "/test")
        # Advance well past the window
        clock[0] += 200
        limiter._cleanup(clock[0])
        # Internal state should be empty
        self.assertEqual(len(limiter._windows), 0)

    def test_cleanup_keeps_recent_entries(self):
        clock = [1000.0]
        limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=10, window_seconds=60)},
            cleanup_interval=0,
            clock=lambda: clock[0],
        )
        limiter.check_rate_limit("t1", "/test")
        clock[0] += 30  # Within window
        limiter._cleanup(clock[0])
        self.assertGreater(len(limiter._windows), 0)


class RateLimiterThreadSafetyTests(unittest.TestCase):
    def test_concurrent_requests(self):
        limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=100, window_seconds=60)},
            cleanup_interval=0,
        )
        results: list[bool] = []
        results_lock = threading.Lock()

        def worker():
            status = limiter.check_rate_limit("t1", "/test")
            with results_lock:
                results.append(status.allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 50 should be allowed (under the 100 limit)
        self.assertEqual(len(results), 50)
        self.assertTrue(all(results))

    def test_concurrent_over_limit(self):
        limiter = RateLimiter(
            config={"/test": RateLimitConfig(requests=10, window_seconds=60)},
            cleanup_interval=0,
        )
        results: list[bool] = []
        results_lock = threading.Lock()

        def worker():
            status = limiter.check_rate_limit("t1", "/test")
            with results_lock:
                results.append(status.allowed)

        threads = [threading.Thread(target=worker) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 10 should be allowed
        self.assertEqual(sum(results), 10)
        self.assertEqual(len([r for r in results if not r]), 20)


class SingletonTests(unittest.TestCase):
    def tearDown(self):
        reset_rate_limiter()

    def test_get_rate_limiter_returns_singleton(self):
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        self.assertIs(limiter1, limiter2)

    def test_reset_rate_limiter_clears_singleton(self):
        limiter1 = get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()
        self.assertIsNot(limiter1, limiter2)


if __name__ == "__main__":
    unittest.main()
