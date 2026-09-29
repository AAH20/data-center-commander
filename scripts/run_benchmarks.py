#!/usr/bin/env python3
"""Benchmark runner for Data Center Commander computational modules.

Measures execution time of core pure-Python operations and outputs JSON
results suitable for regression detection in CI.

Usage:
    PYTHONPATH=src python scripts/run_benchmarks.py [--output PATH] [--iterations N]

Output format:
    {
        "timestamp": "ISO8601",
        "python_version": "3.11.x",
        "platform": "Linux-...",
        "iterations": 5,
        "benchmarks": {
            "tco.evaluate_tco": {
                "mean_seconds": 0.00123,
                "std_seconds": 0.00004,
                "min_seconds": 0.00118,
                "max_seconds": 0.00129,
                "samples": [...]
            },
            ...
        }
    }
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------


def run_benchmark(
    name: str,
    fn: Callable[[], Any],
    iterations: int = 5,
    warmup: int = 1,
) -> dict[str, Any]:
    """Run a benchmark function and return timing statistics."""
    # Warmup
    for _ in range(warmup):
        fn()

    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        end = time.perf_counter()
        samples.append(end - start)

    return {
        "mean_seconds": round(statistics.mean(samples), 8),
        "std_seconds": round(statistics.stdev(samples), 8) if len(samples) > 1 else 0.0,
        "min_seconds": round(min(samples), 8),
        "max_seconds": round(max(samples), 8),
        "samples": [round(s, 8) for s in samples],
    }


# ---------------------------------------------------------------------------
# Benchmark fixtures
# ---------------------------------------------------------------------------


def _make_tco_scenario():
    """Create a TCO scenario for benchmarking."""
    from dcc.economics.tco import TCOAssumptions, TCOCostBreakdown, TCOScenario

    return TCOScenario(
        name="benchmark-tco",
        description="Benchmark scenario",
        scenario_type="on-prem",
        costs=TCOCostBreakdown(
            hardware_capex=500_000,
            facility_capex=200_000,
            design_capex=50_000,
            commissioning_capex=25_000,
            migration_capex=30_000,
            software_capex=40_000,
            energy_annual=120_000,
            maintenance_annual=60_000,
            labor_annual=80_000,
            network_annual=24_000,
            software_annual=36_000,
            insurance_annual=12_000,
            tax_annual=8_000,
            other_annual=10_000,
            refresh_cost=100_000,
            refresh_interval_years=5,
            decommission_cost=20_000,
            residual_value=50_000,
        ),
        assumptions=TCOAssumptions(
            currency="USD",
            horizon_years=10,
            annual_discount_rate=0.08,
            energy_escalation_pct=0.03,
            maintenance_escalation_pct=0.025,
            labor_escalation_pct=0.03,
            other_escalation_pct=0.02,
            contingency_pct=0.05,
            tax_rate=0.21,
            include_tax=False,
        ),
        it_capacity_kw=500,
        rack_count=50,
        area_m2=500,
        annual_energy_kwh=4_380_000,
    )


def _make_deployment_scenario():
    """Create a deployment scenario for benchmarking."""
    from dcc.economics.scenarios import (
        CostBreakdown,
        DeploymentScenario,
        ScenarioAssumptions,
    )

    return DeploymentScenario(
        name="benchmark-scenario",
        description="Benchmark deployment scenario",
        scenario_type="on-prem",
        costs=CostBreakdown(
            capex=300_000,
            site=100_000,
            migration=50_000,
            power_monthly=10_000,
            software_monthly=3_000,
            maintenance_monthly=5_000,
            labor_monthly=6_000,
            network_monthly=2_000,
            insurance_monthly=1_000,
            tax_monthly=500,
            other_monthly=1_000,
            refresh_cost=80_000,
            refresh_month=36,
            decommission_cost=15_000,
            residual_value=30_000,
        ),
        assumptions=ScenarioAssumptions(
            currency="USD",
            horizon_months=36,
            annual_discount_rate=0.08,
            useful_units_per_month=10_000,
            useful_unit_name="requests",
            demand_profile="steady",
        ),
    )


def _make_capacity_points(n: int = 90) -> list:
    """Create capacity data points for benchmarking."""
    from dcc.forecasting.capacity import CapacityDataPoint

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = []
    for i in range(n):
        usable = 1000 + i * 5
        reserved = 600 + i * 3
        policy_reserve = 100
        points.append(
            CapacityDataPoint(
                observed_at=base + timedelta(days=i),
                usable=usable,
                reserved=reserved,
                policy_reserve=policy_reserve,
                forecast_peak=None,
                quality_status="good",
                scenario="baseline",
            )
        )
    return points


def _make_telemetry_series(n: int = 1000) -> list[float]:
    """Create a synthetic telemetry series."""
    import random

    random.seed(42)
    return [random.gauss(100, 15) for _ in range(n)]


def _make_time_series(n: int = 500):
    """Create a time series for interval benchmarking."""
    from dcc.validation.intervals import DataPoint, TimeSeries

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = [
        DataPoint(timestamp=base + timedelta(minutes=5 * i), value=100 + i * 0.1)
        for i in range(n)
    ]
    return TimeSeries(name="benchmark", interval=300, points=points)


# ---------------------------------------------------------------------------
# Benchmark definitions
# ---------------------------------------------------------------------------


def benchmark_tco() -> dict[str, Any]:
    """Benchmark TCO evaluation."""
    from dcc.economics.tco import evaluate_tco

    scenario = _make_tco_scenario()
    return run_benchmark("tco.evaluate_tco", lambda: evaluate_tco(scenario))


def benchmark_tco_compare() -> dict[str, Any]:
    """Benchmark TCO comparison."""
    from dcc.economics.tco import compare_tco

    s1 = _make_tco_scenario()
    s2 = _make_tco_scenario()
    s2.name = "benchmark-tco-2"
    s2.costs = s2.costs.__class__(
        **{**s2.costs.__dict__, "hardware_capex": 600_000}
    )
    return run_benchmark("tco.compare_tco", lambda: compare_tco([s1, s2]))


def benchmark_scenario() -> dict[str, Any]:
    """Benchmark deployment scenario evaluation."""
    from dcc.economics.scenarios import evaluate_scenario

    scenario = _make_deployment_scenario()
    return run_benchmark("scenarios.evaluate_scenario", lambda: evaluate_scenario(scenario))


def benchmark_scenario_compare() -> dict[str, Any]:
    """Benchmark scenario comparison."""
    from dcc.economics.scenarios import compare_scenarios

    s1 = _make_deployment_scenario()
    s2 = _make_deployment_scenario()
    s2.name = "benchmark-scenario-2"
    return run_benchmark("scenarios.compare_scenarios", lambda: compare_scenarios([s1, s2]))


def benchmark_capacity_forecast() -> dict[str, Any]:
    """Benchmark capacity forecasting."""
    from dcc.forecasting.capacity import forecast_capacity

    points = _make_capacity_points(90)
    return run_benchmark(
        "capacity.forecast_capacity",
        lambda: forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=30,
            method="linear",
        ),
    )


def benchmark_capacity_at_risk() -> dict[str, Any]:
    """Benchmark capacity-at-risk computation."""
    from dcc.forecasting.capacity import compute_capacity_at_risk

    points = _make_capacity_points(90)
    return run_benchmark(
        "capacity.compute_capacity_at_risk",
        lambda: compute_capacity_at_risk(points, "power_kw", 0.95),
    )


def benchmark_quality_score() -> dict[str, Any]:
    """Benchmark quality scoring."""
    from dcc.forecasting.capacity import CapacityDataPoint
    from dcc.quality.engine import QualityEngine

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        {
            "id": f"rec-{i}",
            "value": 100 + i,
            "timestamp": (base + timedelta(hours=i)).isoformat(),
            "status": "ok",
        }
        for i in range(200)
    ]
    engine = QualityEngine()
    return run_benchmark(
        "quality.score_source",
        lambda: engine.score_source("benchmark-source", records),
    )


def benchmark_anomaly_detection() -> dict[str, Any]:
    """Benchmark anomaly detection."""
    from dcc.quality.anomaly import zscore_detect

    values = _make_telemetry_series(1000)
    return run_benchmark(
        "anomaly.zscore_detect",
        lambda: zscore_detect(values, threshold=3.0),
    )


def benchmark_anomaly_iqr() -> dict[str, Any]:
    """Benchmark IQR anomaly detection."""
    from dcc.quality.anomaly import iqr_detect

    values = _make_telemetry_series(1000)
    return run_benchmark(
        "anomaly.iqr_detect",
        lambda: iqr_detect(values),
    )


def benchmark_backtest_walk_forward() -> dict[str, Any]:
    """Benchmark walk-forward backtesting."""
    from dcc.forecasting.backtest import walk_forward

    values = _make_telemetry_series(200)
    return run_benchmark(
        "backtest.walk_forward",
        lambda: walk_forward(values, min_train_size=50, step_size=10, horizon=5),
    )


def benchmark_backtest_cross_validate() -> dict[str, Any]:
    """Benchmark cross-validation backtesting."""
    from dcc.forecasting.backtest import cross_validate

    values = _make_telemetry_series(200)
    return run_benchmark(
        "backtest.cross_validate",
        lambda: cross_validate(values, n_splits=5, gap=2, horizon=5),
    )


def benchmark_drift_detection() -> dict[str, Any]:
    """Benchmark drift detection."""
    from dcc.forecasting.drift import DriftDetector

    reference = _make_telemetry_series(500)
    incoming = _make_telemetry_series(200)
    detector = DriftDetector()
    detector.set_reference(reference)
    return run_benchmark(
        "drift.detect",
        lambda: detector.detect(incoming),
    )


def benchmark_cost_allocation() -> dict[str, Any]:
    """Benchmark cost allocation."""
    from decimal import Decimal
    from dcc.economics.allocation import WorkloadShare, allocate_cost

    shares = [
        WorkloadShare(workload_id=f"wl-{i}", share_value=Decimal(str(100 + i)))
        for i in range(20)
    ]
    return run_benchmark(
        "allocation.allocate_cost",
        lambda: allocate_cost(
            total_amount=Decimal("100000"),
            currency="USD",
            workload_ids=[s.workload_id for s in shares],
            shares=shares,
            method="measured_usage",
        ),
    )


def benchmark_consistency_validation() -> dict[str, Any]:
    """Benchmark consistency validation."""
    from dcc.validation.consistency import reconcile_energy_sources

    rows_a = [
        {"source": "utility", "observed_at": f"2026-01-{i+1:02d}T00:00:00Z", "kwh": 1000 + i * 10}
        for i in range(50)
    ]
    rows_b = [
        {"source": "bms", "observed_at": f"2026-01-{i+1:02d}T00:00:00Z", "kwh": 1000 + i * 10}
        for i in range(50)
    ]
    return run_benchmark(
        "consistency.reconcile_energy_sources",
        lambda: reconcile_energy_sources(rows_a, rows_b),
    )


def benchmark_interval_alignment() -> dict[str, Any]:
    """Benchmark interval alignment."""
    from dcc.validation.intervals import align_series

    ts = _make_time_series(500)
    return run_benchmark(
        "intervals.align_series",
        lambda: align_series([ts], target_interval=900),
    )


def benchmark_interval_resample() -> dict[str, Any]:
    """Benchmark interval resampling."""
    from dcc.validation.intervals import resample

    ts = _make_time_series(500)
    return run_benchmark(
        "intervals.resample",
        lambda: resample(ts, target_interval=900, aggregation="mean"),
    )


def benchmark_failure_prediction() -> dict[str, Any]:
    """Benchmark failure prediction."""
    from dcc.forecasting.failure import predict_equipment_failures

    telemetry = {
        "temp": _make_telemetry_series(200),
        "vibration": _make_telemetry_series(200),
        "power": _make_telemetry_series(200),
    }
    return run_benchmark(
        "failure.predict_equipment_failures",
        lambda: predict_equipment_failures(
            asset_id="asset-001",
            telemetry_series=telemetry,
        ),
    )


def benchmark_feature_extraction() -> dict[str, Any]:
    """Benchmark feature extraction."""
    from dcc.forecasting.features import extract_features

    values = _make_telemetry_series(500)
    return run_benchmark(
        "features.extract_features",
        lambda: extract_features(values),
    )


def benchmark_load_forecast() -> dict[str, Any]:
    """Benchmark load forecasting."""
    from dcc.forecasting.load import LoadForecaster

    values = _make_telemetry_series(300)
    forecaster = LoadForecaster(window=24)
    return run_benchmark(
        "load.forecast",
        lambda: forecaster.forecast(values, horizon=24),
    )


def benchmark_maintenance_optimization() -> dict[str, Any]:
    """Benchmark maintenance window optimization."""
    from dcc.forecasting.maintenance import optimize_maintenance_windows

    load_profile = _make_telemetry_series(168)  # One week hourly
    return run_benchmark(
        "maintenance.optimize_maintenance_windows",
        lambda: optimize_maintenance_windows(
            load_profile=load_profile,
            min_window_hours=4,
            max_windows=3,
        ),
    )


def benchmark_price_forecast() -> dict[str, Any]:
    """Benchmark price forecasting."""
    from dcc.forecasting.price import forecast_prices

    historical = [
        {"observed_at": f"2026-01-{i+1:02d}T00:00:00Z", "price": 0.10 + (i % 7) * 0.01}
        for i in range(90)
    ]
    return run_benchmark(
        "price.forecast_prices",
        lambda: forecast_prices(historical, horizon_days=30),
    )


def benchmark_budget_forecast() -> dict[str, Any]:
    """Benchmark budget forecasting."""
    from dcc.economics.budget import forecast_budget

    line_items = [
        {
            "category": "energy",
            "monthly_amount": "10000",
            "escalation_pct": "0.03",
            "start_month": 1,
            "end_month": 36,
        }
        for _ in range(20)
    ]
    return run_benchmark(
        "budget.forecast_budget",
        lambda: forecast_budget(
            line_items=line_items,
            horizon_months=36,
            discount_rate=0.08,
        ),
    )


def benchmark_estimate_sizing() -> dict[str, Any]:
    """Benchmark estimate sizing."""
    from dcc.economics.estimates import DeploymentEstimator

    estimator = DeploymentEstimator()
    return run_benchmark(
        "estimates.size_electrical",
        lambda: estimator.size_electrical(
            it_load_kw=500,
            redundancy="N+1",
            pue=1.5,
        ),
    )


def benchmark_reconciliation() -> dict[str, Any]:
    """Benchmark estimate reconciliation."""
    from dcc.economics.reconciliation import reconcile_estimate

    estimate_lines = [
        {
            "phase": "design",
            "category": "electrical",
            "estimated_amount": "50000",
        }
        for _ in range(30)
    ]
    actuals = [
        {
            "phase": "design",
            "category": "electrical",
            "actual_amount": str(48000 + i * 100),
        }
        for i in range(30)
    ]
    return run_benchmark(
        "reconciliation.reconcile_estimate",
        lambda: reconcile_estimate(estimate_lines, actuals),
    )


def benchmark_unit_economics() -> dict[str, Any]:
    """Benchmark unit economics calculations."""
    from dcc.economics.unit import compute_all_unit_economics

    return run_benchmark(
        "unit.compute_all_unit_economics",
        lambda: compute_all_unit_economics(
            total_cost=1_000_000,
            currency="USD",
            annual_energy_kwh=4_380_000,
            it_capacity_kw=500,
            rack_count=50,
            area_m2=500,
            annual_work_units=120_000,
        ),
    )


def benchmark_seasonal_decompose() -> dict[str, Any]:
    """Benchmark seasonal decomposition."""
    from dcc.quality.anomaly import seasonal_decompose_detect

    values = _make_telemetry_series(500)
    return run_benchmark(
        "anomaly.seasonal_decompose_detect",
        lambda: seasonal_decompose_detect(values, period=24),
    )


def benchmark_calibration() -> dict[str, Any]:
    """Benchmark forecast calibration."""
    from dcc.forecasting.calibration import calibrate_forecasts

    pairs = [
        {"forecast": 100 + i, "actual": 100 + i + (i % 5) - 2}
        for i in range(200)
    ]
    return run_benchmark(
        "calibration.calibrate_forecasts",
        lambda: calibrate_forecasts(pairs),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DCC benchmarks")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".benchmarks/results.json"),
        help="Output path for benchmark results",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations per benchmark",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup runs per benchmark",
    )
    args = parser.parse_args()

    benchmark_fns = [
        benchmark_tco,
        benchmark_tco_compare,
        benchmark_scenario,
        benchmark_scenario_compare,
        benchmark_capacity_forecast,
        benchmark_capacity_at_risk,
        benchmark_quality_score,
        benchmark_anomaly_detection,
        benchmark_anomaly_iqr,
        benchmark_seasonal_decompose,
        benchmark_backtest_walk_forward,
        benchmark_backtest_cross_validate,
        benchmark_drift_detection,
        benchmark_cost_allocation,
        benchmark_consistency_validation,
        benchmark_interval_alignment,
        benchmark_interval_resample,
        benchmark_failure_prediction,
        benchmark_feature_extraction,
        benchmark_load_forecast,
        benchmark_maintenance_optimization,
        benchmark_price_forecast,
        benchmark_budget_forecast,
        benchmark_estimate_sizing,
        benchmark_reconciliation,
        benchmark_unit_economics,
        benchmark_calibration,
    ]

    results: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "iterations": args.iterations,
        "benchmarks": {},
    }

    print(f"Running {len(benchmark_fns)} benchmarks ({args.iterations} iterations each)...")
    print()

    for fn in benchmark_fns:
        name = fn.__name__.replace("benchmark_", "")
        try:
            result = run_benchmark(
                name,
                fn,
                iterations=args.iterations,
                warmup=args.warmup,
            )
            results["benchmarks"][name] = result
            print(f"  {name:45s}  mean={result['mean_seconds']:.6f}s  std={result['std_seconds']:.6f}s")
        except Exception as e:
            print(f"  {name:45s}  ERROR: {e}")
            results["benchmarks"][name] = {"error": str(e)}

    # Write results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print()
    print(f"Results written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
