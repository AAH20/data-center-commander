"""Example: Quick TCO estimate with minimal inputs.

Uses the quick_tco convenience function for rapid comparison.
"""
from dcc.economics.tco import quick_tco

result = quick_tco(
    capex=5_000_000,
    annual_opex=1_200_000,
    horizon_years=10,
    discount_rate=0.08,
)
print(f"TCO PV: ${result.total_pv:,.2f}")
print(f"EAC: ${result.eac:,.2f}")
print(f"Year 1 cash: ${result.year_one_cash:,.2f}")
