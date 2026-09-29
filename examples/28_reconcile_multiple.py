"""Example: Reconcile multiple estimates at once.

Combines variance analysis across a portfolio of projects.
"""
from dcc.economics.reconciliation import reconcile_multiple

estimates = [
    {
        "estimate_row": {"id": "EST-001", "name": "Project A", "currency": "USD"},
        "rollup_rows": [{"phase": "it", "present_value_base": 1_000_000, "present_value_low": 900_000, "present_value_high": 1_100_000, "line_count": 10}],
        "actual_rows": [{"phase": "it", "amount": 950_000, "currency": "USD"}],
    },
    {
        "estimate_row": {"id": "EST-002", "name": "Project B", "currency": "USD"},
        "rollup_rows": [{"phase": "it", "present_value_base": 2_000_000, "present_value_low": 1_800_000, "present_value_high": 2_200_000, "line_count": 15}],
        "actual_rows": [{"phase": "it", "amount": 2_300_000, "currency": "USD"}],
    },
]
result = reconcile_multiple(estimates=estimates)
print(f"Combined estimate: ${result['combined']['total_estimate_base']:,.2f}")
print(f"Combined actual: ${result['combined']['total_actual']:,.2f}")
print(f"Combined variance: ${result['combined']['total_variance']:,.2f}")
