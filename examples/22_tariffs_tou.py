"""Example: Time-of-use tariff calculation.

Different rates for peak and off-peak periods.
"""
from dcc.economics.tariffs import create_simple_tou_tariff, calculate_tariff

spec = create_simple_tou_tariff(
    currency="USD",
    peak_rate=0.25,
    off_peak_rate=0.10,
    peak_hours=(12, 13, 14, 15, 16, 17),
    peak_days=(1, 2, 3, 4, 5),
    demand_rate_per_kw=18.00,
    fixed_monthly_charge=75.00,
)
result = calculate_tariff(
    spec=spec,
    energy_kwh=80000,
    peak_demand_kw=800,
    energy_by_period={"peak": 20000, "off_peak": 60000},
)
for tou in result.tou_charges:
    print(f"  {tou.period_name}: {tou.energy_kwh} kWh @ ${tou.rate_per_kwh}/kWh = ${tou.charge:,.2f}")
print(f"Total: ${result.total:,.2f}")
