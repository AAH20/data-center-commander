"""Example: Compare TCO of two deployment options.

Side-by-side comparison of on-prem vs. cloud over the same horizon.
"""
from dcc.economics.tco import (
    TCOAssumptions, TCOCostBreakdown, TCOScenario, compare_tco,
)

assumptions = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
onprem = TCOScenario(
    name="On-Prem",
    costs=TCOCostBreakdown(
        hardware_capex=10_000_000,
        energy_annual=1_500_000,
        maintenance_annual=600_000,
        labor_annual=1_000_000,
        network_annual=200_000,
        software_annual=300_000,
        refresh_cost=3_000_000,
        refresh_interval_years=6,
        decommission_cost=1_000_000,
        residual_value=2_000_000,
    ),
    assumptions=assumptions,
)
cloud = TCOScenario(
    name="Cloud",
    costs=TCOCostBreakdown(
        hardware_capex=500_000,
        labor_annual=200_000,
        network_annual=100_000,
        software_annual=5_000_000,
    ),
    assumptions=assumptions,
)
comparison = compare_tco([onprem, cloud])
print(f"On-prem PV: ${comparison.scenarios[0].total_pv:,.2f}")
print(f"Cloud PV: ${comparison.scenarios[1].total_pv:,.2f}")
print(f"Delta (cloud - onprem): ${comparison.pv_deltas[1]:+,.2f}")
print(f"Winner: {'Cloud' if comparison.pv_deltas[1] < 0 else 'On-prem'}")
