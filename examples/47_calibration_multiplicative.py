"""Example: Multiplicative calibration.

Scales forecasts by the ratio of actual to predicted.
"""
from dcc.forecasting.calibration import (
    ForecastPoint, ActualPoint, match_forecast_actual_pairs,
    apply_multiplicative_correction,
)

forecasts = [ForecastPoint(timestamp=i, value=100) for i in range(10)]
actuals = [ActualPoint(timestamp=i, value=110) for i in range(10)]
pairs = match_forecast_actual_pairs(forecasts, actuals)
calibrated = apply_multiplicative_correction(pairs, forecasts)
print(f"Scale factor: {calibrated.scale_factor:.4f}")
for f in calibrated.calibrated_forecasts[:3]:
    print(f"  t={f.timestamp}: {f.value:.1f}")
