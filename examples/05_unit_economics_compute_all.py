"""Example: Compute all unit economics metrics in one call.

Demonstrates the convenience wrapper that returns EAC, cost/kW, cost/rack,
cost/m², cost/kWh, and optionally cost/work-unit.
"""
from dcc.economics.unit import compute_all_unit_economics

results = compute_all_unit_economics(
    present_value=10_000_000,
    years=15,
    discount_rate=0.08,
    it_capacity_kw=5000,
    rack_count=800,
    area_m2=10000,
    energy_cost=5_000_000,
    it_energy_kwh=8_000_000,
    facility_energy_kwh=12_000_000,
    allocated_cost=12_000_000,
    useful_work=1_000_000,
)
print(f"EAC: ${results['eac']:,.2f}")
print(f"Cost/kW-year: ${results['cost_per_kw'].value:,.2f}")
print(f"Cost/rack-year: ${results['cost_per_rack'].value:,.2f}")
print(f"Cost/m²-year: ${results['cost_per_m2'].value:,.2f}")
print(f"Cost/kWh (IT): ${results['cost_per_kwh']['it_boundary'].value:.4f}")
print(f"Cost/kWh (facility): ${results['cost_per_kwh']['facility_boundary'].value:.4f}")
print(f"Cost/work-unit: ${results['cost_per_work'].value:.2f}")
