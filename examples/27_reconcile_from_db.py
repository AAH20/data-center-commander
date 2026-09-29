"""Example: Reconcile from database row dicts.

Convenience wrapper that extracts fields from DB rows.
"""
from dcc.economics.reconciliation import reconcile_from_database_rows

estimate_row = {"id": "EST-001", "name": "DC Build", "currency": "USD"}
rollup_rows = [
    {"phase": "electrical", "present_value_base": 1_000_000, "present_value_low": 900_000, "present_value_high": 1_100_000, "line_count": 8},
]
actual_rows = [
    {"phase": "electrical", "amount": 1_050_000, "currency": "USD"},
]
result = reconcile_from_database_rows(
    estimate_row=estimate_row,
    rollup_rows=rollup_rows,
    actual_rows=actual_rows,
)
print(f"Classification: {result['summary']['overall_classification']}")
