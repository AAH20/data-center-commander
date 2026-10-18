"""Example: Multiplicative calibration.

Scales forecasts by the ratio of actual to predicted.
"""
from dcc.forecasting.calibration import (
    ForecastPoint, ActualPoint, match_forecast_actual_pairs,
    apply_multiplicative_correction, compute_calibration_metrics,
)

forecasts = [ForecastPoint(timestamp=i, value=100) for i in range(10)]
actuals = [ActualPoint(timestamp=i, value=110) for i in range(10)]
pairs = match_forecast_actual_pairs(forecasts, actuals)
metrics = compute_calibration_metrics(pairs)
scale = metrics.get("scale_factor", 1.0)
calibrated = apply_multiplicative_correction(forecasts, scale)
print(f"Scale factor: {scale:.4f}")
for f in calibrated[:3]:
    print(f"  t={f.timestamp}: {f.value:.1f}")
