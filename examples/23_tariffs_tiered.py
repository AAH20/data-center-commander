"""Example: Tiered rate tariff calculation.

Different rates for different consumption levels.
"""
from dcc.economics.tariffs import create_tiered_tariff, calculate_tariff

spec = create_tiered_tariff(
    currency="USD",
    tiers=[
        {"upper_limit_kwh": 10000, "rate_per_kwh": 0.15},
        {"upper_limit_kwh": 50000, "rate_per_kwh": 0.12},
        {"upper_limit_kwh": 100000, "rate_per_kwh": 0.10},
        {"upper_limit_kwh": None, "rate_per_kwh": 0.08},
    ],
    demand_rate_per_kw=12.50,
    fixed_monthly_charge=50.00,
)
result = calculate_tariff(spec=spec, energy_kwh=75000, peak_demand_kw=600)
for tiered in result.tiered_charges:
    print(f"  {tiered.rate_name}: ${tiered.charge:,.2f}")
    for tb in tiered.tier_breakdown:
        print(f"    Tier {tb['tier']}: {tb['energy_kwh']} kWh @ ${tb['rate_per_kwh']}/kWh = ${tb['charge']}")
print(f"Total: ${result.total:,.2f}")
