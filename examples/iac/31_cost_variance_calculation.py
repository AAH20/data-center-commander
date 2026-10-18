"""Example: Cost variance calculation.

Demonstrates how total variance and variance percentage are calculated.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": "2024-01-01", "cost": 120.0, "expected_cost": 100.0},
    {"resource_id": "i-2", "resource_name": "web-2", "resource_type": "aws_instance",
     "timestamp": "2024-01-01", "cost": 80.0, "expected_cost": 100.0},
]

detector = CostAnomalyDetector()
report = detector.detect(cost_data)
print(f"Total expected: ${report.total_expected_cost:.2f}")
print(f"Total actual: ${report.total_actual_cost:.2f}")
print(f"Total variance: ${report.total_variance:.2f}")
print(f"Variance %: {report.variance_pct:.1f}%")
