"""Statistical anomaly detection for telemetry data.

Provides z-score, IQR, and seasonal decomposition methods for detecting
anomalies in univariate time-series telemetry. Pure-Python implementation
with no external dependencies.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Anomaly:
    """A single detected anomaly."""
    index: int
    timestamp: float | None
    value: float
    expected: float
    deviation: float
    method: str
    severity: str  # "low", "medium", "high"


@dataclass
class AnomalyReport:
    """Aggregate report from an anomaly detection run."""
    method: str
    total_points: int
    anomalies: list[Anomaly] = field(default_factory=list)
    statistics: dict[str, float] = field(default_factory=dict)

    @property
    def anomaly_count(self) -> int:
        return len(self.anomalies)

    @property
    def anomaly_rate(self) -> float:
        return self.anomaly_count / self.total_points if self.total_points else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "total_points": self.total_points,
            "anomaly_count": self.anomaly_count,
            "anomaly_rate": round(self.anomaly_rate, 6),
            "statistics": {k: round(v, 6) for k, v in self.statistics.items()},
            "anomalies": [
                {
                    "index": a.index,
                    "timestamp": a.timestamp,
                    "value": round(a.value, 6),
                    "expected": round(a.expected, 6),
                    "deviation": round(a.deviation, 6),
                    "method": a.method,
                    "severity": a.severity,
                }
                for a in self.anomalies
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_series(values: Sequence[float]) -> list[float]:
    """Convert and validate a sequence of numeric values."""
    if not values:
        raise ValueError("values must not be empty")
    result = []
    for v in values:
        if v is None:
            raise ValueError("values must not contain None")
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric value: {v!r}") from exc
        if math.isnan(f) or math.isinf(f):
            raise ValueError(f"non-finite value: {v!r}")
        result.append(f)
    return result


def _validate_timestamps(
    timestamps: Sequence[float] | None, expected_len: int
) -> list[float | None]:
    """Validate and normalize timestamps."""
    if timestamps is None:
        return [None] * expected_len
    if len(timestamps) != expected_len:
        raise ValueError(
            f"timestamps length ({len(timestamps)}) must match values length ({expected_len})"
        )
    result: list[float | None] = []
    for t in timestamps:
        if t is None:
            result.append(None)
        else:
            try:
                result.append(float(t))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"non-numeric timestamp: {t!r}") from exc
    return result


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile (same method as numpy's default)."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    rank = (p / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _classify_severity(deviation_ratio: float) -> str:
    """Classify anomaly severity based on deviation ratio."""
    if deviation_ratio >= 4.0:
        return "high"
    if deviation_ratio >= 2.0:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Z-Score Anomaly Detection
# ---------------------------------------------------------------------------


def zscore_detect(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    threshold: float = 3.0,
    window: int | None = None,
) -> AnomalyReport:
    """Detect anomalies using z-score (standard score) method.

    Args:
        values: Numeric time-series values.
        timestamps: Optional timestamps corresponding to values.
        threshold: Z-score threshold (default 3.0). Points with
            |z-score| > threshold are flagged.
        window: If set, use a rolling window of this many points for
            local mean/std instead of global statistics. Useful for
            non-stationary series.

    Returns:
        AnomalyReport with detected anomalies and summary statistics.
    """
    vals = _validate_series(values)
    ts = _validate_timestamps(timestamps, len(vals))
    if threshold <= 0:
        raise ValueError("threshold must be positive")
    if window is not None and window < 2:
        raise ValueError("window must be at least 2")

    anomalies: list[Anomaly] = []
    n = len(vals)

    if window is None:
        # Global z-score
        mean = statistics.fmean(vals)
        std = statistics.stdev(vals) if n > 1 else 0.0
        if std == 0:
            return AnomalyReport(
                method="zscore",
                total_points=n,
                statistics={"mean": mean, "std": 0.0, "threshold": threshold},
            )
        for i, v in enumerate(vals):
            z = (v - mean) / std
            if abs(z) > threshold:
                anomalies.append(
                    Anomaly(
                        index=i,
                        timestamp=ts[i],
                        value=v,
                        expected=mean,
                        deviation=z,
                        method="zscore",
                        severity=_classify_severity(abs(z)),
                    )
                )
        return AnomalyReport(
            method="zscore",
            total_points=n,
            anomalies=anomalies,
            statistics={
                "mean": round(mean, 6),
                "std": round(std, 6),
                "threshold": threshold,
            },
        )
    else:
        # Rolling z-score
        anomalies = []
        for i in range(n):
            start = max(0, i - window + 1)
            window_vals = vals[start : i + 1]
            if len(window_vals) < 2:
                continue
            mean = statistics.fmean(window_vals)
            std = statistics.stdev(window_vals)
            if std == 0:
                continue
            z = (vals[i] - mean) / std
            if abs(z) > threshold:
                anomalies.append(
                    Anomaly(
                        index=i,
                        timestamp=ts[i],
                        value=vals[i],
                        expected=mean,
                        deviation=z,
                        method="zscore_rolling",
                        severity=_classify_severity(abs(z)),
                    )
                )
        all_mean = statistics.fmean(vals)
        all_std = statistics.stdev(vals) if n > 1 else 0.0
        return AnomalyReport(
            method="zscore_rolling",
            total_points=n,
            anomalies=anomalies,
            statistics={
                "mean": round(all_mean, 6),
                "std": round(all_std, 6),
                "threshold": threshold,
                "window": window,
            },
        )


# ---------------------------------------------------------------------------
# IQR Anomaly Detection
# ---------------------------------------------------------------------------


def iqr_detect(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    k: float = 1.5,
) -> AnomalyReport:
    """Detect anomalies using the Interquartile Range (IQR) method.

    Values outside [Q1 - k*IQR, Q3 + k*IQR] are flagged as anomalies.
    The default k=1.5 is Tukey's standard for outlier detection.

    Args:
        values: Numeric time-series values.
        timestamps: Optional timestamps corresponding to values.
        k: IQR multiplier (default 1.5). Use 3.0 for "extreme" outliers.

    Returns:
        AnomalyReport with detected anomalies and summary statistics.
    """
    vals = _validate_series(values)
    ts = _validate_timestamps(timestamps, len(vals))
    if k <= 0:
        raise ValueError("k must be positive")

    sorted_vals = sorted(vals)
    q1 = _percentile(sorted_vals, 25)
    q3 = _percentile(sorted_vals, 75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr

    anomalies: list[Anomaly] = []
    for i, v in enumerate(vals):
        if v < lower or v > upper:
            # Deviation as distance beyond the nearest fence, in IQR units
            if v < lower:
                dev = (lower - v) / iqr if iqr > 0 else float("inf")
                expected = q1
            else:
                dev = (v - upper) / iqr if iqr > 0 else float("inf")
                expected = q3
            anomalies.append(
                Anomaly(
                    index=i,
                    timestamp=ts[i],
                    value=v,
                    expected=expected,
                    deviation=round(dev, 6),
                    method="iqr",
                    severity=_classify_severity(dev),
                )
            )

    return AnomalyReport(
        method="iqr",
        total_points=len(vals),
        anomalies=anomalies,
        statistics={
            "q1": round(q1, 6),
            "q3": round(q3, 6),
            "iqr": round(iqr, 6),
            "lower_fence": round(lower, 6),
            "upper_fence": round(upper, 6),
            "k": k,
        },
    )


# ---------------------------------------------------------------------------
# Seasonal Decomposition Anomaly Detection
# ---------------------------------------------------------------------------


def _moving_average(values: list[float], period: int) -> list[float]:
    """Centered moving average for even/odd period lengths."""
    n = len(values)
    result: list[float] = []
    half = period // 2
    for i in range(n):
        if period % 2 == 1:
            # Odd period: symmetric window
            start = i - half
            end = i + half + 1
        else:
            # Even period: asymmetric window, then smooth
            start = i - half
            end = i + half
        start = max(0, start)
        end = min(n, end)
        window = values[start:end]
        result.append(statistics.fmean(window) if window else values[i])
    return result


def _detrend(values: list[float], trend: list[float]) -> list[float]:
    """Remove trend component (additive model)."""
    return [v - t for v, t in zip(values, trend)]


def _extract_seasonal(
    detrended: list[float], period: int
) -> list[float]:
    """Extract seasonal component by averaging detrended values at each phase."""
    n = len(detrended)
    phase_sums: list[float] = [0.0] * period
    phase_counts: list[int] = [0] * period
    for i, v in enumerate(detrended):
        phase = i % period
        phase_sums[phase] += v
        phase_counts[phase] += 1
    seasonal_means = [
        phase_sums[p] / phase_counts[p] if phase_counts[p] > 0 else 0.0
        for p in range(period)
    ]
    # Center the seasonal component (mean = 0 for additive model)
    seasonal_mean = statistics.fmean(seasonal_means)
    seasonal_means = [s - seasonal_mean for s in seasonal_means]
    # Expand to full length
    return [seasonal_means[i % period] for i in range(n)]


def _compute_residual(
    values: list[float], trend: list[float], seasonal: list[float]
) -> list[float]:
    """Compute residual = actual - trend - seasonal."""
    return [v - t - s for v, t, s in zip(values, trend, seasonal)]


def seasonal_decompose_detect(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    period: int = 24,
    threshold: float = 3.0,
) -> AnomalyReport:
    """Detect anomalies via seasonal decomposition.

    Decomposes the series into trend + seasonal + residual (additive model),
    then applies z-score detection on the residual component.

    Args:
        values: Numeric time-series values.
        timestamps: Optional timestamps corresponding to values.
        period: Seasonal period length (e.g., 24 for hourly data with
            daily seasonality, 7 for daily data with weekly seasonality).
        threshold: Z-score threshold for residual anomalies (default 3.0).

    Returns:
        AnomalyReport with detected anomalies and decomposition statistics.
    """
    vals = _validate_series(values)
    ts = _validate_timestamps(timestamps, len(vals))
    if period < 2:
        raise ValueError("period must be at least 2")
    if len(vals) < period * 2:
        raise ValueError(
            f"need at least 2 full periods ({period * 2} points) for seasonal decomposition, "
            f"got {len(vals)}"
        )
    if threshold <= 0:
        raise ValueError("threshold must be positive")

    # Step 1: Estimate trend via centered moving average
    trend = _moving_average(vals, period)

    # Step 2: Detrend
    detrended = _detrend(vals, trend)

    # Step 3: Extract seasonal component
    seasonal = _extract_seasonal(detrended, period)

    # Step 4: Compute residual
    residual = _compute_residual(vals, trend, seasonal)

    # Step 5: Z-score on residual
    res_mean = statistics.fmean(residual)
    res_std = statistics.stdev(residual) if len(residual) > 1 else 0.0

    anomalies: list[Anomaly] = []
    if res_std > 0:
        for i, r in enumerate(residual):
            z = (r - res_mean) / res_std
            if abs(z) > threshold:
                expected = trend[i] + seasonal[i]
                anomalies.append(
                    Anomaly(
                        index=i,
                        timestamp=ts[i],
                        value=vals[i],
                        expected=round(expected, 6),
                        deviation=round(z, 6),
                        method="seasonal_decompose",
                        severity=_classify_severity(abs(z)),
                    )
                )

    return AnomalyReport(
        method="seasonal_decompose",
        total_points=len(vals),
        anomalies=anomalies,
        statistics={
            "period": period,
            "threshold": threshold,
            "residual_mean": round(res_mean, 6),
            "residual_std": round(res_std, 6),
            "trend_mean": round(statistics.fmean(trend), 6),
            "seasonal_amplitude": round(max(seasonal) - min(seasonal), 6),
        },
    )


# ---------------------------------------------------------------------------
# Convenience: run all methods
# ---------------------------------------------------------------------------


def detect_all(
    values: Sequence[float],
    timestamps: Sequence[float] | None = None,
    *,
    zscore_threshold: float = 3.0,
    zscore_window: int | None = None,
    iqr_k: float = 1.5,
    seasonal_period: int = 24,
    seasonal_threshold: float = 3.0,
) -> dict[str, AnomalyReport]:
    """Run all three anomaly detection methods and return combined results.

    Returns:
        Dictionary with keys "zscore", "iqr", "seasonal" mapping to
        their respective AnomalyReport objects.
    """
    return {
        "zscore": zscore_detect(
            values, timestamps, threshold=zscore_threshold, window=zscore_window
        ),
        "iqr": iqr_detect(values, timestamps, k=iqr_k),
        "seasonal": seasonal_decompose_detect(
            values, timestamps, period=seasonal_period, threshold=seasonal_threshold
        ),
    }
