"""Example: Detect decreasing cost trend.

Demonstrates detecting a sustained downward cost trend.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector, CostAnomalyType

cost_data = []
for d in range(1, 15):
    cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                      "timestamp": f"2024-01-{d:02d}", "cost": 200.0, "expected_cost": 200.0})
for d in range(15, 29):
    cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                      "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 200.0})

detector = CostAnomalyDetector(spike_threshold=0.20, trend_window=7)
report = detector.detect(cost_data)
print(f"Has anomalies: {report.has_anomalies}")
for a in report.anomalies:
    print(f"  {a.anomaly_type.value}: {a.description}")
