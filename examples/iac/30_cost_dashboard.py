"""Example: Build cost anomaly dashboard data.

Demonstrates creating dashboard-ready cost anomaly data.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector, build_cost_dashboard

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0, "expected_cost": 100.0}
    for d in range(1, 15)
]
cost_data.append({"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
                  "timestamp": "2024-01-15", "cost": 500.0, "expected_cost": 100.0})

detector = CostAnomalyDetector(zscore_threshold=2.0)
report = detector.detect(cost_data)
dashboard = build_cost_dashboard(report)
print(f"Total anomalies: {dashboard['total_anomalies']}")
print(f"Has anomalies: {dashboard['has_anomalies']}")
print(f"Total variance: ${dashboard['total_variance']}")
print(f"Variance %: {dashboard['variance_pct']}%")
print(f"Severity counts: {dashboard['severity_counts']}")
print(f"Top anomalies: {len(dashboard['top_anomalies'])}")
