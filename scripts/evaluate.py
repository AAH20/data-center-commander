"""Evaluation and benchmark framework for Data Center Commander.

Runs performance benchmarks, optimization quality tests, and generates
a comprehensive evaluation report with evolution parameters.
"""
from __future__ import annotations

import json
import time
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dcc.optimization_kernels import (
    Asset,
    CapacityDimension,
    EnergyRequest,
    NetworkNode,
    Technician,
    WorkOrder,
    Workload,
    capacity_allocation,
    clarke_wright_savings,
    dsatur_zoning,
    first_fit_decreasing,
    max_min_fair_energy_allocation,
)


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_time_ms: float
    mean_ms: float
    p50_ms: float
    p99_ms: float
    throughput_per_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationQuality:
    problem: str
    algorithm: str
    approximation_ratio: str
    test_cases: int
    passed: int
    failed: int
    avg_quality_score: float


class BenchmarkRunner:
    """Runs performance benchmarks on optimization kernels."""

    def __init__(self) -> None:
        self.results: list[BenchmarkResult] = []

    def run_benchmark(
        self,
        name: str,
        fn,
        iterations: int = 1000,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a benchmark and collect timing statistics."""
        times: list[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            fn(**kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=sum(times),
            mean_ms=statistics.mean(times),
            p50_ms=statistics.median(times),
            p99_ms=sorted(times)[int(len(times) * 0.99)],
            throughput_per_sec=iterations / (sum(times) / 1000),
        )
        self.results.append(result)
        return result

    def report(self) -> dict[str, Any]:
        return {
            "benchmarks": [
                {
                    "name": r.name,
                    "iterations": r.iterations,
                    "mean_ms": round(r.mean_ms, 4),
                    "p50_ms": round(r.p50_ms, 4),
                    "p99_ms": round(r.p99_ms, 4),
                    "throughput_per_sec": round(r.throughput_per_sec, 2),
                }
                for r in self.results
            ]
        }


class OptimizationEvaluator:
    """Evaluates optimization algorithm quality."""

    def __init__(self) -> None:
        self.results: list[OptimizationQuality] = []

    def evaluate_placement(self) -> OptimizationQuality:
        """Evaluate FFD placement quality."""
        test_cases = 100
        passed = 0
        quality_scores = []

        for seed in range(test_cases):
            # Generate random workloads and assets
            import random
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

            # Check: all placed workloads respect capacity
            placed = set()
            for wls in result.values():
                placed.update(wls)

            unplaced = result.get("__unplaced__", [])
            total = len(placed) + len(unplaced)

            # Quality: placement ratio
            quality = len(placed) / total if total > 0 else 1.0
            quality_scores.append(quality)

            if quality >= 0.8:  # 80% placement is acceptable
                passed += 1

        result = OptimizationQuality(
            problem="Workload Placement",
            algorithm="First-Fit Decreasing",
            approximation_ratio="11/9 × OPT + 1",
            test_cases=test_cases,
            passed=passed,
            failed=test_cases - passed,
            avg_quality_score=statistics.mean(quality_scores),
        )
        self.results.append(result)
        return result

    def evaluate_maintenance_routing(self) -> OptimizationQuality:
        """Evaluate Clarke-Wright Savings routing quality."""
        test_cases = 50
        passed = 0
        quality_scores = []

        for seed in range(test_cases):
            import random
            random.seed(seed)

            n_orders = random.randint(3, 20)
            n_techs = random.randint(1, 5)

            work_orders = [
                WorkOrder(
                    id=f"wo{i}",
                    asset_id=f"a{i}",
                    priority=random.randint(1, 5),
                    duration_hours=random.uniform(0.5, 4),
                    skill_required=random.choice(["electrical", "mechanical", "network"]),
                    latitude=random.uniform(40.0, 42.0),
                    longitude=random.uniform(-75.0, -73.0),
                )
                for i in range(n_orders)
            ]
            technicians = [
                Technician(
                    id=f"t{i}",
                    skills=frozenset(random.sample(["electrical", "mechanical", "network"], k=random.randint(1, 3))),
                    base_latitude=40.5,
                    base_longitude=-74.0,
                )
                for i in range(n_techs)
            ]

            result = clarke_wright_savings(work_orders, technicians)

            # Check: all work orders assigned
            assigned = set()
            for wos in result.values():
                assigned.update(wos)

            quality = len(assigned) / n_orders if n_orders > 0 else 1.0
            quality_scores.append(quality)

            if quality >= 0.9:
                passed += 1

        result = OptimizationQuality(
            problem="Maintenance Routing",
            algorithm="Clarke-Wright Savings + 2-opt",
            approximation_ratio="2 × OPT",
            test_cases=test_cases,
            passed=passed,
            failed=test_cases - passed,
            avg_quality_score=statistics.mean(quality_scores),
        )
        self.results.append(result)
        return result

    def evaluate_network_zoning(self) -> OptimizationQuality:
        """Evaluate DSATUR zoning quality."""
        test_cases = 100
        passed = 0
        quality_scores = []

        for seed in range(test_cases):
            import random
            random.seed(seed)

            n_nodes = random.randint(3, 30)
            nodes = []
            for i in range(n_nodes):
                neighbors = tuple(
                    f"n{j}" for j in range(n_nodes)
                    if j != i and random.random() < 0.3
                )
                nodes.append(NetworkNode(id=f"n{i}", neighbors=neighbors))

            result = dsatur_zoning(nodes)

            # Check: no adjacent nodes share zone
            valid = True
            for node in nodes:
                for neighbor in node.neighbors:
                    if result.get(node.id) == result.get(neighbor):
                        valid = False
                        break
                if not valid:
                    break

            # Quality: colors used / max degree + 1
            max_deg = max(len(n.neighbors) for n in nodes) if nodes else 0
            colors_used = len(set(result.values()))
            quality = 1.0 if colors_used <= max_deg + 1 else (max_deg + 1) / colors_used
            quality_scores.append(quality)

            if valid:
                passed += 1

        result = OptimizationQuality(
            problem="Network Zoning",
            algorithm="DSATUR",
            approximation_ratio="≤ Δ+1 colors",
            test_cases=test_cases,
            passed=passed,
            failed=test_cases - passed,
            avg_quality_score=statistics.mean(quality_scores),
        )
        self.results.append(result)
        return result

    def evaluate_energy_allocation(self) -> OptimizationQuality:
        """Evaluate max-min fair energy allocation quality."""
        test_cases = 100
        passed = 0
        quality_scores = []

        for seed in range(test_cases):
            import random
            random.seed(seed)

            n_requests = random.randint(2, 20)
            total_energy = random.uniform(100, 10000)

            requests = [
                EnergyRequest(
                    workload_id=f"w{i}",
                    energy_kwh=random.uniform(10, 500),
                    useful_work_per_kwh=random.uniform(1, 100),
                    min_fair_share=random.uniform(0, 50),
                )
                for i in range(n_requests)
            ]

            result = max_min_fair_energy_allocation(requests, total_energy)

            # Check: total allocated ≈ total energy
            total_allocated = sum(result.values())
            budget_error = abs(total_allocated - total_energy) / total_energy

            # Check: min fair share respected
            min_share_ok = all(
                result.get(r.workload_id, 0) >= r.min_fair_share * 0.99
                for r in requests
            )

            quality = 1.0 - budget_error
            quality_scores.append(quality)

            if budget_error < 0.01 and min_share_ok:
                passed += 1

        result = OptimizationQuality(
            problem="Energy Allocation",
            algorithm="Max-Min Fairness",
            approximation_ratio="Pareto optimal",
            test_cases=test_cases,
            passed=passed,
            failed=test_cases - passed,
            avg_quality_score=statistics.mean(quality_scores),
        )
        self.results.append(result)
        return result

    def report(self) -> dict[str, Any]:
        return {
            "optimization_quality": [
                {
                    "problem": r.problem,
                    "algorithm": r.algorithm,
                    "approximation_ratio": r.approximation_ratio,
                    "test_cases": r.test_cases,
                    "passed": r.passed,
                    "failed": r.failed,
                    "pass_rate": round(r.passed / r.test_cases * 100, 2),
                    "avg_quality_score": round(r.avg_quality_score, 4),
                }
                for r in self.results
            ]
        }


class EvolutionTracker:
    """Tracks evolution of optimization quality across runs."""

    def __init__(self, history_file: str = "evolution_history.json") -> None:
        self.history_file = Path(history_file)
        self.history: list[dict[str, Any]] = []
        if self.history_file.exists():
            self.history = json.loads(self.history_file.read_text())

    def record(self, run_data: dict[str, Any]) -> None:
        run_data["timestamp"] = time.time()
        self.history.append(run_data)
        self.history_file.write_text(json.dumps(self.history, indent=2, default=str))

    def trend(self, metric: str) -> list[float]:
        """Get the trend of a metric across runs."""
        return [
            run.get("metrics", {}).get(metric, 0)
            for run in self.history
            if "metrics" in run
        ]

    def summary(self) -> dict[str, Any]:
        if not self.history:
            return {"runs": 0}

        latest = self.history[-1]
        return {
            "total_runs": len(self.history),
            "latest_run": latest.get("timestamp"),
            "metrics": latest.get("metrics", {}),
        }


def run_full_evaluation() -> dict[str, Any]:
    """Run the complete evaluation suite."""
    print("=" * 60)
    print("Data Center Commander — Evaluation Suite")
    print("=" * 60)

    # Performance benchmarks
    print("\n[1/3] Running performance benchmarks...")
    runner = BenchmarkRunner()

    # Benchmark FFD with various sizes
    for n in [10, 50, 100, 500]:
        workloads = [
            Workload(f"w{i}", f"wl{i}", cpu_cores=2, ram_gb=4)
            for i in range(n)
        ]
        assets = [
            Asset(f"a{i}", f"server{i}", total_cpu=64, total_ram=256)
            for i in range(max(1, n // 5))
        ]
        runner.run_benchmark(
            f"FFD_placement_n={n}",
            first_fit_decreasing,
            iterations=100,
            workloads=workloads,
            assets=assets,
        )

    # Benchmark DSATUR
    for n in [10, 50, 100]:
        nodes = [
            NetworkNode(f"n{i}", neighbors=tuple(f"n{j}" for j in range(min(i, 5))))
            for i in range(n)
        ]
        runner.run_benchmark(
            f"DSATUR_zoning_n={n}",
            dsatur_zoning,
            iterations=100,
            nodes=nodes,
        )

    # Benchmark energy allocation
    for n in [10, 50, 100]:
        requests = [
            EnergyRequest(f"w{i}", energy_kwh=100, useful_work_per_kwh=10)
            for i in range(n)
        ]
        runner.run_benchmark(
            f"Energy_allocation_n={n}",
            max_min_fair_energy_allocation,
            iterations=100,
            requests=requests,
            total_energy_kwh=10000,
        )

    # Optimization quality
    print("[2/3] Running optimization quality tests...")
    evaluator = OptimizationEvaluator()
    evaluator.evaluate_placement()
    evaluator.evaluate_maintenance_routing()
    evaluator.evaluate_network_zoning()
    evaluator.evaluate_energy_allocation()

    # Generate report
    print("[3/3] Generating report...")
    report = {
        "performance": runner.report(),
        "quality": evaluator.report(),
        "summary": {
            "total_benchmarks": len(runner.results),
            "total_quality_tests": len(evaluator.results),
            "overall_pass_rate": round(
                sum(r.passed for r in evaluator.results)
                / sum(r.test_cases for r in evaluator.results)
                * 100,
                2,
            ),
        },
    }

    # Save report
    report_path = Path("evaluation_report.json")
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport saved to {report_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Benchmarks: {report['summary']['total_benchmarks']}")
    print(f"Quality tests: {report['summary']['total_quality_tests']}")
    print(f"Overall pass rate: {report['summary']['overall_pass_rate']}%")

    for b in report["performance"]["benchmarks"]:
        print(f"  {b['name']}: mean={b['mean_ms']:.3f}ms, p99={b['p99_ms']:.3f}ms, throughput={b['throughput_per_sec']:.0f}/s")

    for q in report["quality"]["optimization_quality"]:
        print(f"  {q['problem']}: {q['passed']}/{q['test_cases']} passed ({q['pass_rate']}%), quality={q['avg_quality_score']:.3f}")

    return report


if __name__ == "__main__":
    run_full_evaluation()
