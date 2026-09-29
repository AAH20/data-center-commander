"""Example: Load tariff from a dictionary (e.g., database JSONB).

Demonstrates deserializing a tariff spec from stored JSON.
"""
from dcc.economics.tariffs import TariffSpec, calculate_tariff

tariff_dict = {
    "schema_version": "tariff.v1",
    "currency": "USD",
    "timezone": "America/Chicago",
    "billing_period": "monthly",
    "tou_periods": [
        {"name": "peak", "days_of_week": [1,2,3,4,5], "start_time": "14:00", "end_time": "20:00", "rate_per_kwh": "0.28"},
        {"name": "off_peak", "days_of_week": [1,2,3,4,5,6,7], "start_time": "20:00", "end_time": "14:00", "rate_per_kwh": "0.09"},
    ],
    "demand_charges": [{"name": "peak_demand", "rate_per_kw": "16.00", "billing_demand_basis": "peak_kw_monthly"}],
    "tiered_rates": [],
    "fixed_charges": [{"name": "service_fee", "amount": "100.00", "frequency": "monthly"}],
}
spec = TariffSpec.from_dict(tariff_dict)
result = calculate_tariff(spec=spec, energy_kwh=100000, peak_demand_kw=900)
print(f"Total: ${result.total:,.2f}")
