"""Tests for the cost optimization engine models."""

from dcc.cost_optimization.models import (
    CloudProvider,
    CostBreakdown,
    InstanceType,
    OptimizationReport,
    PricingModel,
    ReservedInstancePlan,
    RightsizingRecommendation,
    RiskLevel,
    SpotInstanceStrategy,
    Workload,
)


def test_instance_type_monthly_costs():
    it = InstanceType(
        name="m5.xlarge",
        provider=CloudProvider.AWS,
        vcpus=4,
        memory_gb=16.0,
        storage_gb=100,
        on_demand_hourly=0.192,
        reserved_1yr_hourly=0.120,
        reserved_3yr_hourly=0.080,
        spot_hourly=0.058,
    )
    assert it.on_demand_monthly == 0.192 * 730
    assert it.reserved_1yr_monthly == 0.120 * 730
    assert it.reserved_3yr_monthly == 0.080 * 730
    assert it.spot_monthly == 0.058 * 730


def test_instance_type_vcpu_memory_ratio():
    it = InstanceType(
        name="m5.xlarge",
        provider=CloudProvider.AWS,
        vcpus=4,
        memory_gb=16.0,
        storage_gb=100,
        on_demand_hourly=0.192,
        reserved_1yr_hourly=0.120,
        reserved_3yr_hourly=0.080,
        spot_hourly=0.058,
    )
    assert it.vcpu_to_memory_ratio == 0.25


def test_workload_monthly_cost_computed():
    it = InstanceType(
        name="m5.xlarge",
        provider=CloudProvider.AWS,
        vcpus=4,
        memory_gb=16.0,
        storage_gb=100,
        on_demand_hourly=0.192,
        reserved_1yr_hourly=0.120,
        reserved_3yr_hourly=0.080,
        spot_hourly=0.058,
    )
    wl = Workload(
        workload_id="wl-001",
        name="test-app",
        instance_type=it,
        pricing_model=PricingModel.ON_DEMAND,
        region="us-east-1",
    )
    assert wl.monthly_cost == 0.192 * 730


def test_workload_custom_uptime():
    it = InstanceType(
        name="m5.xlarge",
        provider=CloudProvider.AWS,
        vcpus=4,
        memory_gb=16.0,
        storage_gb=100,
        on_demand_hourly=0.192,
        reserved_1yr_hourly=0.120,
        reserved_3yr_hourly=0.080,
        spot_hourly=0.058,
    )
    wl = Workload(
        workload_id="wl-002",
        name="batch-job",
        instance_type=it,
        pricing_model=PricingModel.ON_DEMAND,
        region="us-east-1",
        uptime_hours_monthly=200.0,
    )
    assert wl.monthly_cost == 0.192 * 200


def test_cost_breakdown_defaults():
    cb = CostBreakdown()
    assert cb.total_monthly == 0.0
    assert cb.workload_count == 0
    assert cb.by_provider == {}


def test_optimization_report_defaults():
    report = OptimizationReport()
    assert report.total_workloads == 0
    assert report.total_monthly_cost == 0.0
    assert report.rightsizing_recommendations == []
    assert report.reserved_instance_plans == []
    assert report.spot_strategies == []
