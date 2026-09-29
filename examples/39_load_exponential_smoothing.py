"""Example: Exponential smoothing forecast.

Weighted average with exponential decay — more weight on recent observations.
"""
from dcc.forecasting.load import ExponentialSmoothingForecaster, LoadObservation
from datetime import datetime, timedelta

base = datetime(2026, 1, 1)
obs = [LoadObservation(timestamp=base + timedelta(hours=i), value=120 + (i % 24) * 3) for i in range(72)]
forecaster = ExponentialSmoothingForecaster(alpha=0.3)
result = forecaster.forecast(obs, horizon=24)
print(f"Model: {result.model_name}")
print(f"Training points: {result.training_points}")
for p in result.points[:5]:
    print(f"  {p.timestamp}: {p.predicted:.1f} kW")
