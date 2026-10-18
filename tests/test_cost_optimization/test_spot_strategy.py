"""Tests for the spot instance planner."""

from dcc.cost_optimization.models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    RiskLevel,
    Workload,
)
from dcc.cost_optimization.spot_strategy import SpotInstancePlanner


def _make_catalog():
    return [
        InstanceType(
            name="m5.xlarge",
            provider=CloudProvider.AWS,
            vcpus=4,
            memory_gb=16.0,
            storage_gb=100,
            on_demand_hourly=0.192,
            reserved_1yr_hourly=0.120,
            reserved_3yr_hourly=0.080,
            spot_hourly=0.058,
        ),
        InstanceType(
            name="m6i.xlarge",
            provider=CloudProvider.AWS,
            vcpus=4,
            memory_gb=16.0,
            storage_gb=100,
            on_demand_hourly=0.172,
            reserved_1yr_hourly=0.108,
            reserved_3yr_hourly=0.068,
            spot_hourly=0.052,
        ),
    ]


def _make_workload(
    wl_id="wl-001",
    name="test-app",
    instance_name="m5.xlarge",
    catalog=None,
    pricing=PricingModel.ON_DEMAND,
    environment="dev",
    cpu_avg=0.5,
):
    if catalog is None:
        catalog = _make_catalog()
    instance = next(i for i in catalog if i.name == instance_name)
    return Workload(
        workload_id=wl_id,
        name=name,
        instance_type=instance,
        pricing_model=pricing,
        region="us-east-1",
        environment=environment,
        cpu_utilization_avg=cpu_avg,
    )


def test_plan_empty_workloads():
    planner = SpotInstancePlanner()
    result = planner.plan([])
    assert result == []


def test_plan_dev_workload():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="dev")
    result = planner.plan([wl])
    assert len(result) > 0
    assert result[0].monthly_savings > 0
    assert result[0].savings_percent > 50  # Spot is typically 60-70% cheaper


def test_plan_skips_already_spot():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(pricing=PricingModel.SPOT, environment="dev")
    result = planner.plan([wl])
    assert len(result) == 0


def test_plan_skips_production_high_utilization():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="production", cpu_avg=0.8)
    result = planner.plan([wl])
    assert len(result) == 0


def test_plan_production_low_utilization():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="production", cpu_avg=0.3)
    result = planner.plan([wl])
    # May or may not recommend depending on interruption probability
    if result:
        assert result[0].risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def test_plan_savings_calculation():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="dev")
    result = planner.plan([wl])
    assert len(result) > 0
    strategy = result[0]
    assert strategy.monthly_savings > 0
    assert strategy.annual_savings == strategy.monthly_savings * 12
    assert strategy.recommended_max_bid > 0
    assert strategy.recommended_max_bid >= strategy.recommended_instance.spot_hourly


def test_plan_diversification_advice():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="dev")
    result = planner.plan([wl])
    assert len(result) > 0
    assert "diversif" in result[0].diversification_recommendation.lower()


def test_plan_fallback_strategy():
    catalog = _make_catalog()
    planner = SpotInstancePlanner(catalog)
    wl = _make_workload(environment="dev")
    result = planner.plan([wl])
    assert len(result) > 0
    assert len(result[0].fallback_strategy) > 0


def test_plan_without_catalog():
    planner = SpotInstancePlanner([])
    wl = _make_workload(environment="dev")
    result = planner.plan([wl])
    # Without catalog, uses current instance for spot pricing
    assert len(result) > 0
