# ADR-011: Failure Prediction Model

## Status
Accepted

## Context
Predictive maintenance requires scoring asset failure risk from telemetry patterns without requiring a trained ML classifier or external dependencies.

## Decision
The failure prediction model uses statistical methods: z-score anomaly detection, IQR-based outlier detection, EWMA shift detection, trend slope analysis, and degradation detection. Risk scores combine telemetry anomalies, degradation trends, data staleness, criticality weighting, and lifecycle state. Output is relative risk for prioritization, not absolute failure probability.

## Consequences
- **Positive:** No ML dependencies; interpretable risk factors; works with limited history; pure stdlib.
- **Negative:** Not a trained classifier; may miss complex failure modes; requires telemetry data.
- **Mitigation:** Model policy transparency; human review of critical assets; continuous model evaluation.
