"""Tests for optimization kernel improvements.

These tests verify that the improved algorithms meet quality thresholds.
"""

from __future__ import annotations

import random
import unittest

from dcc.optimization_kernels import (
    Asset,
    Technician,
    Workload,
    WorkOrder,
    clarke_wright_savings,
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


class TestClarkeWrightImprovement(unittest.TestCase):
    """Test that improved Clarke-Wright achieves >90% assignment rate."""

    def test_assignment_rate_above_90_percent(self):
        """Clarke-Wright should assign >90% of work orders when capacity and skills are sufficient."""
        test_cases = 50
        total_assignment_rate = 0.0

        for seed in range(test_cases):
            random.seed(seed)
            n_orders = random.randint(3, 20)
            n_techs = random.randint(1, 5)

            # Ensure all skills are covered by at least one technician
            all_skills = {"electrical", "mechanical", "network"}
            technicians = [
                Technician(
                    id=f"t{i}",
                    skills=frozenset(
                        random.sample(
                            list(all_skills),
                            k=random.randint(1, 3),
                        )
                    ),
                    base_latitude=40.5,
                    base_longitude=-74.0,
                    available_hours=100.0,  # Sufficient capacity for all work orders
                )
                for i in range(n_techs)
            ]

            # Verify all skills are covered; if not, add them to first technician
            covered_skills = set()
            for t in technicians:
                covered_skills.update(t.skills)
            missing_skills = all_skills - covered_skills
            if missing_skills and technicians:
                technicians[0] = Technician(
                    id=technicians[0].id,
                    skills=technicians[0].skills | missing_skills,
                    base_latitude=technicians[0].base_latitude,
                    base_longitude=technicians[0].base_longitude,
                    available_hours=technicians[0].available_hours,
                )

            work_orders = [
                WorkOrder(
                    id=f"wo{i}",
                    asset_id=f"a{i}",
                    priority=random.randint(1, 5),
                    duration_hours=random.uniform(0.5, 4),
                    skill_required=random.choice(list(all_skills)),
                    latitude=random.uniform(40.0, 42.0),
                    longitude=random.uniform(-75.0, -73.0),
                )
                for i in range(n_orders)
            ]

            result = clarke_wright_savings(work_orders, technicians)

            assigned = set()
            for wos in result.values():
                assigned.update(wos)

            quality = len(assigned) / n_orders if n_orders > 0 else 1.0
            total_assignment_rate += quality

        avg_assignment_rate = total_assignment_rate / test_cases
        self.assertGreater(
            avg_assignment_rate,
            0.90,
            f"Clarke-Wright assignment rate {avg_assignment_rate:.2%} is below 90% threshold",
        )

    def test_all_orders_assigned_when_skills_match(self):
        """All work orders should be assigned when technicians have matching skills."""
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

        assigned = set()
        for wos in result.values():
            assigned.update(wos)

        self.assertEqual(assigned, {"wo1", "wo2", "wo3"})

    def test_respects_technician_capacity(self):
        """Technicians should not be assigned more work than their available hours."""
        work_orders = [
            WorkOrder(
                f"wo{i}",
                f"a{i}",
                priority=1,
                duration_hours=4,
                skill_required="electrical",
                latitude=40.0 + i * 0.1,
                longitude=-74.0,
            )
            for i in range(5)
        ]
        technicians = [
            Technician(
                "t1",
                frozenset({"electrical"}),
                base_latitude=40.0,
                base_longitude=-74.0,
                available_hours=8.0,
            ),
        ]

        result = clarke_wright_savings(work_orders, technicians)

        # Total assigned hours should not exceed available hours
        for tech_id, wo_ids in result.items():
            tech = next(t for t in technicians if t.id == tech_id)
            total_hours = sum(wo.duration_hours for wo in work_orders if wo.id in wo_ids)
            self.assertLessEqual(
                total_hours,
                tech.available_hours,
                f"Technician {tech_id} assigned {total_hours}h but only has {tech.available_hours}h",
            )


if __name__ == "__main__":
    unittest.main()
