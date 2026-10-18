"""Tests for the main cost optimization engine."""

from dcc.cost_optimization.engine import CostOptimizationEngine
from dcc.cost_optimization.models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    RiskLevel,
    Workload,
)


def _make_catalog():
    return [
        InstanceType(
            name="t3.medium",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=4.0,
            storage_gb=40,
            on_demand_hourly=0.0416,
            reserved_1yr_hourly=0.0262,
            reserved_3yr_hourly=0.0164,
            spot_hourly=0.0125,
        ),
        InstanceType(
            name="m5.large",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=8.0,
            storage_gb=50,
            on_demand_hourly=0.096,
            reserved_1yr_hourly=0.060,
            reserved_3yr_hourly=0.038,
            spot_hourly=0.029,
        ),
        InstanceType(
            name="m5.xlarge",
            provider=CloudProvider.AWS,
            vcpus=4,
            memory_gb=16.0,
            storage_gb=100,
            on_demand_hourly=0.192,
            reserved_1yr_hourly=0.120,
            reserved_3yr_hourly=0.076,
            spot_hourly=0.058,
        ),
        InstanceType(
            name="m6i.large",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=8.0,
            storage_gb=50,
            on_demand_hourly=0.086,
            reserved_1yr_hourly=0.054,
            reserved_3yr_hourly=0.034,
            spot_hourly=0.026,
        ),
    ]


def _make_workload(
    wl_id="wl-001",
    name="test-app",
    instance_name="m5.xlarge",
    catalog=None,
    pricing=PricingModel.ON_DEMAND,
    environment="production",
    cpu_avg=0.5,
    mem_avg=0.6,
    region="us-east-1",
    team="engineering",
):
    if catalog is None:
        catalog = _make_catalog()
    instance = next(i for i in catalog if i.name == instance_name)
    return Workload(
        workload_id=wl_id,
        name=name,
        instance_type=instance,
        pricing_model=pricing,
        region=region,
        environment=environment,
        team=team,
        cpu_utilization_avg=cpu_avg,
        memory_utilization_avg=mem_avg,
    )


def test_engine_run_empty():
    engine = CostOptimizationEngine()
    report = engine.run([])
    assert report.total_workloads == 0
    assert report.total_monthly_cost == 0.0
    assert report.total_potential_savings == 0.0


def test_engine_run_single_workload():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    wl = _make_workload()
    report = engine.run([wl])
    assert report.total_workloads == 1
    assert report.total_monthly_cost > 0
    assert report.cost_breakdown is not None
    assert report.cost_breakdown.workload_count == 1


def test_engine_run_multiple_workloads():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", instance_name="m5.xlarge"),
        _make_workload("wl-002", "app2", instance_name="m5.large", environment="dev", cpu_avg=0.15, mem_avg=0.20),
        _make_workload("wl-003", "app3", instance_name="m5.xlarge", environment="staging"),
    ]
    report = engine.run(workloads)
    assert report.total_workloads == 3
    assert report.total_monthly_cost > 0
    assert report.generated_at != ""


def test_engine_risk_summary():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", environment="dev", cpu_avg=0.15, mem_avg=0.20),
        _make_workload("wl-002", "app2", environment="production"),
    ]
    report = engine.run(workloads)
    assert "low" in report.risk_summary
    assert "medium" in report.risk_summary
    assert "high" in report.risk_summary


def test_engine_quick_wins():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", environment="dev", cpu_avg=0.10, mem_avg=0.15),
    ]
    report = engine.run(workloads)
    # Should have at least some quick wins for dev workloads
    assert isinstance(report.quick_wins, list)


def test_engine_long_term_recommendations():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", instance_name="m5.xlarge", environment="dev", cpu_avg=0.10, mem_avg=0.15),
        _make_workload("wl-002", "app2", instance_name="m5.xlarge", environment="dev", cpu_avg=0.12, mem_avg=0.18),
    ]
    report = engine.run(workloads)
    assert isinstance(report.long_term_recommendations, list)


def test_engine_savings_percent():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", environment="dev", cpu_avg=0.10, mem_avg=0.15),
    ]
    report = engine.run(workloads)
    if report.total_monthly_cost > 0:
        assert report.savings_percent >= 0


def test_engine_cost_breakdown():
    catalog = _make_catalog()
    engine = CostOptimizationEngine(catalog)
    workloads = [
        _make_workload("wl-001", "app1", region="us-east-1", team="engineering"),
        _make_workload("wl-002", "app2", region="us-west-2", team="data"),
    ]
    report = engine.run(workloads)
    cb = report.cost_breakdown
    assert cb is not None
    assert cb.total_monthly > 0
    assert "us-east-1" in cb.by_region
    assert "us-west-2" in cb.by_region
    assert "engineering" in cb.by_team
    assert "data" in cb.by_team
