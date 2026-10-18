"""Example: Detect increasing cost trend.

Demonstrates detecting a sustained upward cost trend.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = []
for d in range(1, 15):
    cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                      "timestamp": f"2024-01-{d:02d}", "cost": 100.0 + d * 2, "expected_cost": 100.0})
for d in range(15, 29):
    cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                      "timestamp": f"2024-01-{d:02d}", "cost": 200.0 + d * 2, "expected_cost": 100.0})

detector = CostAnomalyDetector(spike_threshold=0.20, trend_window=7)
report = detector.detect(cost_data)
print(f"Has anomalies: {report.has_anomalies}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.description}")
