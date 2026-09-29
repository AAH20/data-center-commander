"""Example: TCO cost breakdown by category.

Shows how to extract per-category costs from a TCO result.
"""
from dcc.economics.tco import TCOAssumptions, TCOEngine, tco_breakdown_by_category

assumptions = TCOAssumptions(currency="USD", horizon_years=10, annual_discount_rate=0.08)
engine = TCOEngine(assumptions=assumptions)
result = engine.evaluate(
    capex=5_000_000, annual_energy=1_000_000, annual_maintenance=400_000,
    annual_labor=600_000, annual_network=150_000, annual_software=250_000,
    refresh_cost=1_500_000, refresh_year=5, terminal_cost=300_000, residual_value=800_000,
)
breakdown = tco_breakdown_by_category(result)
for category, amount in breakdown.items():
    print(f"  {category}: ${amount:,.2f}")
