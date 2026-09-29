"""Capacity demand forecasting for Data Center Commander.

Predicts future capacity requirements from historical capacity snapshots.
All forecasts are advisory, read-only, and carry provenance + quality status.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

# Capacity dimensions that can be forecastable
FORECASTABLE_DIMENSIONS = frozenset({
    "power_kw",
    "cooling_kw",
    "rack_u",
    "network_gbps",
    "storage_tb",
    "cpu_cores",
    "gpu_units",
    "water_m3_day",
    "fuel_hours",
})

# Minimum data points required for each method
MIN_POINTS_LINEAR = 3
MIN_POINTS_MOVING_AVG = 2
MIN_POINTS_EXP_SMOOTHING = 3

# Quality thresholds
MAX_DAILY_GROWTH_RATE = 0.5  # 50% daily growth is suspicious
MIN_COVERAGE_FOR_FORECAST = 0.5  # At least 50% of days must have data


@dataclass
class CapacityDataPoint:
    """A single capacity observation."""
    observed_at: datetime
    usable: float
    reserved: float
    policy_reserve: float
    forecast_peak: float | None
    quality_status: str
    scenario: str

    @property
    def committed(self) -> float:
        """Total committed capacity (reserved + policy reserve)."""
        return self.reserved + self.policy_reserve

    @property
    def headroom(self) -> float:
        """Remaining headroom (usable - committed)."""
        return self.usable - self.committed

    @property
    def utilization(self) -> float:
        """Utilization ratio (committed / usable)."""
        if self.usable <= 0:
            return 0.0
        return self.committed / self.usable


@dataclass
class ForecastPoint:
    """A single forecast data point."""
    target_date: datetime
    predicted_value: float
    lower_bound: float
    upper_bound: float
    method: str
    confidence: float  # 0.0 to 1.0


@dataclass
class CapacityForecast:
    """Complete forecast result for one dimension."""
    facility_id: str
    dimension: str
    unit: str
    scenario: str
    method: str
    generated_at: datetime
    data_points_used: int
    history_start: datetime
    history_end: datetime
    forecast_horizon_days: int
    forecast_points: list[ForecastPoint] = field(default_factory=list)
    quality_status: str = "estimated"
    reason_codes: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    execution_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for API response."""
        return {
            "facility_id": self.facility_id,
            "dimension": self.dimension,
            "unit": self.unit,
            "scenario": self.scenario,
            "method": self.method,
            "generated_at": self.generated_at.isoformat(),
            "data_points_used": self.data_points_used,
            "history_start": self.history_start.isoformat(),
            "history_end": self.history_end.isoformat(),
            "forecast_horizon_days": self.forecast_horizon_days,
            "forecast_points": [
                {
                    "target_date": p.target_date.isoformat(),
                    "predicted_value": round(p.predicted_value, 6),
                    "lower_bound": round(p.lower_bound, 6),
                    "upper_bound": round(p.upper_bound, 6),
                    "method": p.method,
                    "confidence": round(p.confidence, 4),
                }
                for p in self.forecast_points
            ],
            "quality_status": self.quality_status,
            "reason_codes": self.reason_codes,
            "provenance": self.provenance,
            "execution_permitted": self.execution_permitted,
        }


def _validate_dimension(dimension: str) -> None:
    """Validate that a dimension is forecastable."""
    if dimension not in FORECASTABLE_DIMENSIONS:
        raise ValueError(
            f"dimension must be one of {sorted(FORECASTABLE_DIMENSIONS)}, got {dimension!r}"
        )


def _validate_horizon(horizon_days: int) -> None:
    """Validate forecast horizon."""
    if not isinstance(horizon_days, int) or isinstance(horizon_days, bool):
        raise ValueError("horizon_days must be an integer")
    if not 1 <= horizon_days <= 365:
        raise ValueError("horizon_days must be between 1 and 365")


def _validate_data_points(points: list[CapacityDataPoint], method: str) -> None:
    """Validate that we have enough data points for the chosen method."""
    if not points:
        raise ValueError("at least one data point is required")

    min_required = {
        "linear": MIN_POINTS_LINEAR,
        "moving_average": MIN_POINTS_MOVING_AVG,
        "exponential_smoothing": MIN_POINTS_EXP_SMOOTHING,
    }.get(method, 3)

    if len(points) < min_required:
        raise ValueError(
            f"method {method!r} requires at least {min_required} data points, "
            f"got {len(points)}"
        )


