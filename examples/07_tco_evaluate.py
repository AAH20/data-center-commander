"""Example: Full TCO evaluation with escalation and refresh.

Demonstrates the TCOEngine with detailed assumptions including
energy escalation, maintenance escalation, and hardware refresh.
"""
from dcc.economics.tco import (
    TCOAssumptions, TCOCostBreakdown, TCOScenario, evaluate_tco,
)

assumptions = TCOAssumptions(
    currency="USD",
    horizon_years=15,
    annual_discount_rate=0.08,
    energy_escalation_pct=0.03,
    maintenance_escalation_pct=0.025,
    labor_escalation_pct=0.03,
)
scenario = TCOScenario(
    name="DC Build 2MW",
    costs=TCOCostBreakdown(
        hardware_capex=8_000_000,
        facility_capex=2_000_000,
        energy_annual=2_000_000,
        maintenance_annual=500_000,
        labor_annual=800_000,
        network_annual=300_000,
        software_annual=400_000,
        refresh_cost=2_000_000,
        refresh_interval_years=7,
        decommission_cost=500_000,
        residual_value=1_000_000,
    ),
    assumptions=assumptions,
)
result = evaluate_tco(scenario)
print(f"Total PV: ${result.total_pv:,.2f}")
print(f"Total CapEx: ${result.total_capex:,.2f}")
print(f"Total OpEx: ${result.total_opex:,.2f}")
print(f"EAC: ${result.equivalent_annual_cost:,.2f}")
