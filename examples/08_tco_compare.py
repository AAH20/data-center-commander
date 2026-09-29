"""Example: Compare TCO of two deployment options.

Side-by-side comparison of on-prem vs. cloud over the same horizon.
"""
from dcc.economics.tco import TCOAssumptions, TCOEngine, compare_tco

assumptions = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
engine = TCOEngine(assumptions=assumptions)

onprem = engine.evaluate(
    capex=10_000_000, annual_energy=1_500_000, annual_maintenance=600_000,
    annual_labor=1_000_000, annual_network=200_000, annual_software=300_000,
    refresh_cost=3_000_000, refresh_year=6, terminal_cost=1_000_000, residual_value=2_000_000,
)
cloud = engine.evaluate(
    capex=500_000, annual_energy=0, annual_maintenance=0,
    annual_labor=200_000, annual_network=100_000, annual_software=5_000_000,
    refresh_cost=0, refresh_year=0, terminal_cost=0, residual_value=0,
)

comparison = compare_tco(onprem, cloud)
print(f"On-prem PV: ${comparison.scenario_a.total_pv:,.2f}")
print(f"Cloud PV: ${comparison.scenario_b.total_pv:,.2f}")
print(f"Delta (cloud - onprem): ${comparison.npv_delta:,.2f}")
print(f"Winner: {'Cloud' if comparison.npv_delta < 0 else 'On-prem'}")
