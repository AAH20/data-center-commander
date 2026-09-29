"""Example: Budget unit economics.

Computes EAC and cost-per-unit from a budget forecast.
"""
from dcc.economics.budget import compute_unit_economics

result = compute_unit_economics(
    total_cost=10_000_000,
    horizon_years=10,
    discount_rate=0.08,
    denominator=5000,
    denominator_unit="kW",
)
print(f"EAC: ${result['equivalent_annual_cost']:,.2f}")
print(f"Cost per unit: ${result['cost_per_unit']:,.2f}/{result['denominator_unit"]}")
