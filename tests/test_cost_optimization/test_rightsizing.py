"""Tests for the rightsizing engine."""

from dcc.cost_optimization.models import (
    CloudProvider,
    InstanceType,
    PricingModel,
    RiskLevel,
    Workload,
)
from dcc.cost_optimization.rightsizing import RightsizingEngine


def _make_catalog():
    """Create a small instance catalog for testing."""
    return [
        InstanceType(
            name="t3.small",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=2.0,
            storage_gb=20,
            on_demand_hourly=0.0208,
            reserved_1yr_hourly=0.0131,
            reserved_3yr_hourly=0.0082,
            spot_hourly=0.0062,
        ),
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
    region="us-east-1",
    environment="production",
    cpu_avg=0.5,
    mem_avg=0.6,
    cpu_p95=0.7,
    mem_p95=0.75,
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
        cpu_utilization_avg=cpu_avg,
        memory_utilization_avg=mem_avg,
        cpu_utilization_p95=cpu_p95,
        memory_utilization_p95=mem_p95,
    )


def test_recommend_downsize():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    # Very underutilized m5.xlarge — should recommend smaller
    wl = _make_workload(
        instance_name="m5.xlarge",
        cpu_avg=0.10,
        mem_avg=0.15,
        environment="dev",
    )
    recs = engine.recommend(wl)
    downsize_recs = [r for r in recs if r.action == "downsize"]
    assert len(downsize_recs) > 0
    assert downsize_recs[0].monthly_savings > 0
    assert downsize_recs[0].recommended_instance.vcpus < 4


def test_recommend_no_downsize_when_well_utilized():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    wl = _make_workload(
        instance_name="m5.xlarge",
        cpu_avg=0.60,
        mem_avg=0.70,
    )
    recs = engine.recommend(wl)
    downsize_recs = [r for r in recs if r.action == "downsize"]
    assert len(downsize_recs) == 0


def test_recommend_all_sorts_by_savings():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    wl1 = _make_workload("wl-001", "app1", instance_name="m5.xlarge", cpu_avg=0.10, mem_avg=0.15, environment="dev")
    wl2 = _make_workload("wl-002", "app2", instance_name="m5.xlarge", cpu_avg=0.12, mem_avg=0.18, environment="dev")
    recs = engine.recommend_all([wl1, wl2])
    if len(recs) >= 2:
        assert recs[0].annual_savings >= recs[1].annual_savings


def test_recommend_without_catalog():
    engine = RightsizingEngine([])
    wl = _make_workload(cpu_avg=0.10, mem_avg=0.15)
    recs = engine.recommend(wl)
    # Without catalog, no downsize or upsize recommendations
    assert len([r for r in recs if r.action == "downsize"]) == 0


def test_family_modernization():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    # m5.xlarge with low utilization — m6i.large is newer and cheaper
    wl = _make_workload(
        instance_name="m5.xlarge",
        cpu_avg=0.15,
        mem_avg=0.20,
        environment="production",
    )
    recs = engine.recommend(wl)
    family_recs = [r for r in recs if r.action == "family_change"]
    # m6i.large is newer and cheaper than m5.xlarge
    assert len(family_recs) > 0


def test_risk_assessment_production():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    wl = _make_workload(
        instance_name="m5.xlarge",
        cpu_avg=0.10,
        mem_avg=0.15,
        environment="production",
    )
    recs = engine.recommend(wl)
    downsize_recs = [r for r in recs if r.action == "downsize"]
    if downsize_recs:
        # Very low utilization in production should be low risk
        assert downsize_recs[0].risk_level == RiskLevel.LOW


def test_risk_assessment_dev():
    catalog = _make_catalog()
    engine = RightsizingEngine(catalog)
    wl = _make_workload(
        instance_name="m5.xlarge",
        cpu_avg=0.10,
        mem_avg=0.15,
        environment="dev",
    )
    recs = engine.recommend(wl)
    downsize_recs = [r for r in recs if r.action == "downsize"]
    if downsize_recs:
        assert downsize_recs[0].risk_level == RiskLevel.LOW
