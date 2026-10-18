"""Example: Build an estimate with the EstimateBuilder.

Demonstrates fluent construction of a detailed cost estimate.
"""
from decimal import Decimal
from dcc.economics.estimates import (
    EstimateBuilder, DeploymentSpec, DeploymentType, TierLevel, RedundancyLevel,
)

spec = DeploymentSpec(
    name="DC Build 5MW",
    deployment_type=DeploymentType.GREENFIELD,
    it_capacity_kw=Decimal("5000"),
    rack_count=500,
    white_space_m2=Decimal("8000"),
    tier_level=TierLevel.TIER_III,
    redundancy=RedundancyLevel.N_PLUS_1,
    geography="us-east",
    currency="USD",
    horizon_months=180,
    discount_rate=Decimal("0.08"),
    contingency_pct=Decimal("0.10"),
)
builder = EstimateBuilder(spec)
line_items = builder.build_line_items()
print(f"Line items: {len(line_items)}")
for item in line_items[:5]:
    print(f"  {item.description}: ${item.extended_base:,.2f}")
