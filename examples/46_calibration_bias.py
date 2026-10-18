"""Example: Bias correction calibration.

Adjusts forecasts by the mean error of recent predictions.
"""
from dcc.forecasting.calibration import (
    ForecastPoint, ActualPoint, match_forecast_actual_pairs,
    apply_bias_correction, compute_calibration_metrics,
)

forecasts = [ForecastPoint(timestamp=i, value=100 + i * 2) for i in range(10)]
actuals = [ActualPoint(timestamp=i, value=95 + i * 2) for i in range(10)]
pairs = match_forecast_actual_pairs(forecasts, actuals)
metrics = compute_calibration_metrics(pairs)
bias = metrics.get("bias", 0.0)
calibrated = apply_bias_correction(forecasts, bias)
print(f"Bias: {bias:.2f}")
print(f"Calibrated first: {calibrated[0].value:.1f}")