def _compute_linear_trend(points: list[CapacityDataPoint]) -> tuple[float, float, float]:
    """Compute linear trend (slope, intercept, r_squared) using least squares.

    Uses day index as the independent variable.
    """
    if len(points) < 2:
        return 0.0, points[0].usable if points else 0.0, 0.0

    # Convert dates to day indices (relative to first point)
    base_date = points[0].observed_at
    x_values = [(p.observed_at - base_date).total_seconds() / 86400.0 for p in points]
    y_values = [p.usable for p in points]

    n = len(x_values)
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_x2 = sum(x * x for x in x_values)
    sum_y2 = sum(y * y for y in y_values)

    denominator = n * sum_x2 - sum_x * sum_x
    if abs(denominator) < 1e-10:
        # All x values are the same; return mean
        mean_y = sum_y / n
        return 0.0, mean_y, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    # R-squared
    ss_tot = sum_y2 - (sum_y * sum_y) / n
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0

    return slope, intercept, max(0.0, min(1.0, r_squared))


def _compute_moving_average(points: list[CapacityDataPoint], window: int = 3) -> float:
    """Compute simple moving average of the last `window` points."""
    if not points:
        return 0.0
    recent = points[-window:]
    return sum(p.usable for p in recent) / len(recent)


def _compute_exponential_smoothing(
    points: list[CapacityDataPoint], alpha: float = 0.3
) -> float:
    """Compute exponential smoothing forecast."""
    if not points:
        return 0.0
    if len(points) == 1:
        return points[0].usable

    smoothed = points[0].usable
    for p in points[1:]:
        smoothed = alpha * p.usable + (1 - alpha) * smoothed
    return smoothed


def _compute_volatility(points: list[CapacityDataPoint]) -> float:
    """Compute coefficient of variation (std dev / mean) of usable values."""
    if len(points) < 2:
        return 0.0
    values = [p.usable for p in points]
    mean_val = sum(values) / len(values)
    if abs(mean_val) < 1e-10:
        return 0.0
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)
    return std_dev / abs(mean_val)


def _assess_quality(
    points: list[CapacityDataPoint],
    method: str,
    r_squared: float,
    volatility: float,
) -> tuple[str, list[str]]:
    """Assess forecast quality and return (quality_status, reason_codes)."""
    reasons: list[str] = []

    # Check data recency
    now = datetime.now(timezone.utc)
    latest = max(p.observed_at for p in points)
    age_days = (now - latest).days
    if age_days > 30:
        reasons.append(f"data_stale_{age_days}d")

    # Check data coverage
    if len(points) >= 2:
        date_range = (max(p.observed_at for p in points) - min(p.observed_at for p in points)).days
        if date_range > 0:
            coverage = len(points) / (date_range + 1)
            if coverage < MIN_COVERAGE_FOR_FORECAST:
                reasons.append(f"low_coverage_{coverage:.2f}")

    # Check for suspicious growth rates
    if len(points) >= 2:
        sorted_points = sorted(points, key=lambda p: p.observed_at)
        for i in range(1, len(sorted_points)):
            prev = sorted_points[i - 1].usable
            curr = sorted_points[i].usable
            days_diff = (sorted_points[i].observed_at - sorted_points[i - 1].observed_at).days
            if days_diff > 0 and prev > 0:
                daily_growth = (curr - prev) / prev / days_diff
                if abs(daily_growth) > MAX_DAILY_GROWTH_RATE:
                    reasons.append("suspicious_growth_rate")
                    break

    # Method-specific quality checks
    if method == "linear" and r_squared < 0.3:
        reasons.append("poor_linear_fit")
    if volatility > 0.5:
        reasons.append("high_volatility")

    # Determine overall quality
    if not reasons:
        quality = "good"
    elif all(r.startswith("data_stale") for r in reasons):
        quality = "estimated"
    elif any(r in ("suspicious_growth_rate", "high_volatility") for r in reasons):
        quality = "suspect"
    else:
        quality = "estimated"

    return quality, reasons


