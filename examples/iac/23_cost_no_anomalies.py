"""Example: Cost anomaly detection with no anomalies.

Demonstrates stable cost data with no anomalies detected.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
    for d in range(1, 15)
]

detector = CostAnomalyDetector()
report = detector.detect(cost_data)
print(f"Has anomalies: {report.has_anomalies}")
print(f"Total anomalies: {report.total_anomalies}")
print(f"Total expected: ${report.total_expected_cost:.2f}")
print(f"Total actual: ${report.total_actual_cost:.2f}")
