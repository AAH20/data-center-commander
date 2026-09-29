"""Example: Full TCO evaluation with escalation and refresh.

Demonstrates the TCOEngine with detailed assumptions including
energy escalation, maintenance escalation, and hardware refresh.
"""
from dcc.economics.tco import TCOAssumptions, TCOEngine, evaluate_tco

assumptions = TCOAssumptions(
    currency="USD",
    horizon_years=15,
    annual_discount_rate=0.08,
    energy_escalation_pct=0.03,
    maintenance_escalation_pct=0.025,
    labor_escalation_pct=0.03,
)
engine = TCOEngine(assumptions=assumptions)
result = engine.evaluate(
    capex=8_000_000,
    annual_energy=2_000_000,
    annual_maintenance=500_000,
    annual_labor=800_000,
    annual_network=300_000,
    annual_software=400_000,
    refresh_cost=2_000_000,
    refresh_year=8,
    terminal_cost=500_000,
    residual_value=1_000_000,
)
print(f"Total PV: ${result.total_pv:,.2f}")
print(f"Total CapEx: ${result.total_capex:,.2f}")
print(f"Total OpEx PV: ${result.total_opex_pv:,.2f}")
print(f"EAC: ${result.eac:,.2f}")
