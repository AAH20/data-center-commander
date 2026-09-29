"""Forecast calibration: adjust forecasts using recent observed actuals.

Supports bias correction (additive) and multiplicative scaling.
Pure-Python, no external dependencies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class CalibrationMethod(str, Enum):
    """Calibration method selector."""

    NONE = "none"
    BIAS = "bias"
    MULTIPLICATIVE = "multiplicative"


@dataclass(frozen=True)
class ForecastPoint:
    """A single forecast prediction with optional prediction interval."""

    timestamp: float
    value: float
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True)
class ActualPoint:
    """A single observed actual value."""

    timestamp: float
    value: float


@dataclass(frozen=True)
class MatchedPair:
    """A forecast-actual pair matched by timestamp."""

    timestamp: float
    forecast: float
    actual: float
    error: float  # forecast - actual (positive = over-forecast)


@dataclass(frozen=True)
class CalibrationResult:
    """Result of calibrating forecasts against recent actuals."""

    method: CalibrationMethod
    pairs: list[MatchedPair]
    bias: float
    scale_factor: float
    metrics: dict[str, float] = field(default_factory=dict)
    calibrated_forecasts: list[ForecastPoint] = field(default_factory=list)
    sample_size: int = 0
    sufficient_data: bool = False


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def match_forecast_actual_pairs(
    forecasts: Sequence[ForecastPoint],
    actuals: Sequence[ActualPoint],
    *,
    tolerance: float = 0.0,
) -> list[MatchedPair]:
    """Match forecast points to actual points by timestamp.

    Args:
        forecasts: Forecast points to match.
        actuals: Observed actual points.
        tolerance: Maximum absolute timestamp difference for a match.
                   0.0 means exact match only.

    Returns:
        List of matched pairs sorted by timestamp.
    """
    if tolerance < 0:
        raise ValueError("tolerance must be >= 0")

    # Index actuals by timestamp for O(1) lookup
    actual_by_ts: dict[float, float] = {}
    for a in actuals:
        actual_by_ts[a.timestamp] = a.value

    pairs: list[MatchedPair] = []
    for f in forecasts:
        if tolerance == 0.0:
            if f.timestamp in actual_by_ts:
                actual_val = actual_by_ts[f.timestamp]
                pairs.append(
                    MatchedPair(
                        timestamp=f.timestamp,
                        forecast=f.value,
                        actual=actual_val,
                        error=f.value - actual_val,
                    )
                )
        else:
            # Find closest actual within tolerance
            best_ts: float | None = None
            best_dist = tolerance
            for ts in actual_by_ts:
                dist = abs(ts - f.timestamp)
                if dist <= best_dist:
                    best_dist = dist
                    best_ts = ts
            if best_ts is not None:
                actual_val = actual_by_ts[best_ts]
                pairs.append(
                    MatchedPair(
                        timestamp=f.timestamp,
                        forecast=f.value,
                        actual=actual_val,
                        error=f.value - actual_val,
                    )
                )

    pairs.sort(key=lambda p: p.timestamp)
    return pairs


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_calibration_metrics(pairs: Sequence[MatchedPair]) -> dict[str, float]:
    """Compute calibration error metrics from matched pairs.

    Returns a dict with: bias, mae, rmse, mape, smape, variance_ratio.
    """
    if not pairs:
        return {
            "bias": 0.0,
            "mae": 0.0,
            "rmse": 0.0,
            "mape": 0.0,
            "smape": 0.0,
            "variance_ratio": 1.0,
        }

    n = len(pairs)
    errors = [p.error for p in pairs]
    actuals = [p.actual for p in pairs]
    forecasts = [p.forecast for p in pairs]

    bias = sum(errors) / n
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e**2 for e in errors) / n)

    # MAPE: skip zero actuals
    mape_pairs = [(a, f) for a, f in zip(actuals, forecasts) if a != 0]
    mape = (
        sum(abs((a - f) / a) for a, f in mape_pairs) / len(mape_pairs) * 100.0
        if mape_pairs
        else 0.0
    )

    # SMAPE
    denom = sum(abs(a) + abs(f) for a, f in zip(actuals, forecasts))
    smape = (
        2.0 * sum(abs(a - f) for a, f in zip(actuals, forecasts)) / denom * 100.0
        if denom != 0
        else 0.0
    )

    # Variance ratio
    if n < 2:
        variance_ratio = 1.0
    else:
        mean_a = sum(actuals) / n
        mean_f = sum(forecasts) / n
        var_a = sum((a - mean_a) ** 2 for a in actuals) / (n - 1)
        var_f = sum((f - mean_f) ** 2 for f in forecasts) / (n - 1)
        if var_a == 0:
            variance_ratio = 1.0 if var_f == 0 else float("inf")
        else:
            variance_ratio = var_f / var_a

    return {
        "bias": bias,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "smape": smape,
        "variance_ratio": variance_ratio,
    }


# ---------------------------------------------------------------------------
# Calibration application
# ---------------------------------------------------------------------------


def apply_bias_correction(
    forecasts: Sequence[ForecastPoint],
    bias: float,
) -> list[ForecastPoint]:
    """Apply additive bias correction to forecasts.

    Subtracts the bias (mean error) from each forecast value.
    Also adjusts prediction interval bounds if present.
    """
    result: list[ForecastPoint] = []
    for f in forecasts:
        result.append(
            ForecastPoint(
                timestamp=f.timestamp,
                value=f.value - bias,
                lower=f.lower - bias if f.lower is not None else None,
                upper=f.upper - bias if f.upper is not None else None,
            )
        )
    return result


def apply_multiplicative_correction(
    forecasts: Sequence[ForecastPoint],
    scale_factor: float,
) -> list[ForecastPoint]:
    """Apply multiplicative scaling to forecasts.

    Multiplies each forecast value by the scale_factor.
    Also scales prediction interval bounds if present.
    """
    if scale_factor <= 0:
        raise ValueError("scale_factor must be > 0")

    result: list[ForecastPoint] = []
    for f in forecasts:
        result.append(
            ForecastPoint(
                timestamp=f.timestamp,
                value=f.value * scale_factor,
                lower=f.lower * scale_factor if f.lower is not None else None,
                upper=f.upper * scale_factor if f.upper is not None else None,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Main calibration entry point
# ---------------------------------------------------------------------------


def calibrate_forecasts(
    forecasts: Sequence[ForecastPoint],
    actuals: Sequence[ActualPoint],
    *,
    method: CalibrationMethod | str = CalibrationMethod.BIAS,
    min_samples: int = 3,
    tolerance: float = 0.0,
) -> CalibrationResult:
    """Calibrate forecasts using recent actuals.

    Args:
        forecasts: The forecast points to calibrate.
        actuals: Recent observed actual values.
        method: Calibration method — 'none', 'bias', or 'multiplicative'.
        min_samples: Minimum number of matched pairs required for calibration.
        tolerance: Timestamp matching tolerance (0 = exact match).

    Returns:
        CalibrationResult with calibrated forecasts and metrics.
    """
    if isinstance(method, str):
        try:
            method = CalibrationMethod(method)
        except ValueError:
            raise ValueError(
                f"unknown calibration method: {method!r}. "
                f"Choose from: {', '.join(m.value for m in CalibrationMethod)}"
            ) from None

    # Match forecast-actual pairs
    pairs = match_forecast_actual_pairs(forecasts, actuals, tolerance=tolerance)
    sample_size = len(pairs)
    sufficient_data = sample_size >= min_samples

    # Compute metrics
    metrics = compute_calibration_metrics(pairs)

    # Determine correction parameters
    bias = 0.0
    scale_factor = 1.0

    if sufficient_data and method == CalibrationMethod.BIAS:
        bias = metrics["bias"]
    elif sufficient_data and method == CalibrationMethod.MULTIPLICATIVE:
        # Scale factor = mean(actual) / mean(forecast)
        mean_actual = sum(p.actual for p in pairs) / sample_size
        mean_forecast = sum(p.forecast for p in pairs) / sample_size
        if mean_forecast != 0:
            scale_factor = mean_actual / mean_forecast

    # Apply correction
    if method == CalibrationMethod.BIAS and sufficient_data:
        calibrated = apply_bias_correction(forecasts, bias)
    elif method == CalibrationMethod.MULTIPLICATIVE and sufficient_data:
        calibrated = apply_multiplicative_correction(forecasts, scale_factor)
    else:
        calibrated = list(forecasts)

    return CalibrationResult(
        method=method,
        pairs=pairs,
        bias=bias,
        scale_factor=scale_factor,
        metrics=metrics,
        calibrated_forecasts=calibrated,
        sample_size=sample_size,
        sufficient_data=sufficient_data,
    )
