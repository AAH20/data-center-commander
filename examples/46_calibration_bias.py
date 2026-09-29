"""Example: Bias correction calibration.

Adjusts forecasts by the mean error of recent predictions.
"""
from dcc.forecasting.calibration import (
    ForecastPoint, ActualPoint, match_forecast_actual_pairs,
    apply_bias_correction, CalibrationMethod,
)

forecasts = [ForecastPoint(timestamp=i, value=100 + i * 2) for i in range(10)]
actuals = [ActualPoint(timestamp=i, value=95 + i * 2) for i in range(10)]
pairs = match_forecast_actual_pairs(forecasts, actuals)
calibrated = apply_bias_correction(pairs, forecasts)
print(f"Bias: {calibrated.bias:.2f}")
print(f"Scale factor: {calibrated.scale_factor:.4f}")
print(f"Sufficient data: {calibrated.sufficient_data}")
