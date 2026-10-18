"""Example: Auto-select best forecasting model.

Compares multiple models and picks the one with lowest error.
"""
from dcc.forecasting.load import (
    MovingAverageForecaster, ExponentialSmoothingForecaster,
    LinearTrendForecaster, select_best_model, LoadObservation,
)
from datetime import datetime, timedelta

base = datetime(2026, 1, 1)
obs = [LoadObservation(timestamp=base + timedelta(hours=i), value=100 + i * 0.3 + (i % 12) * 2) for i in range(96)]
best_name, best_result = select_best_model(obs)
print(f"Best model: {best_name}")
print(f"Metrics: {best_result.metrics}")
