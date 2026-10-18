"""Tests for the optimization engine and cache layer.

Covers all 5 NP-hard solvers, TTL cache, and circuit breaker.
"""

from __future__ import annotations

import threading
import time
import unittest

from dcc.cache import CircuitBreaker, CircuitBreakerOpenError, TTLCache, cached
from dcc.optimization import (
    CapacityAllocationSolver,
    EnergyAllocationSolver,
    EnergyConsumer,
    MaintenanceRoutingSolver,
    NetworkZoningSolver,
    Rack,
    ResourceVector,
    Workload,
    WorkloadPlacementSolver,
    WorkOrder,
)


class TestResourceVector(unittest.TestCase):
    """Test ResourceVector operations."""

    def test_addition(self) -> None:
        a = ResourceVector(cpu_cores=4, memory_gb=16)
        b = ResourceVector(cpu_cores=2, memory_gb=8)
        result = a + b
        self.assertEqual(result.cpu_cores, 6)
        self.assertEqual(result.memory_gb, 24)

    def test_subtraction(self) -> None:
        a = ResourceVector(cpu_cores=4, memory_gb=16)
        b = ResourceVector(cpu_cores=2, memory_gb=8)
        result = a - b
        self.assertEqual(result.cpu_cores, 2)
        self.assertEqual(result.memory_gb, 8)

    def test_fits_in(self) -> None:
        small = ResourceVector(cpu_cores=2, memory_gb=8)
        large = ResourceVector(cpu_cores=4, memory_gb=16)
        self.assertTrue(small.fits_in(large))
        self.assertFalse(large.fits_in(small))

    def test_utilization(self) -> None:
        used = ResourceVector(cpu_cores=2, memory_gb=16)
        capacity = ResourceVector(cpu_cores=4, memory_gb=32)
        self.assertAlmostEqual(used.utilization(capacity), 0.5)

    def test_total_demand(self) -> None:
        rv = ResourceVector(cpu_cores=4, memory_gb=16, gpu_units=2)
        self.assertEqual(rv.total_demand(), 22.0)


