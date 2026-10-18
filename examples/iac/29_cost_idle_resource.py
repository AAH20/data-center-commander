"""Example: Detect idle resources.

Demonstrates detecting resources with cost but low utilization.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": "2024-01-01", "cost": 100.0, "expected_cost": 100.0, "utilization": 0.02},
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": "2024-01-02", "cost": 100.0, "expected_cost": 100.0, "utilization": 0.01},
]

detector = CostAnomalyDetector()
report = detector.detect(cost_data)
print(f"Has anomalies: {report.has_anomalies}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.description}")
