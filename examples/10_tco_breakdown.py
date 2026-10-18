"""Example: TCO cost breakdown by category.

Shows how to extract per-category costs from a TCO result.
"""
from dcc.economics.tco import (
    TCOAssumptions, TCOCostBreakdown, TCOScenario, evaluate_tco,
    tco_breakdown_by_category,
)

assumptions = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
scenario = TCOScenario(
    name="DC Build",
    costs=TCOCostBreakdown(
        hardware_capex=5_000_000,
        energy_annual=1_000_000,
        maintenance_annual=400_000,
        labor_annual=600_000,
        network_annual=150_000,
        software_annual=250_000,
        refresh_cost=1_500_000,
        refresh_interval_years=5,
        decommission_cost=300_000,
        residual_value=800_000,
    ),
    assumptions=assumptions,
)
result = evaluate_tco(scenario)
breakdown = tco_breakdown_by_category(result)
for category, amount in breakdown.items():
    print(f"  {category}: ${amount:,.2f}")
