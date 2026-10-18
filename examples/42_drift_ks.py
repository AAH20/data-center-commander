"""Example: Kolmogorov-Smirnov drift detection.

Non-parametric test for distribution change.
"""
from dcc.forecasting.drift import compute_ks_statistic, detect_drift, DriftMethod

reference = list(range(100))
current = list(range(100, 200))
ks_stat, p_value = compute_ks_statistic(reference, current)
print(f"KS statistic: {ks_stat:.4f}, p-value: {p_value:.4f}")
results = detect_drift(reference, current, methods={DriftMethod.KS})
for r in results:
    print(f"Detected: {r.detected}, Severity: {r.severity}")
