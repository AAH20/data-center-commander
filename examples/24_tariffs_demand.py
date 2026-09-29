"""Example: Demand charge calculation.

Standalone demand charge calculation for peak kW billing.
"""
from dcc.economics.tariffs import DemandCharge, calculate_demand_charges

charges = [
    DemandCharge(name="peak_demand", rate_per_kw=15.00, billing_demand_basis="peak_kw_monthly"),
    DemandCharge(name="contract_demand", rate_per_kw=8.00, billing_demand_basis="contract_demand"),
]
results = calculate_demand_charges(demand_charges=charges, billing_demand_kw=750)
for r in results:
    print(f"  {r.charge_name}: {r.billing_demand_kw} kW @ ${r.rate_per_kw}/kW = ${r.charge:,.2f}")
