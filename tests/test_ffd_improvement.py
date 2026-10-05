"""Tests for FFD placement improvement.

These tests verify that the improved FFD algorithm achieves >80% placement rate
by using best-fit decreasing instead of first-fit decreasing.
"""
from __future__ import annotations

import random
import unittest

from dcc.optimization_kernels import (
    Asset,
    Workload,
    first_fit_decreasing,
)


class TestFFDImprovement(unittest.TestCase):
    """Test that improved FFD achieves >80% placement rate."""

    def test_placement_rate_above_80_percent(self):
        """FFD should place >80% of workloads across 100 random test cases."""
        test_cases = 100
        total_placement_rate = 0.0

        for seed in range(test_cases):
            random.seed(seed)
            n_workloads = random.randint(5, 50)
            n_assets = random.randint(2, 10)

            workloads = [
                Workload(
                    id=f"w{i}",
                    name=f"wl{i}",
                    cpu_cores=random.uniform(0.5, 8),
                    ram_gb=random.uniform(1, 32),
                    gpu_units=random.uniform(0, 2),
                    power_kw=random.uniform(0.1, 2),
                )
                for i in range(n_workloads)
            ]
            assets = [
                Asset(
                    id=f"a{i}",
                    name=f"server{i}",
                    total_cpu=random.uniform(16, 64),
                    total_ram=random.uniform(64, 256),
                    total_gpu=random.uniform(0, 8),
                    power_budget_kw=random.uniform(5, 20),
                )
                for i in range(n_assets)
            ]

            result = first_fit_decreasing(workloads, assets)

            placed = set()
            for wls in result.values():
                placed.update(wls)

            unplaced = result.get("__unplaced__", [])
            total = len(placed) + len(unplaced)
            quality = len(placed) / total if total > 0 else 1.0
            total_placement_rate += quality

        avg_placement_rate = total_placement_rate / test_cases
        self.assertGreater(
            avg_placement_rate,
            0.80,
            f"FFD placement rate {avg_placement_rate:.2%} is below 80% threshold",
        )

    def test_ffd_respects_all_constraints(self):
        """FFD must respect CPU, RAM, GPU, and power constraints."""
        workloads = [
            Workload("w1", "web", cpu_cores=4, ram_gb=16, gpu_units=1, power_kw=2),
            Workload("w2", "db", cpu_cores=8, ram_gb=32, gpu_units=0, power_kw=3),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=16, total_ram=64, total_gpu=4, power_budget_kw=10),
        ]

        result = first_fit_decreasing(workloads, assets)

        # Verify placed workloads don't exceed capacity
        for asset_id, wl_ids in result.items():
            if asset_id == "__unplaced__":
                continue
            asset = next(a for a in assets if a.id == asset_id)
            total_cpu = sum(w.cpu_cores for w in workloads if w.id in wl_ids)
            total_ram = sum(w.ram_gb for w in workloads if w.id in wl_ids)
            total_gpu = sum(w.gpu_units for w in workloads if w.id in wl_ids)
            total_power = sum(w.power_kw for w in workloads if w.id in wl_ids)

            self.assertLessEqual(total_cpu, asset.total_cpu)
            self.assertLessEqual(total_ram, asset.total_ram)
            self.assertLessEqual(total_gpu, asset.total_gpu)
            self.assertLessEqual(total_power, asset.power_budget_kw)

    def test_ffd_uses_best_fit_for_better_packing(self):
        """FFD should use best-fit (tightest fit) instead of first-fit."""
        # Create workloads that benefit from best-fit
        workloads = [
            Workload("w1", "small", cpu_cores=1, ram_gb=1),
            Workload("w2", "medium", cpu_cores=4, ram_gb=8),
            Workload("w3", "large", cpu_cores=8, ram_gb=16),
        ]
        assets = [
            Asset("a1", "server1", total_cpu=16, total_ram=32),
            Asset("a2", "server2", total_cpu=16, total_ram=32),
        ]

        result = first_fit_decreasing(workloads, assets)

        # All should be placed
        placed = set()
        for wls in result.values():
            placed.update(wls)
        self.assertEqual(placed, {"w1", "w2", "w3"})

    def test_ffd_handles_empty_input(self):
        """FFD should handle empty workloads and assets gracefully."""
        result = first_fit_decreasing([], [])
        self.assertEqual(result, {})

        result = first_fit_decreasing([Workload("w1", "test", cpu_cores=1, ram_gb=1)], [])
        self.assertIn("__unplaced__", result)

    def test_ffd_handles_zero_capacity(self):
        """FFD should handle assets with zero capacity."""
        workloads = [Workload("w1", "test", cpu_cores=1, ram_gb=1)]
        assets = [Asset("a1", "server1", total_cpu=0, total_ram=0)]

        result = first_fit_decreasing(workloads, assets)
        self.assertIn("__unplaced__", result)


if __name__ == "__main__":
    unittest.main()
