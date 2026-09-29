"""Example: Lifecycle cost calculator.

Computes year-by-year cash flows with escalation and refresh.
"""
from dcc.economics.estimates import LifecycleCostCalculator, DeploymentSpec, DeploymentType

spec = DeploymentSpec(
    deployment_type=DeploymentType.ONPREM,
    it_capacity_kw=1000,
    rack_count=100,
    area_m2=1500,
    horizon_years=10,
    discount_rate=0.08,
)
calc = LifecycleCostCalculator(spec)
result = calc.calculate(
    capex=2_000_000,
    annual_energy=400_000,
    annual_maintenance=150_000,
    annual_labor=200_000,
    annual_network=50_000,
    annual_software=80_000,
    refresh_cost=500_000,
    refresh_year=5,
)
print(f"Total PV: ${result.total_pv:,.2f}")
for cf in result.yearly_cash_flows[:3]:
    print(f"  Year {cf.year}: ${cf.net_cash_flow:,.2f}")
