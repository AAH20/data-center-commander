"""Example: Reconcile an estimate against actual costs.

Compares estimated PV vs. actual spend with variance classification.
"""
from dcc.economics.reconciliation import reconcile_estimate, VarianceThresholds

estimate_rollup = [
    {"phase": "electrical", "present_value_base": 2_000_000, "present_value_low": 1_800_000, "present_value_high": 2_200_000, "line_count": 15, "currency": "USD"},
    {"phase": "mechanical", "present_value_base": 1_500_000, "present_value_low": 1_350_000, "present_value_high": 1_650_000, "line_count": 10, "currency": "USD"},
    {"phase": "it", "present_value_base": 3_000_000, "present_value_low": 2_700_000, "present_value_high": 3_300_000, "line_count": 20, "currency": "USD"},
]
actuals = [
    {"phase": "electrical", "amount": 2_100_000, "currency": "USD"},
    {"phase": "mechanical", "amount": 1_400_000, "currency": "USD"},
    {"phase": "it", "amount": 3_200_000, "currency": "USD"},
]
result = reconcile_estimate(
    estimate_id="EST-001",
    estimate_name="DC Expansion Phase 1",
    currency="USD",
    estimate_rollup=estimate_rollup,
    actuals=actuals,
    thresholds=VarianceThresholds(favorable_pct=-0.10, unfavorable_pct=0.10, significant_pct=0.20),
)
print(f"Total estimate: ${result['summary']['total_estimate_base']:,.2f}")
print(f"Total actual: ${result['summary']['total_actual']:,.2f}")
print(f"Variance: ${result['summary']['total_variance']:,.2f} ({result['summary']['total_variance_pct']}%)")
print(f"Classification: {result['summary']['overall_classification']}")
