"""Example: Manual approved allocation.

Uses pre-approved weights for cost distribution.
"""
from dcc.economics.allocation import allocate_cost, AllocationMethod
from decimal import Decimal

report = allocate_cost(
    cost_actual_id="COST-003",
    total_amount=1_000_000,
    currency="USD",
    method=AllocationMethod.MANUAL_APPROVED,
    workload_ids=["prod", "staging", "dev"],
    custom_weights={
        "prod": Decimal("0.6"),
        "staging": Decimal("0.3"),
        "dev": Decimal("0.1"),
    },
)
for r in report.results:
    print(f"  {r.workload_id}: ${r.allocated_amount:,.2f} ({r.allocation_fraction:.1%})")
