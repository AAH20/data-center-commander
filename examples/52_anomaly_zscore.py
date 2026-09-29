"""Example: Z-score anomaly detection.

Flags observations that deviate significantly from the mean.
"""
from dcc.forecasting.anomaly import detect_anomalies

values = [100, 102, 98, 101, 99, 103, 97, 100, 150, 101, 99, 100]
report = detect_anomalies(values, method="zscore", threshold=2.5)
print(f"Method: {report.method}")
print(f"Anomalies: {report.anomaly_count}/{report.total_points}")
for a in report.anomalies:
    print(f"  Index {a.index}: value={a.value}, expected={a.expected:.1f}, deviation={a.deviation:.1f}")
