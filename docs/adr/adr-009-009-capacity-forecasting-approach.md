# ADR-009: Capacity Forecasting Approach

## Status
Accepted

## Context
Operators need forward-looking capacity predictions to plan procurement, identify at-risk dates, and avoid over-provisioning.

## Decision
Capacity forecasting uses three methods: linear trend (least squares), moving average, and exponential smoothing. Method selection is automatic based on data characteristics (R², volatility). Forecasts include confidence intervals that widen with horizon. Quality gates require minimum data points, coverage, and flag suspicious growth rates.

## Consequences
- **Positive:** Multiple methods for different data patterns; automatic method selection; uncertainty quantification.
- **Negative:** No seasonality modeling; limited to 365-day horizon; requires sufficient history.
- **Mitigation:** Minimum history gates; quality status propagation; advisory-only labeling.
