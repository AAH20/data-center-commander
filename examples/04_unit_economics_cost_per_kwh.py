"""Example: Cost per kWh at IT and facility boundaries.

Shows how the same energy OPEX yields different unit costs depending on
whether you divide by IT energy or total facility energy.
"""
from dcc.economics.unit import cost_per_kwh

results = cost_per_kwh(
    energy_cost=3_600_000,
    it_energy_kwh=5_000_000,
    facility_energy_kwh=7_500_000,
)
for boundary, res in results.items():
    print(f"{boundary}: ${res.value:.4f}/kWh [{res.status}]")
