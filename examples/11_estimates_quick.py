"""Example: Quick deployment estimate.

Uses quick_estimate for rapid bottom-up cost estimation.
"""
from dcc.economics.estimates import quick_estimate

result = quick_estimate(
    it_capacity_kw=2000,
    rack_count=200,
    area_m2=3000,
    deployment_type="onprem",
    tier_level="tier_iii",
    redundancy_level="n_plus_1",
    geography="us-east",
    currency="USD",
    horizon_years=15,
)
print(f"Total PV: ${result.total_pv:,.2f}")
print(f"Line items: {len(result.line_items)}")
for line in result.line_items[:5]:
    print(f"  {line.description}: ${line.extended_base:,.2f}")
