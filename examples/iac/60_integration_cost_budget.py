"""Example: Cost anomaly detection with budget data.

Demonstrates detecting cost anomalies with budget comparison.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

# Monthly cost data for multiple resources
cost_data = [
    # web-1: stable
    {"resource_id": "web-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
    for d in range(1, 15)
] + [
    # web-2: over budget
    {"resource_id": "web-2", "resource_name": "web-2", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 200.0, "expected_cost": 100.0}
    for d in range(1, 15)
] + [
    # db-1: spike on last day
    {"resource_id": "db-1", "resource_name": "db-1", "resource_type": "aws_db_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 150.0, "expected_cost": 150.0}
    for d in range(1, 15)
] + [
    {"resource_id": "db-1", "resource_name": "db-1", "resource_type": "aws_db_instance",
     "timestamp": "2024-01-15", "cost": 500.0, "expected_cost": 150.0},
]

budget_data = {
    "web-1": 100.0,
    "web-2": 100.0,
    "db-1": 150.0,
}

detector = CostAnomalyDetector(zscore_threshold=2.0, budget_variance_threshold=0.10)
report = detector.detect(cost_data, budget_data)
print(f"Total anomalies: {report.total_anomalies}")
print(f"Total expected: ${report.total_expected_cost:.2f}")
print(f"Total actual: ${report.total_actual_cost:.2f}")
print(f"Total variance: ${report.total_variance:.2f}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.resource_name} - {a.description}")
