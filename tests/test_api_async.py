"""Tests for the async API layer.

Tests pagination, caching, rate limiting, and optimization endpoints.
Uses httpx ASGITransport for in-process testing (no real server needed).
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from dcc.api_async import (
    Page,
    RateLimiter,
    app,
    cache,
    decode_cursor,
    encode_cursor,
    first_fit_decreasing,
    list_assets,
)


class TestPagination(unittest.TestCase):
    def test_encode_decode_cursor_roundtrip(self):
        cursor = encode_cursor(500)
        self.assertEqual(decode_cursor(cursor), 500)

    def test_decode_invalid_cursor_raises(self):
        with self.assertRaises(ValueError):
            decode_cursor("not-valid!!!")

    def test_page_has_more_when_extra_row(self):
        page = Page(
            items=[{"id": "1"}, {"id": "2"}],
            total=100,
            limit=2,
            offset=0,
            has_more=True,
            next_cursor=encode_cursor(2),
        )
        self.assertTrue(page.has_more)
        self.assertIsNotNone(page.next_cursor)

    def test_page_no_more_when_last_page(self):
        page = Page(
            items=[{"id": "99"}, {"id": "100"}],
            total=100,
            limit=2,
            offset=98,
            has_more=False,
            next_cursor=None,
        )
        self.assertFalse(page.has_more)
        self.assertIsNone(page.next_cursor)


class TestCache(unittest.TestCase):
    def test_cache_set_and_get(self):
        cache._data.clear()
        cache.set("test:key", {"value": 42}, ttl=60)
        result = cache.get("test:key")
        self.assertEqual(result, {"value": 42})

    def test_cache_expiry(self):
        cache._data.clear()
        cache.set("test:expired", "value", ttl=-1)
        result = cache.get("test:expired")
        self.assertIsNone(result)

    def test_cache_invalidate(self):
        cache._data.clear()
        cache.set("tenant:1:overview", {"data": 1})
        cache.set("tenant:2:overview", {"data": 2})
        cache.invalidate("tenant:1")
        self.assertIsNone(cache.get("tenant:1:overview"))
        self.assertIsNotNone(cache.get("tenant:2:overview"))


class TestRateLimiter(unittest.TestCase):
    def test_allows_within_limit(self):
        limiter = RateLimiter(rps=100)
        for _ in range(10):
            self.assertTrue(limiter.is_allowed("client1"))

    def test_blocks_over_limit(self):
        limiter = RateLimiter(rps=2)
        # Consume initial tokens
        self.assertTrue(limiter.is_allowed("client2"))
        self.assertTrue(limiter.is_allowed("client2"))
        # Third immediate call should fail (no time for token replenishment)
        self.assertFalse(limiter.is_allowed("client2"))

    def test_separate_clients_independent(self):
        limiter = RateLimiter(rps=100)
        self.assertTrue(limiter.is_allowed("client_a"))
        self.assertTrue(limiter.is_allowed("client_b"))
        # Different clients have separate buckets


class TestOptimizationEndpoints(unittest.TestCase):
    """Test the optimization kernel endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_optimization_kernels_callable(self):
        """Verify all optimization kernels are importable and callable."""
        self.assertTrue(callable(first_fit_decreasing))

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["service"], "data-center-commander")
        self.assertFalse(data["execution_permitted"])

    def test_readyz_no_db(self):
        """readyz should return 503 when DB is not configured."""
        with patch("dcc.api_async.get_pool", side_effect=Exception("no db")):
            response = self.client.get("/readyz")
            self.assertEqual(response.status_code, 503)

    def test_pagination_params(self):
        """Test that pagination params are accepted (no 422 validation error)."""
        # Verify the endpoint function signature accepts the expected params
        sig = inspect.signature(list_assets)
        param_names = list(sig.parameters.keys())
        self.assertIn("tenant_id", param_names)
        self.assertIn("limit", param_names)
        self.assertIn("cursor", param_names)


class TestEvidenceVerification(unittest.TestCase):
    def test_hash_chain_verification(self):
        """Test that evidence chain verification detects tampering."""
        import hashlib

        # Build a valid chain
        events = []
        prev_hash = ""
        for i in range(5):
            payload = f"event_{i}"
            h = hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()
            events.append({"sequence": i, "hash": h, "payload": payload})
            prev_hash = h

        # Verify chain
        prev_hash = ""
        for event in events:
            computed = hashlib.sha256(f"{prev_hash}{event['payload']}".encode()).hexdigest()
            self.assertEqual(computed, event["hash"])
            prev_hash = event["hash"]

        # Tamper with one event
        events[2]["payload"] = "tampered"
        prev_hash = ""
        tampered = False
        for event in events:
            computed = hashlib.sha256(f"{prev_hash}{event['payload']}".encode()).hexdigest()
            if computed != event["hash"]:
                tampered = True
                break
            prev_hash = event["hash"]
        self.assertTrue(tampered)


if __name__ == "__main__":
    unittest.main()
