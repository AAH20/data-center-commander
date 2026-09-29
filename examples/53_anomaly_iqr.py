"""Example: IQR-based anomaly detection.

Uses interquartile range for robust outlier detection.
"""
from dcc.forecasting.anomaly import detect_anomalies

values = [10, 12, 11, 13, 12, 11, 10, 12, 50, 11, 12, 10]
report = detect_anomalies(values, method="iqr", factor=1.5)
print(f"Anomalies: {report.anomaly_count}")
for a in report.anomalies:
    print(f"  Index {a.index}: value={a.value} (severity: {a.severity})")
