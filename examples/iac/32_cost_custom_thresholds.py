"""Example: Custom detector thresholds.

Demonstrating customizing detection thresholds.
"""
from dcc.iac_observability.cost_anomaly import CostAnomalyDetector

cost_data = [
    {"resource_id": "i-1", "resource_name": "web-1", "resource_type": "aws_instance",
     "timestamp": f"2024-01-{d:02d}", "cost": 100.0 + d * 5, "expected_cost": 100.0}
    for d in range(1, 15)
]

# Strict thresholds
detector = CostAnomalyDetector(
    zscore_threshold=1.5,
    spike_threshold=0.15,
    budget_variance_threshold=0.05,
    trend_window=5,
)
report = detector.detect(cost_data)
print(f"Strict thresholds - anomalies: {report.total_anomalies}")

# Lenient thresholds
detector2 = CostAnomalyDetector(
    zscore_threshold=4.0,
    spike_threshold=0.50,
    budget_variance_threshold=0.30,
    trend_window=14,
)
report2 = detector2.detect(cost_data)
print(f"Lenient thresholds - anomalies: {report2.total_anomalies}")
