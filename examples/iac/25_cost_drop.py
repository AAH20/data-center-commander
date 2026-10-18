"""Example: Detect cost drop.

Demonstrates detecting a sudden cost decrease.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
    for d in range(1, 15)
]
# Add a drop
cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                  "timestamp": "2024-01-15", "cost": 10.0, "expected_cost": 100.0})

detector = CostAnomalyDetector(zscore_threshold=2.0)
report = detector.detect(cost_data)
print(f"Has anomalies: {report.has_anomalies}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.description}")
