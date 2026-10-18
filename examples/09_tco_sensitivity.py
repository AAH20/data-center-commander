"""Example: TCO sensitivity analysis.

Varies discount rate and energy escalation to see impact on total cost.
"""
from dcc.economics.tco import (
    TCOAssumptions, TCOCostBreakdown, TCOScenario, run_tco_sensitivity,
)

assumptions = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
scenario = TCOScenario(
    name="Base",
    costs=TCOCostBreakdown(
        hardware_capex=5_000_000,
        energy_annual=1_000_000,
        maintenance_annual=300_000,
        labor_annual=500_000,
        network_annual=100_000,
        software_annual=200_000,
    ),
    assumptions=assumptions,
)
sensitivity = run_tco_sensitivity(
    scenario=scenario,
    parameter_name="discount_rate",
    values=[0.04, 0.06, 0.08, 0.10, 0.12],
)
for val, pv in zip(sensitivity.values_tested, sensitivity.pv_results):
    print(f"  Discount {val:.0%}: PV = ${pv:,.2f}")
