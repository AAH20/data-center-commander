"""Example: Metered energy allocation.

Allocates cost based on measured energy consumption per workload.
"""
from dcc.economics.allocation import allocate_cost, AllocationMethod, WorkloadShare

report = allocate_cost(
    cost_actual_id="COST-002",
    total_amount=500_000,
    currency="USD",
    method=AllocationMethod.DIRECT_METER,
    workload_ids=["workload-a", "workload-b", "workload-c"],
    shares=[
        WorkloadShare(workload_id="workload-a", share_value=Decimal("3000")),
        WorkloadShare(workload_id="workload-b", share_value=Decimal("5000")),
        WorkloadShare(workload_id="workload-c", share_value=Decimal("2000")),
    ],
)
for r in report.results:
    print(f"  {r.workload_id}: ${r.allocated_amount:,.2f} ({r.allocation_fraction:.1%})")
