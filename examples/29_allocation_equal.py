"""Example: Equal-share cost allocation.

Divides a shared cost equally among workloads.
"""
from dcc.economics.allocation import allocate_cost, AllocationMethod

report = allocate_cost(
    cost_actual_id="COST-001",
    total_amount=120_000,
    currency="USD",
    method=AllocationMethod.EQUAL_SHARE,
    workload_ids=["web", "api", "db"],
)
print(f"Total: ${report.total_amount:,.2f}")
print(f"Allocated: ${report.allocated_total:,.2f}")
for r in report.results:
    print(f"  {r.workload_id}: ${r.allocated_amount:,.2f} ({r.allocation_fraction:.1%})")
