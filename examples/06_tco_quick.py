"""Example: Quick TCO estimate with minimal inputs.

Uses the quick_tco convenience function for rapid comparison.
"""
from dcc.economics.tco import quick_tco

result = quick_tco(
    hardware_capex=5_000_000,
    energy_annual=1_000_000,
    maintenance_annual=300_000,
    labor_annual=500_000,
    network_annual=100_000,
    software_annual=200_000,
    horizon_years=10,
    annual_discount_rate=0.08,
)
print(f"TCO PV: ${result.total_pv:,.2f}")
print(f"EAC: ${result.equivalent_annual_cost:,.2f}")
print(f"Year 1 cash: ${result.year_one_cash:,.2f}")
