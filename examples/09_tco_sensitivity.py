"""Example: TCO sensitivity analysis.

Varies discount rate and energy escalation to see impact on total cost.
"""
from dcc.economics.tco import TCOAssumptions, TCOEngine, run_tco_sensitivity

base = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
engine = TCOEngine(assumptions=base)

sensitivity = run_tco_sensitivity(
    engine=engine,
    capex=5_000_000,
    annual_energy=1_000_000,
    annual_maintenance=300_000,
    annual_labor=500_000,
    annual_network=100_000,
    annual_software=200_000,
    parameter="annual_discount_rate",
    values=[0.04, 0.06, 0.08, 0.10, 0.12],
)
for val, pv in zip(sensitivity.values_tested, sensitivity.pv_results):
    print(f"  Discount {val:.0%}: PV = ${pv:,.2f}")
