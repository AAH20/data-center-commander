"""Example: Equivalent Annual Cost (EAC) calculation.

Converts a present-value cost into an equal annual payment over a horizon,
optionally discounting future costs.
"""
from dcc.economics.unit import equivalent_annual_cost

# Simple: $1M over 10 years, no discount
eac_simple = equivalent_annual_cost(1_000_000, 10, 0.0)
print(f"EAC (no discount): ${eac_simple:,.2f}/year")

# With 8% discount rate
eac_discounted = equivalent_annual_cost(1_000_000, 10, 0.08)
print(f"EAC (8% discount): ${eac_discounted:,.2f}/year")

# Edge: zero horizon raises ValueError
try:
    equivalent_annual_cost(1_000_000, 0)
except ValueError as e:
    print(f"Expected error: {e}")
