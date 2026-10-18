"""Example: Detect budget variance.

Demonstrates detecting when actual cost exceeds budget.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": "2024-01-01", "cost": 150.0, "expected_cost": 100.0},
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": "2024-01-02", "cost": 160.0, "expected_cost": 100.0},
]
budget_data = {"i-1": 100.0}

detector = CostAnomalyDetector(budget_variance_threshold=0.10)
report = detector.detect(cost_data, budget_data)
print(f"Has anomalies: {report.has_anomalies}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.description}")
    print(f"    Deviation: {a.deviation_pct:.1f}%")
