"""Example: Moving average load forecast.

Simple forecasting using a rolling window average.
"""
from dcc.forecasting.load import MovingAverageForecaster, LoadObservation
from datetime import datetime, timedelta

# Generate sample data
base = datetime(2026, 1, 1)
obs = [LoadObservation(timestamp=base + timedelta(hours=i), value=100 + i * 0.5) for i in range(48)]
forecaster = MovingAverageForecaster(window=6)
result = forecaster.forecast(obs, horizon=12)
print(f"Model: {result.model_name}")
for p in result.points:
    print(f"  {p.timestamp}: {p.predicted:.1f} kW")