def _generate_forecast_points(
    points: list[CapacityDataPoint],
    method: str,
    horizon_days: int,
    slope: float,
    intercept: float,
    r_squared: float,
    volatility: float,
) -> list[ForecastPoint]:
    """Generate forecast points for each day in the horizon."""
    if not points:
        return []

    base_date = points[0].observed_at
    last_date = max(p.observed_at for p in points)
    last_value = points[-1].usable

    # Compute prediction interval multiplier based on volatility and R-squared
    # Higher volatility or lower R-squared = wider intervals
    base_multiplier = 1.0 + volatility * 2.0
    confidence_factor = max(0.1, r_squared)

    forecast_points: list[ForecastPoint] = []

    for day_offset in range(1, horizon_days + 1):
        target_date = last_date + timedelta(days=day_offset)
        days_from_base = (target_date - base_date).total_seconds() / 86400.0

        if method == "linear":
            predicted = slope * days_from_base + intercept
        elif method == "moving_average":
            predicted = last_value  # Flat forecast from moving average
        elif method == "exponential_smoothing":
            predicted = last_value  # Flat forecast from smoothing
        else:
            predicted = last_value

        # Ensure non-negative for capacity
        predicted = max(0.0, predicted)

        # Uncertainty grows with horizon; always include a minimum margin
        uncertainty_factor = base_multiplier * (1.0 + day_offset / 30.0)
        margin = predicted * (1.0 - confidence_factor) * uncertainty_factor
        # Ensure minimum 5% margin even with perfect fit
        min_margin = predicted * 0.05
        margin = max(margin, min_margin)

        lower_bound = max(0.0, predicted - margin)
        upper_bound = predicted + margin

        # Confidence decreases with horizon
        confidence = max(0.1, confidence_factor * (1.0 - day_offset / (horizon_days * 2.0)))

        forecast_points.append(
            ForecastPoint(
                target_date=target_date,
                predicted_value=predicted,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                method=method,
                confidence=confidence,
            )
        )

    return forecast_points


def forecast_capacity(
    *,
    facility_id: str,
    dimension: str,
    unit: str,
    scenario: str,
    data_points: list[CapacityDataPoint],
    horizon_days: int = 30,
    method: Literal["linear", "moving_average", "exponential_smoothing"] = "linear",
) -> CapacityForecast:
    """Generate a capacity demand forecast.

    Args:
        facility_id: Facility identifier.
        dimension: Capacity dimension (e.g., 'power_kw').
        unit: Unit of measurement (e.g., 'kW').
        scenario: Scenario name (e.g., 'baseline', 'growth').
        data_points: Historical capacity observations.
        horizon_days: Number of days to forecast (1-365).
        method: Forecasting method to use.

    Returns:
        CapacityForecast with predictions, confidence intervals, and quality status.
    """
    _validate_dimension(dimension)
    _validate_horizon(horizon_days)
    _validate_data_points(data_points, method)

    # Sort by date
    sorted_points = sorted(data_points, key=lambda p: p.observed_at)

    # Compute trend
    slope, intercept, r_squared = _compute_linear_trend(sorted_points)
    volatility = _compute_volatility(sorted_points)

    # Generate forecast points
    forecast_points = _generate_forecast_points(
        sorted_points, method, horizon_days, slope, intercept, r_squared, volatility
    )

    # Assess quality
    quality_status, reason_codes = _assess_quality(sorted_points, method, r_squared, volatility)

    # Build provenance
    provenance = {
        "source": "capacity_snapshots",
        "method": method,
        "data_points": len(sorted_points),
        "history_days": (sorted_points[-1].observed_at - sorted_points[0].observed_at).days,
        "r_squared": round(r_squared, 6),
        "volatility": round(volatility, 6),
        "slope_per_day": round(slope, 6),
        "synthetic": all(
            p.quality_status in ("estimated", "suspect") for p in sorted_points
        ),
        "label": "ADVISORY FORECAST - NOT FOR AUTONOMOUS EXECUTION",
    }

    return CapacityForecast(
        facility_id=facility_id,
        dimension=dimension,
        unit=unit,
        scenario=scenario,
        method=method,
        generated_at=datetime.now(timezone.utc),
        data_points_used=len(sorted_points),
        history_start=sorted_points[0].observed_at,
        history_end=sorted_points[-1].observed_at,
        forecast_horizon_days=horizon_days,
        forecast_points=forecast_points,
        quality_status=quality_status,
        reason_codes=reason_codes,
        provenance=provenance,
        execution_permitted=False,
    )


