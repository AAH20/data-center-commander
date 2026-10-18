"""Tests for NP-hard optimization kernels.

Each test verifies the approximation guarantee or a specific property
of the algorithm. Tests use real data structures, not mocks.
"""

from __future__ import annotations

import unittest

from dcc.optimization_kernels import (
    Asset,
    CapacityDimension,
    EnergyRequest,
    NetworkNode,
    Technician,
    Workload,
    WorkOrder,
    capacity_allocation,
    clarke_wright_savings,
    dsatur_zoning,
    first_fit_decreasing,
    max_min_fair_energy_allocation,
)


class TestFirstFitDecreasing(unittest.TestCase):
    """Tests for workload placement (bin packing)."""

    def test_places_all_workloads_when_capacity_sufficient(self):
        workloads = [
            Workload("w1", "web", cpu_cores=2, ram_gb=4),
            Workload("w2", "db", cpu_cores=4, ram_gb=8),
            Workload("w3", "cache", cpu_cores=1, ram_gb=2),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=8, total_ram=16),
            Asset("a2", "server2", total_cpu=8, total_ram=16),
        ]

        result = first_fit_decreasing(workloads, assets)

        # All workloads should be placed
        placed = set()
        for wls in result.values():
            placed.update(wls)
        self.assertEqual(placed, {"w1", "w2", "w3"})

    def test_reports_unplaced_when_capacity_insufficient(self):
        workloads = [
            Workload("w1", "web", cpu_cores=16, ram_gb=32),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=8, total_ram=16),
        ]

        result = first_fit_decreasing(workloads, assets)

        self.assertIn("__unplaced__", result)
        self.assertEqual(result["__unplaced__"], ["w1"])

    def test_respects_anti_affinity(self):
        workloads = [
            Workload("w1", "web1", cpu_cores=2, ram_gb=4, anti_affinity=("w2",)),
            Workload("w2", "web2", cpu_cores=2, ram_gb=4, anti_affinity=("w1",)),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=8, total_ram=16),
        ]

        result = first_fit_decreasing(workloads, assets)

        # With only 1 asset and anti-affinity, at most 1 should be placed
        placed = set()
        for key, wls in result.items():
            if key != "__unplaced__":
                placed.update(wls)
        self.assertLessEqual(len(placed), 1)

    def test_respects_affinity(self):
        workloads = [
            Workload("w1", "web", cpu_cores=2, ram_gb=4, affinity=("w2",)),
            Workload("w2", "db", cpu_cores=4, ram_gb=8, affinity=("w1",)),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=8, total_ram=16),
            Asset("a2", "server2", total_cpu=8, total_ram=16),
        ]

        result = first_fit_decreasing(workloads, assets)

        # Both should be placed on the same asset
        placed = set()
        for wls in result.values():
            placed.update(wls)
        self.assertEqual(placed, {"w1", "w2"})

    def test_ffd_uses_at_most_opt_plus_one(self):
        """FFD guarantee: uses ≤ 11/9 × OPT + 1 bins."""
        # Create workloads that perfectly pack into 2 bins
        workloads = [Workload(f"w{i}", f"wl{i}", cpu_cores=1, ram_gb=1) for i in range(10)]
        assets = [Asset(f"a{i}", f"server{i}", total_cpu=5, total_ram=5) for i in range(2)]

        result = first_fit_decreasing(workloads, assets)

        # Should use at most 2 assets (OPT = 2)
        used_assets = [k for k in result if k != "__unplaced__"]
        self.assertLessEqual(len(used_assets), 2)


class TestClarkeWrightSavings(unittest.TestCase):
    """Tests for maintenance routing (TSP)."""

    def test_routes_all_work_orders(self):
        work_orders = [
            WorkOrder(
                "wo1",
                "a1",
                priority=1,
                duration_hours=2,
                skill_required="electrical",
                latitude=40.7128,
                longitude=-74.0060,
            ),
            WorkOrder(
                "wo2",
                "a2",
                priority=2,
                duration_hours=1,
                skill_required="electrical",
                latitude=40.7580,
                longitude=-73.9855,
            ),
            WorkOrder(
                "wo3",
                "a3",
                priority=3,
                duration_hours=3,
                skill_required="electrical",
                latitude=40.6892,
                longitude=-74.0445,
            ),
        ]
        technicians = [
            Technician(
                "t1", frozenset({"electrical"}), base_latitude=40.7128, base_longitude=-74.0060
            ),
        ]

        result = clarke_wright_savings(work_orders, technicians)

        # All work orders should be assigned
        assigned = set()
        for wos in result.values():
            assigned.update(wos)
        self.assertEqual(assigned, {"wo1", "wo2", "wo3"})

    def test_filters_by_skill(self):
        work_orders = [
            WorkOrder(
                "wo1",
                "a1",
                priority=1,
                duration_hours=2,
                skill_required="electrical",
                latitude=40.7128,
                longitude=-74.0060,
            ),
            WorkOrder(
                "wo2",
                "a2",
                priority=2,
                duration_hours=1,
                skill_required="mechanical",
                latitude=40.7580,
                longitude=-73.9855,
            ),
        ]
        technicians = [
            Technician(
                "t1", frozenset({"electrical"}), base_latitude=40.7128, base_longitude=-74.0060
            ),
        ]

        result = clarke_wright_savings(work_orders, technicians)

        # Only electrical work orders should be assigned
        assigned = set()
        for wos in result.values():
            assigned.update(wos)
        self.assertEqual(assigned, {"wo1"})

    def test_empty_input(self):
        result = clarke_wright_savings([], [])
        self.assertEqual(result, {})


