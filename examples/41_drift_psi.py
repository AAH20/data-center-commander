"""Example: Population Stability Index (PSI) drift detection.

Measures distribution shift between reference and current data.
"""
from dcc.forecasting.drift import compute_psi, detect_drift, DriftMethod

reference = [100, 102, 98, 105, 97, 103, 99, 101, 104, 96] * 10
current = [110, 112, 108, 115, 107, 113, 109, 111, 114, 106] * 10
psi = compute_psi(reference, current, bins=10)
print(f"PSI: {psi:.4f}")
results = detect_drift(reference, current, methods={DriftMethod.PSI})
for r in results:
    print(f"Detected: {r.detected}, Severity: {r.severity}")
