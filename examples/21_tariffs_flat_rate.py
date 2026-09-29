"""Example: Flat rate tariff calculation.

Simplest tariff structure — single rate for all consumption.
"""
from dcc.economics.tariffs import create_flat_rate_tariff, calculate_tariff

spec = create_flat_rate_tariff(
    currency="USD",
    rate_per_kwh=0.12,
    demand_rate_per_kw=15.00,
    fixed_monthly_charge=100.00,
)
result = calculate_tariff(spec=spec, energy_kwh=50000, peak_demand_kw=500)
print(f"Energy charges: ${result.total_energy_charges:,.2f}")
print(f"Demand charges: ${result.total_demand_charges:,.2f}")
print(f"Fixed charges: ${result.total_fixed_charges:,.2f}")
print(f"Total: ${result.total:,.2f}")