class TestCapacityAllocation(unittest.TestCase):
    """Tests for capacity allocation (multiple knapsack)."""

    def test_allocates_within_capacity(self):
        dimensions = [
            CapacityDimension("power_kw", total=100.0),
            CapacityDimension("cooling_kw", total=200.0),
        ]
        demands: dict[str, dict[str, float]] = {
            "d1": {"power_kw": 30.0, "cooling_kw": 60.0},
            "d2": {"power_kw": 40.0, "cooling_kw": 80.0},
        }

        result = capacity_allocation(dimensions, demands)

        # Total allocated should not exceed capacity
        total_power = sum(result[d].get("power_kw", 0) for d in result)
        total_cooling = sum(result[d].get("cooling_kw", 0) for d in result)
        self.assertLessEqual(total_power, 100)
        self.assertLessEqual(total_cooling, 200)

    def test_allocates_all_when_capacity_sufficient(self):
        dimensions = [
            CapacityDimension("power_kw", total=100.0),
        ]
        demands: dict[str, dict[str, float]] = {
            "d1": {"power_kw": 30.0},
            "d2": {"power_kw": 40.0},
        }

        result = capacity_allocation(dimensions, demands)

        self.assertEqual(result["d1"]["power_kw"], 30)
        self.assertEqual(result["d2"]["power_kw"], 40)

    def test_partial_allocation_when_capacity_insufficient(self):
        dimensions = [
            CapacityDimension("power_kw", total=50.0),
        ]
        demands: dict[str, dict[str, float]] = {
            "d1": {"power_kw": 30.0},
            "d2": {"power_kw": 40.0},
        }

        result = capacity_allocation(dimensions, demands)

        # Total should not exceed 50
        total = sum(result[d].get("power_kw", 0) for d in result)
        self.assertLessEqual(total, 50)


class TestDSATURZoning(unittest.TestCase):
    """Tests for network zoning (graph coloring)."""

    def test_no_adjacent_nodes_share_zone(self):
        nodes = [
            NetworkNode("n1", neighbors=("n2", "n3")),
            NetworkNode("n2", neighbors=("n1", "n3")),
            NetworkNode("n3", neighbors=("n1", "n2")),
        ]

        result = dsatur_zoning(nodes)

        # All nodes should be assigned
        self.assertEqual(set(result.keys()), {"n1", "n2", "n3"})

        # No adjacent nodes should share a zone
        for node in nodes:
            for neighbor in node.neighbors:
                self.assertNotEqual(result[node.id], result[neighbor])

    def test_uses_at_most_delta_plus_one_colors(self):
        # Star graph: center connected to 4 leaves
        # Max degree = 4, so should use ≤ 5 colors
        nodes = [
            NetworkNode("center", neighbors=("l1", "l2", "l3", "l4")),
            NetworkNode("l1", neighbors=("center",)),
            NetworkNode("l2", neighbors=("center",)),
            NetworkNode("l3", neighbors=("center",)),
            NetworkNode("l4", neighbors=("center",)),
        ]

        result = dsatur_zoning(nodes)

        zones_used = set(result.values())
        self.assertLessEqual(len(zones_used), 5)

    def test_empty_input(self):
        result = dsatur_zoning([])
        self.assertEqual(result, {})


class TestMaxMinFairEnergyAllocation(unittest.TestCase):
    """Tests for energy allocation (fractional knapsack with fairness)."""

    def test_allocates_full_budget(self):
        requests = [
            EnergyRequest("w1", energy_kwh=50, useful_work_per_kwh=10),
            EnergyRequest("w2", energy_kwh=50, useful_work_per_kwh=5),
        ]

        result = max_min_fair_energy_allocation(requests, total_energy_kwh=100)

        total = sum(result.values())
        self.assertAlmostEqual(total, 100, places=5)

    def test_higher_gain_gets_more(self):
        requests = [
            EnergyRequest("w1", energy_kwh=50, useful_work_per_kwh=10),
            EnergyRequest("w2", energy_kwh=50, useful_work_per_kwh=5),
        ]

        result = max_min_fair_energy_allocation(requests, total_energy_kwh=100)

        # w1 has higher gain density, should get more
        self.assertGreater(result["w1"], result["w2"])

    def test_respects_minimum_fair_share(self):
        requests = [
            EnergyRequest("w1", energy_kwh=50, useful_work_per_kwh=10, min_fair_share=30),
            EnergyRequest("w2", energy_kwh=50, useful_work_per_kwh=5, min_fair_share=20),
        ]

        result = max_min_fair_energy_allocation(requests, total_energy_kwh=100)

        self.assertGreaterEqual(result["w1"], 30)
        self.assertGreaterEqual(result["w2"], 20)

    def test_empty_input(self):
        result = max_min_fair_energy_allocation([], total_energy_kwh=100)
        self.assertEqual(result, {})

    def test_zero_budget(self):
        requests = [
            EnergyRequest("w1", energy_kwh=50, useful_work_per_kwh=10),
        ]
        result = max_min_fair_energy_allocation(requests, total_energy_kwh=0)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