def forecast_from_snapshots(
    *,
    facility_id: str,
    dimension: str,
    unit: str,
    scenario: str,
    snapshots: list[dict[str, Any]],
    horizon_days: int = 30,
    method: Literal["linear", "moving_average", "exponential_smoothing"] = "linear",
) -> CapacityForecast:
    """Generate a forecast from raw snapshot dictionaries.

    Args:
        facility_id: Facility identifier.
        dimension: Capacity dimension.
        unit: Unit of measurement.
        scenario: Scenario name.
        snapshots: List of snapshot dicts with keys: observed_at, usable, reserved,
                   policy_reserve, forecast_peak, quality_status, scenario.
        horizon_days: Number of days to forecast.
        method: Forecasting method.

    Returns:
        CapacityForecast result.
    """
    data_points: list[CapacityDataPoint] = []
    for snap in snapshots:
        try:
            observed_at = snap["observed_at"]
            if isinstance(observed_at, str):
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            elif isinstance(observed_at, datetime) and observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)

            data_points.append(
                CapacityDataPoint(
                    observed_at=observed_at,
                    usable=float(snap.get("usable", 0)),
                    reserved=float(snap.get("reserved", 0)),
                    policy_reserve=float(snap.get("policy_reserve", 0)),
                    forecast_peak=float(snap["forecast_peak"]) if snap.get("forecast_peak") is not None else None,
                    quality_status=str(snap.get("quality_status", "unknown")),
                    scenario=str(snap.get("scenario", "unknown")),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue

    return forecast_capacity(
        facility_id=facility_id,
        dimension=dimension,
        unit=unit,
        scenario=scenario,
        data_points=data_points,
        horizon_days=horizon_days,
        method=method,
    )


def select_best_method(points: list[CapacityDataPoint]) -> str:
    """Select the best forecasting method based on data characteristics.

    Returns one of: 'linear', 'moving_average', 'exponential_smoothing'.
    """
    if len(points) < MIN_POINTS_MOVING_AVG:
        return "moving_average"

    if len(points) < MIN_POINTS_LINEAR:
        return "moving_average"

    # Check if linear trend fits well
    _, _, r_squared = _compute_linear_trend(points)
    if r_squared >= 0.5:
        return "linear"

    # Check volatility
    volatility = _compute_volatility(points)
    if volatility > 0.3:
        return "exponential_smoothing"

    return "moving_average"


def compute_capacity_at_risk(
    forecast: CapacityForecast,
    threshold: float,
) -> dict[str, Any]:
    """Identify dates where forecast exceeds a threshold.

    Args:
        forecast: A CapacityForecast result.
        threshold: Capacity threshold value.

    Returns:
        Dict with at_risk dates and severity assessment.
    """
    at_risk_dates: list[dict[str, Any]] = []

    for point in forecast.forecast_points:
        if point.predicted_value >= threshold:
            at_risk_dates.append(
                {
                    "date": point.target_date.isoformat(),
                    "predicted_value": round(point.predicted_value, 6),
                    "upper_bound": round(point.upper_bound, 6),
                    "confidence": round(point.confidence, 4),
                }
            )

    # Determine severity
    if not at_risk_dates:
        severity = "none"
    elif len(at_risk_dates) <= 3:
        severity = "low"
    elif len(at_risk_dates) <= 7:
        severity = "medium"
    else:
        severity = "high"

    return {
        "threshold": threshold,
        "dimension": forecast.dimension,
        "facility_id": forecast.facility_id,
        "at_risk_dates": at_risk_dates,
        "at_risk_count": len(at_risk_dates),
        "severity": severity,
        "first_at_risk": at_risk_dates[0]["date"] if at_risk_dates else None,
        "execution_permitted": False,
    }
