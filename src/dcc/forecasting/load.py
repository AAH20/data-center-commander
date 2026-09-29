"""ML-based energy load forecasting for Data Center Commander.

Pure-stdlib implementation: no numpy / pandas / sklearn required.
Models: moving average, exponential smoothing, Holt-Winters, linear trend.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoadObservation:
    """A single energy load observation."""
    timestamp: datetime
    value: float
    unit: str = "kW"
    quality: str = "good"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForecastPoint:
    """A single forecast point with optional confidence interval."""
    timestamp: datetime
    predicted: float
    lower_bound: float | None = None
    upper_bound: float | None = None


@dataclass
class ForecastResult:
    """Result of a forecast operation."""
    model_name: str
    points: list[ForecastPoint]
    metrics: dict[str, float] = field(default_factory=dict)
    training_points: int = 0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def aggregate_to_hourly(
    observations: Sequence[LoadObservation],
) -> list[LoadObservation]:
    """Aggregate sub-hourly observations into hourly averages."""
    if not observations:
        return []
    buckets: dict[datetime, list[float]] = {}
    for obs in observations:
        hour_key = obs.timestamp.replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(hour_key, []).append(obs.value)
    result = []
    for ts in sorted(buckets):
        vals = buckets[ts]
        result.append(LoadObservation(
            timestamp=ts,
            value=statistics.fmean(vals),
            unit=observations[0].unit,
            quality="aggregated",
        ))
    return result


def aggregate_to_daily(
    observations: Sequence[LoadObservation],
) -> list[LoadObservation]:
    """Aggregate observations into daily averages."""
    if not observations:
        return []
    buckets: dict[datetime, list[float]] = {}
    for obs in observations:
        day_key = obs.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets.setdefault(day_key, []).append(obs.value)
    result = []
    for ts in sorted(buckets):
        vals = buckets[ts]
        result.append(LoadObservation(
            timestamp=ts,
            value=statistics.fmean(vals),
            unit=observations[0].unit,
            quality="aggregated",
        ))
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    actual: Sequence[float],
    predicted: Sequence[float],
) -> dict[str, float]:
    """Compute MAE, RMSE, MAPE, and R²."""
    n = min(len(actual), len(predicted))
    if n == 0:
        return {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "r2": 0.0, "n": 0}
    pairs = list(zip(actual[:n], predicted[:n]))
    mae = statistics.fmean(abs(a - p) for a, p in pairs)
    rmse = math.sqrt(statistics.fmean((a - p) ** 2 for a, p in pairs))
    mape_vals = [abs((a - p) / a) * 100 for a, p in pairs if a != 0]
    mape = statistics.fmean(mape_vals) if mape_vals else 0.0
    mean_actual = statistics.fmean(a for a, _ in pairs)
    ss_tot = sum((a - mean_actual) ** 2 for a, _ in pairs)
    ss_res = sum((a - p) ** 2 for a, p in pairs)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2, "n": float(n)}


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    observations: Sequence[LoadObservation],
    threshold_std: float = 3.0,
) -> list[LoadObservation]:
    """Detect anomalies using z-score method."""
    if len(observations) < 3:
        return []
    values = [o.value for o in observations]
    mean_val = statistics.fmean(values)
    std_val = statistics.stdev(values) if len(values) > 1 else 0.0
    if std_val == 0:
        return []
    anomalies = []
    for obs in observations:
        z = abs(obs.value - mean_val) / std_val
        if z > threshold_std:
            anomalies.append(LoadObservation(
                timestamp=obs.timestamp,
                value=obs.value,
                unit=obs.unit,
                quality="anomaly",
                metadata={**obs.metadata, "z_score": z},
            ))
    return anomalies


# ---------------------------------------------------------------------------
# Forecasters
# ---------------------------------------------------------------------------

class MovingAverageForecaster:
    """Simple moving average forecaster."""

    def __init__(self, window: int = 24):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window

    def forecast(
        self,
        history: Sequence[LoadObservation],
        horizon: int,
        interval_minutes: int = 60,
    ) -> ForecastResult:
        if not history:
            raise ValueError("history must not be empty")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        values = [o.value for o in history]
        w = min(self.window, len(values))
        ma = statistics.fmean(values[-w:])
        last_ts = history[-1].timestamp
        points = []
        for i in range(1, horizon + 1):
            ts = last_ts + timedelta(minutes=interval_minutes * i)
            points.append(ForecastPoint(timestamp=ts, predicted=ma))
        return ForecastResult(
            model_name=f"MA({self.window})",
            points=points,
            training_points=len(history),
        )


class ExponentialSmoothingForecaster:
    """Single exponential smoothing forecaster."""

    def __init__(self, alpha: float = 0.3):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha

    def forecast(
        self,
        history: Sequence[LoadObservation],
        horizon: int,
        interval_minutes: int = 60,
    ) -> ForecastResult:
        if not history:
            raise ValueError("history must not be empty")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        values = [o.value for o in history]
        smoothed = values[0]
        for v in values[1:]:
            smoothed = self.alpha * v + (1 - self.alpha) * smoothed
        last_ts = history[-1].timestamp
        points = []
        for i in range(1, horizon + 1):
            ts = last_ts + timedelta(minutes=interval_minutes * i)
            points.append(ForecastPoint(timestamp=ts, predicted=smoothed))
        return ForecastResult(
            model_name=f"ES(alpha={self.alpha})",
            points=points,
            training_points=len(history),
        )


class HoltWintersForecaster:
    """Holt-Winters double exponential smoothing (trend + level)."""

    def __init__(self, alpha: float = 0.3, beta: float = 0.1):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        if not 0 < beta <= 1:
            raise ValueError("beta must be in (0, 1]")
        self.alpha = alpha
        self.beta = beta

    def forecast(
        self,
        history: Sequence[LoadObservation],
        horizon: int,
        interval_minutes: int = 60,
    ) -> ForecastResult:
        if len(history) < 2:
            raise ValueError("Holt-Winters requires at least 2 observations")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        values = [o.value for o in history]
        level = values[0]
        trend = values[1] - values[0]
        for v in values[1:]:
            prev_level = level
            level = self.alpha * v + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * trend
        last_ts = history[-1].timestamp
        points = []
        for i in range(1, horizon + 1):
            ts = last_ts + timedelta(minutes=interval_minutes * i)
            pred = level + i * trend
            points.append(ForecastPoint(timestamp=ts, predicted=pred))
        return ForecastResult(
            model_name=f"Holt(alpha={self.alpha},beta={self.beta})",
            points=points,
            training_points=len(history),
        )


class LinearTrendForecaster:
    """Simple linear regression forecaster."""

    def forecast(
        self,
        history: Sequence[LoadObservation],
        horizon: int,
        interval_minutes: int = 60,
    ) -> ForecastResult:
        if len(history) < 2:
            raise ValueError("Linear trend requires at least 2 observations")
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        n = len(history)
        values = [o.value for o in history]
        x_mean = (n - 1) / 2.0
        y_mean = statistics.fmean(values)
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        intercept = y_mean - slope * x_mean
        last_ts = history[-1].timestamp
        points = []
        for i in range(1, horizon + 1):
            ts = last_ts + timedelta(minutes=interval_minutes * i)
            pred = intercept + slope * (n - 1 + i)
            points.append(ForecastPoint(timestamp=ts, predicted=pred))
        return ForecastResult(
            model_name="LinearTrend",
            points=points,
            training_points=len(history),
        )


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def select_best_model(
    history: Sequence[LoadObservation],
    validation_split: float = 0.2,
    interval_minutes: int = 60,
) -> tuple[str, ForecastResult]:
    """Select the best model by backtesting on a validation split.

    Returns (model_name, forecast_on_full_history).
    """
    if len(history) < 5:
        raise ValueError("Need at least 5 observations for model selection")
    split_idx = max(2, int(len(history) * (1 - validation_split)))
    train = list(history[:split_idx])
    val = list(history[split_idx:])
    if not val:
        val = train[-1:]
        train = train[:-1]
    models = [
        MovingAverageForecaster(window=min(12, len(train))),
        ExponentialSmoothingForecaster(alpha=0.3),
        HoltWintersForecaster(alpha=0.3, beta=0.1),
        LinearTrendForecaster(),
    ]
    best_name = ""
    best_rmse = float("inf")
    best_forecaster = models[0]
    for model in models:
        try:
            result = model.forecast(train, len(val), interval_minutes)
            preds = [p.predicted for p in result.points]
            actuals = [o.value for o in val]
            metrics = compute_metrics(actuals, preds)
            if metrics["rmse"] < best_rmse:
                best_rmse = metrics["rmse"]
                best_name = result.model_name
                best_forecaster = model
        except (ValueError, ZeroDivisionError):
            continue
    # Re-train on full history
    horizon = max(1, len(val))
    final = best_forecaster.forecast(history, horizon, interval_minutes)
    final.model_name = best_name
    final.metrics["validation_rmse"] = best_rmse
    return best_name, final