class TestWorkloadPlacementSolver(unittest.TestCase):
    """Test NP-Hard #1: Workload Placement (Bin Packing FFD)."""

    def test_basic_placement(self) -> None:
        racks = [
            Rack(id="r1", name="Rack 1", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
            Rack(id="r2", name="Rack 2", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
        ]
        workloads = [
            Workload(id="w1", name="Web", resources=ResourceVector(cpu_cores=4, memory_gb=16)),
            Workload(id="w2", name="DB", resources=ResourceVector(cpu_cores=8, memory_gb=32)),
            Workload(id="w3", name="Cache", resources=ResourceVector(cpu_cores=2, memory_gb=8)),
        ]
        solver = WorkloadPlacementSolver(racks)
        placement = solver.solve(workloads)

        self.assertEqual(len(placement), 3)
        self.assertIn("w1", placement)
        self.assertIn("w2", placement)
        self.assertIn("w3", placement)

    def test_unplaced_workloads(self) -> None:
        racks = [Rack(id="r1", name="Rack 1", capacity=ResourceVector(cpu_cores=2, memory_gb=8))]
        workloads = [
            Workload(id="w1", name="Small", resources=ResourceVector(cpu_cores=1, memory_gb=4)),
            Workload(id="w2", name="Big", resources=ResourceVector(cpu_cores=8, memory_gb=32)),
        ]
        solver = WorkloadPlacementSolver(racks)
        placement = solver.solve(workloads)

        self.assertEqual(len(placement), 1)
        self.assertIn("w1", placement)
        self.assertEqual(len(solver.unplaced), 1)
        self.assertEqual(solver.unplaced[0].id, "w2")

    def test_anti_affinity(self) -> None:
        racks = [
            Rack(id="r1", name="Rack 1", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
            Rack(id="r2", name="Rack 2", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
        ]
        workloads = [
            Workload(
                id="w1",
                name="Primary",
                resources=ResourceVector(cpu_cores=4, memory_gb=16),
            ),
            Workload(
                id="w2",
                name="Replica",
                resources=ResourceVector(cpu_cores=4, memory_gb=16),
                anti_affinity=frozenset({"w1"}),
            ),
        ]
        solver = WorkloadPlacementSolver(racks)
        placement = solver.solve(workloads)

        # w1 and w2 should be on different racks
        self.assertNotEqual(placement.get("w1"), placement.get("w2"))

    def test_rack_count(self) -> None:
        racks = [
            Rack(id="r1", name="Rack 1", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
            Rack(id="r2", name="Rack 2", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
            Rack(id="r3", name="Rack 3", capacity=ResourceVector(cpu_cores=16, memory_gb=64)),
        ]
        workloads = [
            Workload(id="w1", name="Web", resources=ResourceVector(cpu_cores=4, memory_gb=16)),
            Workload(id="w2", name="DB", resources=ResourceVector(cpu_cores=4, memory_gb=16)),
        ]
        solver = WorkloadPlacementSolver(racks)
        solver.solve(workloads)

        self.assertGreaterEqual(solver.rack_count, 1)
        self.assertLessEqual(solver.rack_count, 3)


class TestMaintenanceRoutingSolver(unittest.TestCase):
    """Test NP-Hard #2: Maintenance Routing (TSP NN + 2-opt)."""

    def test_basic_route(self) -> None:
        work_orders = [
            WorkOrder(
                id="wo1", title="Fix A", priority=1, duration_hours=2, location="A", x=0, y=0
            ),
            WorkOrder(
                id="wo2", title="Fix B", priority=2, duration_hours=1, location="B", x=3, y=4
            ),
            WorkOrder(
                id="wo3", title="Fix C", priority=3, duration_hours=3, location="C", x=6, y=8
            ),
        ]
        solver = MaintenanceRoutingSolver(depot_x=0, depot_y=0)
        route = solver.solve(work_orders)

        self.assertEqual(len(route), 3)
        # All work orders should be in the route
        route_ids = {wo.id for wo in route}
        self.assertEqual(route_ids, {"wo1", "wo2", "wo3"})

    def test_route_improvement(self) -> None:
        # Create a route that can be improved by 2-opt
        work_orders = [
            WorkOrder(id="wo1", title="A", priority=1, duration_hours=1, location="A", x=0, y=0),
            WorkOrder(id="wo2", title="B", priority=1, duration_hours=1, location="B", x=10, y=0),
            WorkOrder(id="wo3", title="C", priority=1, duration_hours=1, location="C", x=5, y=1),
            WorkOrder(id="wo4", title="D", priority=1, duration_hours=1, location="D", x=5, y=-1),
        ]
        solver = MaintenanceRoutingSolver(depot_x=0, depot_y=0)
        route = solver.solve(work_orders)

        # The optimized route should have reasonable total distance
        total_dist = solver._route_distance(route)
        self.assertGreater(total_dist, 0)
        # Should be less than worst case (visiting in worst order)
        self.assertLess(total_dist, 50.0)

    def test_empty_route(self) -> None:
        solver = MaintenanceRoutingSolver()
        route = solver.solve([])
        self.assertEqual(len(route), 0)

    def test_single_stop(self) -> None:
        work_orders = [
            WorkOrder(id="wo1", title="A", priority=1, duration_hours=1, location="A", x=5, y=5),
        ]
        solver = MaintenanceRoutingSolver()
        route = solver.solve(work_orders)
        self.assertEqual(len(route), 1)


class TestCapacityAllocationSolver(unittest.TestCase):
    """Test NP-Hard #3: Capacity Allocation (Multiple Knapsack)."""

    def test_basic_allocation(self) -> None:
        capacity = ResourceVector(cpu_cores=16, memory_gb=64)
        workloads = [
            Workload(
                id="w1", name="Web", resources=ResourceVector(cpu_cores=4, memory_gb=16), priority=3
            ),
            Workload(
                id="w2", name="DB", resources=ResourceVector(cpu_cores=8, memory_gb=32), priority=5
            ),
            Workload(
                id="w3",
                name="Cache",
                resources=ResourceVector(cpu_cores=2, memory_gb=8),
                priority=1,
            ),
        ]
        solver = CapacityAllocationSolver(capacity)
        allocated, unallocated = solver.solve(workloads)

        # Higher priority should be allocated first
        allocated_ids = {w.id for w in allocated}
        self.assertIn("w2", allocated_ids)  # Highest priority
        self.assertIn("w1", allocated_ids)  # Medium priority

    def test_utilization(self) -> None:
        capacity = ResourceVector(cpu_cores=16, memory_gb=64)
        workloads = [
            Workload(
                id="w1", name="Web", resources=ResourceVector(cpu_cores=8, memory_gb=32), priority=1
            ),
        ]
        solver = CapacityAllocationSolver(capacity)
        solver.solve(workloads)

        self.assertAlmostEqual(solver.utilization, 0.5)

    def test_over_capacity(self) -> None:
        capacity = ResourceVector(cpu_cores=4, memory_gb=16)
        workloads = [
            Workload(
                id="w1", name="Big", resources=ResourceVector(cpu_cores=8, memory_gb=32), priority=1
            ),
        ]
        solver = CapacityAllocationSolver(capacity)
        allocated, unallocated = solver.solve(workloads)

        self.assertEqual(len(allocated), 0)
        self.assertEqual(len(unallocated), 1)


class TestNetworkZoningSolver(unittest.TestCase):
    """Test NP-Hard #4: Network Zoning (Welsh-Powell Graph Coloring)."""

    def test_basic_zoning(self) -> None:
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
        solver = NetworkZoningSolver()
        zones = solver.solve(nodes, edges)

        # A cycle of 4 nodes needs 2 colors
        self.assertEqual(len(zones), 2)

    def test_no_edges(self) -> None:
        nodes = ["a", "b", "c"]
        edges: list[tuple[str, str]] = []
        solver = NetworkZoningSolver()
        zones = solver.solve(nodes, edges)

        # No edges = 1 zone
        self.assertEqual(len(zones), 1)

    def test_complete_graph(self) -> None:
        nodes = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c"), ("a", "c")]
        solver = NetworkZoningSolver()
        zones = solver.solve(nodes, edges)

        # Complete graph K3 needs 3 colors
        self.assertEqual(len(zones), 3)

    def test_adjacent_different_zones(self) -> None:
        nodes = ["a", "b", "c", "d", "e"]
        edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "a"), ("a", "c")]
        solver = NetworkZoningSolver()
        zones = solver.solve(nodes, edges)

        # Build node → zone mapping
        node_zone: dict[str, int] = {}
        for i, zone in enumerate(zones):
            for member in zone.members:
                node_zone[member] = i

        # Adjacent nodes must be in different zones
        for a, b in edges:
            self.assertNotEqual(node_zone[a], node_zone[b])


class TestEnergyAllocationSolver(unittest.TestCase):
    """Test NP-Hard #5: Energy Allocation (Fractional Knapsack)."""

    def test_basic_allocation(self) -> None:
        consumers = [
            EnergyConsumer(id="c1", name="Web", energy_kwh=100, useful_work=500, priority=1),
            EnergyConsumer(id="c2", name="DB", energy_kwh=200, useful_work=800, priority=2),
            EnergyConsumer(id="c3", name="Cache", energy_kwh=50, useful_work=300, priority=3),
        ]
        solver = EnergyAllocationSolver(total_energy_kwh=250)
        allocated, unallocated = solver.solve(consumers)

        # Should allocate to highest value density first
        # c3: 300/50 = 6.0, c1: 500/100 = 5.0, c2: 800/200 = 4.0
        allocated_ids = {c.id for c, _ in allocated}
        self.assertIn("c3", allocated_ids)
        self.assertIn("c1", allocated_ids)

    def test_partial_allocation(self) -> None:
        consumers = [
            EnergyConsumer(id="c1", name="Big", energy_kwh=1000, useful_work=5000, priority=1),
        ]
        solver = EnergyAllocationSolver(total_energy_kwh=500)
        allocated, unallocated = solver.solve(consumers)

        self.assertEqual(len(allocated), 1)
        consumer, fraction = allocated[0]
        self.assertEqual(consumer.id, "c1")
        self.assertAlmostEqual(fraction, 0.5)

    def test_full_allocation(self) -> None:
        consumers = [
            EnergyConsumer(id="c1", name="Small", energy_kwh=100, useful_work=500, priority=1),
        ]
        solver = EnergyAllocationSolver(total_energy_kwh=200)
        allocated, unallocated = solver.solve(consumers)

        self.assertEqual(len(allocated), 1)
        self.assertEqual(len(unallocated), 0)
        consumer, fraction = allocated[0]
        self.assertAlmostEqual(fraction, 1.0)


class TestTTLCache(unittest.TestCase):
    """Test TTL Cache."""

    def test_basic_get_set(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl_seconds=60)
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")

    def test_expiration(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl_seconds=0.01)
        cache.set("key1", "value1")
        time.sleep(0.02)
        self.assertIsNone(cache.get("key1"))

    def test_custom_ttl(self) -> None:
        cache: TTLCache[str] = TTLCache(default_ttl_seconds=60)
        cache.set("key1", "value1", ttl_seconds=0.01)
        time.sleep(0.02)
        self.assertIsNone(cache.get("key1"))

    def test_invalidate(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key1", "value1")
        self.assertTrue(cache.invalidate("key1"))
        self.assertIsNone(cache.get("key1"))
        self.assertFalse(cache.invalidate("key1"))

    def test_clear(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_stats(self) -> None:
        cache: TTLCache[str] = TTLCache()
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        stats = cache.stats
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5)

    def test_max_size_eviction(self) -> None:
        cache: TTLCache[int] = TTLCache(max_size=5)
        for i in range(10):
            cache.set(f"key{i}", i)
        # Should have evicted some entries
        self.assertLessEqual(cache.stats["size"], 5)

    def test_cached_decorator(self) -> None:
        cache: TTLCache[int] = TTLCache()
        call_count = 0

        @cached(cache, ttl_seconds=60)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count, 1)  # Second call served from cache


class TestCircuitBreaker(unittest.TestCase):
    """Test Circuit Breaker."""

    def test_normal_operation(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call(lambda: 42)
        self.assertEqual(result, 42)
        self.assertEqual(cb.state, "CLOSED")

    def test_opens_after_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)

        def failing():
            raise ValueError("fail")

        for _ in range(3):
            with self.assertRaises(ValueError):
                cb.call(failing)

        self.assertEqual(cb.state, "OPEN")

    def test_blocks_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60)

        def failing():
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            cb.call(failing)

        with self.assertRaises(CircuitBreakerOpenError):
            cb.call(lambda: 42)

    def test_recovery(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=0.01)

        def failing():
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            cb.call(failing)

        self.assertEqual(cb.state, "OPEN")

        # Wait for recovery timeout
        time.sleep(0.02)

        # Should be in half-open state and allow calls
        result = cb.call(lambda: 42)
        self.assertEqual(result, 42)
        self.assertEqual(cb.state, "CLOSED")


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of cache and solvers."""

    def test_concurrent_cache_access(self) -> None:
        cache: TTLCache[int] = TTLCache()
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(100):
                    cache.set(f"key{i}", i)
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for i in range(100):
                    cache.get(f"key{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
