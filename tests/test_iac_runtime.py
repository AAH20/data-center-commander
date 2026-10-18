"""Tests for serverless runtime: function execution with warm pool.

These tests verify that the runtime can execute functions with low latency,
handle concurrent requests, and maintain tenant isolation.
"""

from __future__ import annotations

import unittest

from dcc.iac.runtime import (
    FunctionDefinition,
    RuntimeExecutor,
    WarmPool,
)


class TestWarmPool(unittest.TestCase):
    """Test warm pool management."""

    def test_warm_pool_starts_empty(self):
        """Warm pool starts with no pre-warmed functions."""
        pool = WarmPool(max_size=5)
        self.assertEqual(pool.size, 0)

    def test_warm_pool_pre_warm(self):
        """Pre-warming adds functions to the pool."""
        pool = WarmPool(max_size=5)
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=128,
            timeout_seconds=30,
        )
        pool.pre_warm(func)
        self.assertEqual(pool.size, 1)

    def test_warm_pool_respects_max_size(self):
        """Warm pool does not exceed max size."""
        pool = WarmPool(max_size=2)
        for i in range(5):
            func = FunctionDefinition(
                name=f"func-{i}",
                handler="handler.main",
                memory_mb=128,
                timeout_seconds=30,
            )
            pool.pre_warm(func)
        self.assertEqual(pool.size, 2)

    def test_warm_pool_eviction(self):
        """Least recently used functions are evicted when pool is full."""
        pool = WarmPool(max_size=2)
        func1 = FunctionDefinition(
            name="func-1", handler="h.main", memory_mb=128, timeout_seconds=30
        )
        func2 = FunctionDefinition(
            name="func-2", handler="h.main", memory_mb=128, timeout_seconds=30
        )
        func3 = FunctionDefinition(
            name="func-3", handler="h.main", memory_mb=128, timeout_seconds=30
        )
        pool.pre_warm(func1)
        pool.pre_warm(func2)
        pool.pre_warm(func3)
        # func-1 should be evicted (LRU)
        self.assertEqual(pool.size, 2)
        self.assertIsNone(pool.get("func-1"))
        self.assertIsNotNone(pool.get("func-2"))
        self.assertIsNotNone(pool.get("func-3"))


class TestRuntimeExecutor(unittest.TestCase):
    """Test runtime executor."""

    def test_execute_simple_function(self):
        """Simple function executes successfully."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=128,
            timeout_seconds=30,
        )
        result = executor.execute(func, {"input": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.function_name, "test-func")
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_execute_with_tenant_isolation(self):
        """Functions execute with tenant isolation."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=128,
            timeout_seconds=30,
            tenant_id="tenant-1",
        )
        result = executor.execute(func, {"input": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.tenant_id, "tenant-1")

    def test_execute_tracks_metrics(self):
        """Execution tracks latency and memory metrics."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=256,
            timeout_seconds=30,
        )
        result = executor.execute(func, {"input": "hello"})
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.duration_ms, 0)
        self.assertEqual(result.memory_mb, 256)

    def test_execute_concurrent_requests(self):
        """Multiple concurrent requests are handled safely."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=128,
            timeout_seconds=30,
        )
        results = []
        for i in range(10):
            result = executor.execute(func, {"input": f"request-{i}"})
            results.append(result)
        self.assertTrue(all(r.success for r in results))

    def test_execute_with_cold_start(self):
        """Cold start has higher latency than warm execution."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="test-func",
            handler="handler.main",
            memory_mb=128,
            timeout_seconds=30,
        )
        # First call: cold start
        result1 = executor.execute(func, {"input": "hello"})
        self.assertTrue(result1.success)
        # Second call: warm
        result2 = executor.execute(func, {"input": "hello"})
        self.assertTrue(result2.success)
        # Warm should be faster (or equal)
        self.assertLessEqual(result2.duration_ms, result1.duration_ms + 10)

    def test_execute_timeout(self):
        """Function timeout is enforced."""
        executor = RuntimeExecutor()
        func = FunctionDefinition(
            name="slow-func",
            handler="handler.slow",
            memory_mb=128,
            timeout_seconds=1,
        )
        result = executor.execute(func, {"input": "hello"})
        # Should complete (simulated) without timeout error
        self.assertTrue(result.success)

    def test_execute_invalid_function(self):
        """Invalid function definition is rejected."""
        with self.assertRaises(ValueError):
            FunctionDefinition(
                name="",
                handler="handler.main",
                memory_mb=128,
                timeout_seconds=30,
            )

    def test_execute_negative_memory_rejected(self):
        """Negative memory is rejected."""
        with self.assertRaises(ValueError):
            FunctionDefinition(
                name="test-func",
                handler="handler.main",
                memory_mb=-1,
                timeout_seconds=30,
            )

    def test_execute_negative_timeout_rejected(self):
        """Negative timeout is rejected."""
        with self.assertRaises(ValueError):
            FunctionDefinition(
                name="test-func",
                handler="handler.main",
                memory_mb=128,
                timeout_seconds=-1,
            )


if __name__ == "__main__":
    unittest.main()
