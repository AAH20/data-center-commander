"""Tests for the cloud cost analyzer."""

from dcc.cost_optimization.cloud_cost_analyzer import CloudCostAnalyzer
from dcc.cost_optimization.models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    Workload,
)


def _make_instance(name="m5.xlarge", provider=CloudProvider.AWS):
    return InstanceType(
        name=name,
        provider=provider,
        vcpus=4,
        memory_gb=16.0,
        storage_gb=100,
        on_demand_hourly=0.192,
        reserved_1yr_hourly=0.120,
        reserved_3yr_hourly=0.080,
        spot_hourly=0.058,
    )


def _make_workload(
    wl_id="wl-001",
    name="test-app",
    instance=None,
    pricing=PricingModel.ON_DEMAND,
    region="us-east-1",
    team="engineering",
    environment="production",
    cpu_avg=0.5,
    mem_avg=0.6,
    cpu_p95=None,
    mem_p95=None,
):
    if instance is None:
        instance = _make_instance()
    return Workload(
        workload_id=wl_id,
        name=name,
        instance_type=instance,
        pricing_model=pricing,
        region=region,
        team=team,
        environment=environment,
        cpu_utilization_avg=cpu_avg,
        memory_utilization_avg=mem_avg,
        cpu_utilization_p95=cpu_p95 if cpu_p95 is not None else cpu_avg,
        memory_utilization_p95=mem_p95 if mem_p95 is not None else mem_avg,
    )


def test_analyze_empty():
    analyzer = CloudCostAnalyzer()
    result = analyzer.analyze([])
    assert result.total_monthly == 0.0
    assert result.workload_count == 0


def test_analyze_single_workload():
    analyzer = CloudCostAnalyzer()
    wl = _make_workload()
    result = analyzer.analyze([wl])
    assert result.total_monthly == wl.monthly_cost
    assert result.workload_count == 1
    assert result.by_provider["aws"] == wl.monthly_cost
    assert result.by_region["us-east-1"] == wl.monthly_cost
    assert result.by_team["engineering"] == wl.monthly_cost
    assert result.by_environment["production"] == wl.monthly_cost


def test_analyze_multiple_workloads():
    analyzer = CloudCostAnalyzer()
    wl1 = _make_workload("wl-001", "app1")
    wl2 = _make_workload("wl-002", "app2", region="us-west-2")
    result = analyzer.analyze([wl1, wl2])
    assert result.total_monthly == wl1.monthly_cost + wl2.monthly_cost
    assert result.workload_count == 2
    assert "us-east-1" in result.by_region
    assert "us-west-2" in result.by_region


def test_top_spenders():
    analyzer = CloudCostAnalyzer()
    wl1 = _make_workload("wl-001", "cheap")
    wl2 = _make_workload(
        "wl-002", "expensive",
        instance=_make_instance("m5.4xlarge"),
    )
    # Make wl2 more expensive
    wl2.instance_type = InstanceType(
        name="m5.4xlarge",
        provider=CloudProvider.AWS,
        vcpus=16,
        memory_gb=64.0,
        storage_gb=500,
        on_demand_hourly=0.768,
        reserved_1yr_hourly=0.480,
        reserved_3yr_hourly=0.320,
        spot_hourly=0.230,
    )
    wl2.monthly_cost = 0.768 * 730
    result = analyzer.top_spenders([wl1, wl2], n=1)
    assert len(result) == 1
    assert result[0].workload_id == "wl-002"


def test_idle_workloads():
    analyzer = CloudCostAnalyzer()
    idle = _make_workload("wl-001", "idle", cpu_avg=0.02, mem_avg=0.05)
    active = _make_workload("wl-002", "active", cpu_avg=0.5, mem_avg=0.6)
    result = analyzer.idle_workloads([idle, active])
    assert len(result) == 1
    assert result[0].workload_id == "wl-001"


def test_underutilized_workloads():
    analyzer = CloudCostAnalyzer()
    under = _make_workload("wl-001", "under", cpu_avg=0.15, mem_avg=0.20)
    normal = _make_workload("wl-002", "normal", cpu_avg=0.5, mem_avg=0.6)
    result = analyzer.underutilized_workloads([under, normal])
    assert len(result) == 1
    assert result[0].workload_id == "wl-001"


def test_overutilized_workloads():
    analyzer = CloudCostAnalyzer()
    over = _make_workload("wl-001", "over", cpu_avg=0.85, mem_avg=0.90, cpu_p95=0.90, mem_p95=0.95)
    normal = _make_workload("wl-002", "normal", cpu_avg=0.5, mem_avg=0.6)
    result = analyzer.overutilized_workloads([over, normal])
    assert len(result) == 1
    assert result[0].workload_id == "wl-001"


def test_cost_trend():
    analyzer = CloudCostAnalyzer()
    current = [_make_workload("wl-001", "app1")]
    previous = [_make_workload("wl-001", "app1")]
    # Make current more expensive
    current[0].monthly_cost = 200.0
    previous[0].monthly_cost = 100.0
    result = analyzer.cost_trend(current, previous)
    assert result["current_monthly"] == 200.0
    assert result["previous_monthly"] == 100.0
    assert result["delta"] == 100.0
    assert result["percent_change"] == 100.0


def test_provider_distribution():
    analyzer = CloudCostAnalyzer()
    aws_wl = _make_workload("wl-001", "aws-app")
    gcp_instance = _make_instance("n1-standard-4", CloudProvider.GCP)
    gcp_wl = _make_workload("wl-002", "gcp-app", instance=gcp_instance)
    result = analyzer.provider_distribution([aws_wl, gcp_wl])
    assert "aws" in result
    assert "gcp" in result
    assert abs(sum(result.values()) - 100.0) < 0.01
