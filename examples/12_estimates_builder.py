"""Example: Build an estimate with the EstimateBuilder.

Demonstrates fluent construction of a detailed cost estimate.
"""
from dcc.economics.estimates import (
    EstimateBuilder, DeploymentSpec, DeploymentType, TierLevel, RedundancyLevel,
)

spec = DeploymentSpec(
    deployment_type=DeploymentType.ONPREM,
    it_capacity_kw=5000,
    rack_count=500,
    area_m2=8000,
    tier_level=TierLevel.TIER_III,
    redundancy_level=RedundancyLevel.N_PLUS_1,
    geography="us-east",
    currency="USD",
    horizon_years=15,
    discount_rate=0.08,
    contingency_pct=0.10,
)
builder = EstimateBuilder(spec)
result = builder.build()
print(f"Total PV: ${result.total_pv:,.2f}")
print(f"Low: ${result.total_low:,.2f}")
print(f"High: ${result.total_high:,.2f}")
print(f"Phases: {len(result.phase_subtotals)}")
for phase in result.phase_subtotals:
    print(f"  {phase.phase}: ${phase.present_value_base:,.2f}")
