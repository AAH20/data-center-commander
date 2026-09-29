"""Example: Kolmogorov-Smirnov drift detection.

Non-parametric test for distribution change.
"""
from dcc.forecasting.drift import compute_ks_statistic, detect_drift, DriftMethod

reference = list(range(100))
current = list(range(100, 200))
ks_stat = compute_ks_statistic(reference, current)
print(f"KS statistic: {ks_stat:.4f}")
result = detect_drift(reference, current, method=DriftMethod.KS)
print(f"Detected: {result.detected}, Severity: {result.severity}")
