"""Example: Cost per kW-year metric.

Normalizes annual cost by IT capacity for cross-facility comparison.
"""
from dcc.economics.unit import cost_per_kw_year

result = cost_per_kw_year(annual_cost=2_400_000, it_capacity_kw=2000)
print(f"Cost per kW-year: ${result.value:,.2f} {result.unit} [{result.status}]")

# Negative cost → not_priced
bad = cost_per_kw_year(annual_cost=-100, it_capacity_kw=100)
print(f"Negative cost: {bad.status} — {bad.detail}")

# Zero capacity → unknown
zero = cost_per_kw_year(annual_cost=1000, it_capacity_kw=0)
print(f"Zero capacity: {zero.status} — {zero.detail}")
