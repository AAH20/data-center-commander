"""Tests for the reserved instance planner."""

import pytest

from dcc.cost_optimization.models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    RiskLevel,
    Workload,
)
from dcc.cost_optimization.reserved_instances import ReservedInstancePlanner


def _make_instance(name="m5.xlarge"):
    return InstanceType(
        name=name,
        provider=CloudProvider.AWS,
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
    environment="production",
    uptime=730.0,
):
    if instance is None:
        instance = _make_instance()
    return Workload(
        workload_id=wl_id,
        name=name,
        instance_type=instance,
        pricing_model=pricing,
        region="us-east-1",
        environment=environment,
        uptime_hours_monthly=uptime,
    )


def test_plan_empty_workloads():
    planner = ReservedInstancePlanner()
    result = planner.plan([])
    assert result == []


def test_plan_on_demand_production_workloads():
    planner = ReservedInstancePlanner()
    workloads = [
        _make_workload("wl-001", "app1"),
        _make_workload("wl-002", "app2"),
    ]
    result = planner.plan(workloads, term_months=12, payment_option="partial_upfront")
    assert len(result) > 0
    assert result[0].quantity == 2
    assert result[0].monthly_savings > 0
    assert result[0].savings_percent > 0


def test_plan_skips_non_on_demand():
    planner = ReservedInstancePlanner()
    workloads = [
        _make_workload("wl-001", "app1", pricing=PricingModel.SPOT),
    ]
    result = planner.plan(workloads)
    assert len(result) == 0


def test_plan_skips_dev_environment():
    planner = ReservedInstancePlanner()
    workloads = [
        _make_workload("wl-001", "app1", environment="dev"),
    ]
    result = planner.plan(workloads)
    assert len(result) == 0


def test_plan_skips_low_uptime():
    planner = ReservedInstancePlanner()
    workloads = [
        _make_workload("wl-001", "app1", uptime=100.0),
    ]
    result = planner.plan(workloads)
    assert len(result) == 0


def test_plan_3yr_term():
    planner = ReservedInstancePlanner()
    workloads = [_make_workload("wl-001", "app1")]
    result = planner.plan(workloads, term_months=36, payment_option="all_upfront")
    assert len(result) > 0
    assert result[0].term_months == 36


def test_plan_all_options():
    planner = ReservedInstancePlanner()
    workloads = [_make_workload("wl-001", "app1")]
    result = planner.plan_all_options(workloads)
    assert "12mo_all_upfront" in result
    assert "12mo_partial_upfront" in result
    assert "12mo_no_upfront" in result
    assert "36mo_all_upfront" in result
    assert "36mo_partial_upfront" in result
    assert "36mo_no_upfront" in result


def test_plan_invalid_term():
    planner = ReservedInstancePlanner()
    with pytest.raises(ValueError):
        planner.plan([], term_months=6)


def test_plan_invalid_payment_option():
    planner = ReservedInstancePlanner()
    with pytest.raises(ValueError):
        planner.plan([], payment_option="invalid")


def test_plan_savings_calculation():
    planner = ReservedInstancePlanner()
    workloads = [_make_workload("wl-001", "app1")]
    result = planner.plan(workloads, term_months=12, payment_option="all_upfront")
    assert len(result) > 0
    plan = result[0]
    assert plan.monthly_savings > 0
    assert plan.annual_savings == plan.monthly_savings * 12
    assert plan.break_even_months > 0
    assert plan.total_upfront > 0


def test_plan_risk_levels():
    planner = ReservedInstancePlanner()
    workloads = [_make_workload("wl-001", "app1")]
    result = planner.plan(workloads)
    assert len(result) > 0
    # m5 is gen 5, 12mo partial should be low or medium risk
    assert result[0].risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
