"""Time-series feature extraction engine for Data Center Commander.

Pure-stdlib implementation of rolling statistics, lag features, seasonal
decomposition, and trend detection. No external dependencies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollingStats:
    """Rolling window statistics for a single point."""

    index: int
    window_start: int
    window_end: int
    count: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    p05: float
    p95: float


@dataclass(frozen=True)
class LagFeature:
    """Lag feature at a specific offset."""

    index: int
    lag: int
    value: float | None


@dataclass(frozen=True)
class SeasonalDecomposition:
    """Classical additive seasonal decomposition result."""

    trend: list[float | None]
    seasonal: list[float]
    residual: list[float | None]
    period: int


@dataclass(frozen=True)
class TrendResult:
    """Trend detection summary."""

    slope: float
    intercept: float
    r_squared: float
    p_value: float | None
    direction: str  # "increasing", "decreasing", "flat"
    mann_kendall_tau: float | None = None
    mann_kendall_p: float | None = None
    change_points: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_series(values: Sequence[float]) -> list[float]:
    """Convert sequence to list of floats, rejecting non-finite values."""
    result: list[float] = []
    for v in values:
        if v is None:
            result.append(float("nan"))
        else:
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                result.append(float("nan"))
            else:
                result.append(f)
    return result


def _mean(xs: list[float]) -> float:
    """Arithmetic mean of a non-empty list."""
    return sum(xs) / len(xs)


def _std(xs: list[float], ddof: int = 1) -> float:
    """Sample standard deviation."""
    n = len(xs)
    if n <= ddof:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def _percentile(sorted_xs: list[float], p: float) -> float:
    """Linear-interpolation percentile (0-100) on a pre-sorted list."""
    n = len(sorted_xs)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_xs[0]
    k = (p / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_xs[int(k)]
    d = k - f
    return sorted_xs[f] * (1 - d) + sorted_xs[c] * d


def _median(xs: list[float]) -> float:
    """Median of a list."""
    s = sorted(xs)
    return _percentile(s, 50.0)


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Ordinary least squares: returns (slope, intercept, r_squared)."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    mx = _mean(xs)
    my = _mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0:
        return 0.0, my, 0.0
    slope = sxy / sxx
    intercept = my - slope * mx
    r_squared = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    return slope, intercept, r_squared


def _mann_kendall(ys: list[float]) -> tuple[float, float]:
    """Mann-Kendall trend test. Returns (tau, two-sided p-value)."""
    n = len(ys)
    if n < 3:
        return 0.0, 1.0
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = ys[j] - ys[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1
    # Variance with tie correction
    tie_counts: dict[float, int] = {}
    for y in ys:
        tie_counts[y] = tie_counts.get(y, 0) + 1
    var_s = (n * (n - 1) * (2 * n + 5)) / 18.0
    for t in tie_counts.values():
        if t > 1:
            var_s -= t * (t - 1) * (2 * t + 5) / 18.0
    if var_s <= 0:
        return 0.0, 1.0
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    # Two-sided p-value from normal approximation
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))
    tau = s / (n * (n - 1) / 2.0) if n > 1 else 0.0
    return tau, p


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# Rolling statistics
# ---------------------------------------------------------------------------


def rolling_stats(
    values: Sequence[float],
    window: int,
    *,
    min_periods: int | None = None,
) -> list[RollingStats]:
    """Compute rolling window statistics.

    Args:
        values: Input time series.
        window: Size of the rolling window (>= 1).
        min_periods: Minimum observations required to produce a result.
            Defaults to ``window`` (full window required).

    Returns:
        List of RollingStats, one per position where enough data exists.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if min_periods is None:
        min_periods = window
    if min_periods < 1:
        raise ValueError("min_periods must be >= 1")

    data = _validate_series(values)
    n = len(data)
    results: list[RollingStats] = []

    for i in range(n):
        start = max(0, i - window + 1)
        end = i + 1
        window_vals = [v for v in data[start:end] if not math.isnan(v)]
        if len(window_vals) < min_periods:
            continue
        s = sorted(window_vals)
        results.append(RollingStats(
            index=i,
            window_start=start,
            window_end=end,
            count=len(window_vals),
            mean=_mean(window_vals),
            std=_std(window_vals),
            min=s[0],
            max=s[-1],
            median=_median(window_vals),
            p05=_percentile(s, 5.0),
            p95=_percentile(s, 95.0),
        ))
    return results


# ---------------------------------------------------------------------------
# Lag features
# ---------------------------------------------------------------------------


def lag_features(
    values: Sequence[float],
    lags: Sequence[int],
) -> list[list[LagFeature]]:
    """Compute lag features for each time step.

    Args:
        values: Input time series.
        lags: List of positive integer lag offsets (e.g. [1, 2, 7]).

    Returns:
        A list (one entry per time step) of lists of LagFeature.
        Each inner list has one LagFeature per requested lag, in order.
        Lag values are ``None`` when the lag extends before the series start.
    """
    if not lags:
        raise ValueError("at least one lag must be specified")
    for lag in lags:
        if lag < 1:
            raise ValueError("lags must be positive integers")

    data = _validate_series(values)
    n = len(data)
    results: list[list[LagFeature]] = []

    for i in range(n):
        step: list[LagFeature] = []
        for lag in lags:
            idx = i - lag
            val = data[idx] if idx >= 0 and not math.isnan(data[idx]) else None
            step.append(LagFeature(index=i, lag=lag, value=val))
        results.append(step)
    return results


# ---------------------------------------------------------------------------
# Seasonal decomposition
# ---------------------------------------------------------------------------


def seasonal_decompose(
    values: Sequence[float],
    period: int,
) -> SeasonalDecomposition:
    """Classical additive seasonal decomposition via moving averages.

    Decomposes a series into trend + seasonal + residual:
        y[t] = trend[t] + seasonal[t] + residual[t]

    The trend is estimated with a centered moving average of length
    ``period`` (or ``period + 1`` if even). The seasonal component is
    the average detrended value for each phase of the cycle.

    Args:
        values: Input time series.
        period: Seasonal period (>= 2).

    Returns:
        SeasonalDecomposition with trend, seasonal, and residual lists
        of the same length as the input.
    """
    if period < 2:
        raise ValueError("period must be >= 2")

    data = _validate_series(values)
    n = len(data)
    if n < period:
        # Not enough data for a full cycle
        return SeasonalDecomposition(
            trend=[None] * n,
            seasonal=[0.0] * n,
            residual=[None] * n,
            period=period,
        )

    # --- Trend: centered moving average ---
    trend: list[float | None] = [None] * n
    half = period // 2
    for i in range(n):
        if period % 2 == 1:
            # Odd period: symmetric window
            lo = i - half
            hi = i + half + 1
        else:
            # Even period: asymmetric, needs 2xMA
            lo = i - half
            hi = i + half
        if lo < 0 or hi > n:
            continue
        window = [v for v in data[lo:hi] if not math.isnan(v)]
        if len(window) >= period // 2:
            trend[i] = _mean(window)

    # --- Detrend and compute seasonal profile ---
    detrended: list[tuple[int, float]] = []
    for i in range(n):
        t = trend[i]
        if t is not None and not math.isnan(data[i]):
            detrended.append((i, data[i] - t))

    # Average detrended value for each phase
    phase_sums: dict[int, float] = {}
    phase_counts: dict[int, int] = {}
    for idx, val in detrended:
        phase = idx % period
        phase_sums[phase] = phase_sums.get(phase, 0.0) + val
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    seasonal_profile: list[float] = []
    for p in range(period):
        if p in phase_counts and phase_counts[p] > 0:
            seasonal_profile.append(phase_sums[p] / phase_counts[p])
        else:
            seasonal_profile.append(0.0)

    # Center the seasonal profile (mean = 0 for additive)
    profile_mean = _mean(seasonal_profile)
    seasonal_profile = [s - profile_mean for s in seasonal_profile]

    # --- Build full-length arrays ---
    seasonal: list[float] = [seasonal_profile[i % period] for i in range(n)]
    residual: list[float | None] = []
    for i in range(n):
        t = trend[i]
        if t is not None and not math.isnan(data[i]):
            residual.append(data[i] - t - seasonal[i])
        else:
            residual.append(None)

    return SeasonalDecomposition(
        trend=trend,
        seasonal=seasonal,
        residual=residual,
        period=period,
    )


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


def detect_trend(
    values: Sequence[float],
    *,
    alpha: float = 0.05,
    mk: bool = True,
    change_points: bool = True,
) -> TrendResult:
    """Detect trend direction and significance in a time series.

    Combines OLS linear regression with the Mann-Kendall non-parametric
    test and optional change-point detection via binary segmentation.

    Args:
        values: Input time series.
        alpha: Significance level for trend classification.
        mk: Whether to compute Mann-Kendall test.
        change_points: Whether to detect change points.

    Returns:
        TrendResult with slope, intercept, r_squared, p_value, direction,
        Mann-Kendall statistics, and change-point indices.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    data = _validate_series(values)
    n = len(data)

    # Filter to valid (non-NaN) points for regression
    valid_x: list[float] = []
    valid_y: list[float] = []
    for i, v in enumerate(data):
        if not math.isnan(v):
            valid_x.append(float(i))
            valid_y.append(v)

    if len(valid_x) < 2:
        return TrendResult(
            slope=0.0,
            intercept=0.0,
            r_squared=0.0,
            p_value=None,
            direction="flat",
            mann_kendall_tau=None,
            mann_kendall_p=None,
            change_points=[],
        )

    slope, intercept, r_squared = _linear_regression(valid_x, valid_y)

    # OLS p-value for slope (t-test with n-2 df)
    p_value: float | None = None
    if len(valid_x) > 2:
        n_valid = len(valid_x)
        y_pred = [slope * x + intercept for x in valid_x]
        residuals = [y - yp for y, yp in zip(valid_y, y_pred)]
        mse = sum(r * r for r in residuals) / (n_valid - 2)
        x_mean = _mean(valid_x)
        sxx = sum((x - x_mean) ** 2 for x in valid_x)
        if sxx > 0:
            if mse == 0.0:
                # Perfect fit: p-value is 0
                p_value = 0.0
            else:
                se_slope = math.sqrt(mse / sxx)
                t_stat = slope / se_slope
                # Approximate p-value using normal for large n, t-dist for small
                p_value = 2.0 * (1.0 - _student_t_cdf(abs(t_stat), n_valid - 2))

    # Mann-Kendall
    mk_tau: float | None = None
    mk_p: float | None = None
    if mk and len(valid_y) >= 3:
        mk_tau, mk_p = _mann_kendall(valid_y)

    # Direction classification
    direction = "flat"
    if p_value is not None and p_value < alpha:
        if slope > 0:
            direction = "increasing"
        elif slope < 0:
            direction = "decreasing"
    elif mk_p is not None and mk_p < alpha and mk_tau is not None:
        if mk_tau > 0:
            direction = "increasing"
        elif mk_tau < 0:
            direction = "decreasing"

    # Change-point detection
    cps: list[int] = []
    if change_points and len(valid_y) >= 8:
        cps = _detect_change_points(valid_y)

    return TrendResult(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        p_value=p_value,
        direction=direction,
        mann_kendall_tau=mk_tau,
        mann_kendall_p=mk_p,
        change_points=cps,
    )


def _student_t_cdf(t: float, df: int) -> float:
    """Approximate Student's t CDF using the regularized incomplete beta.

    Uses a simple numerical integration (Simpson's rule) for the t PDF.
    """
    if df < 1:
        return 0.5
    # For large df, t approaches normal
    if df > 100:
        return _normal_cdf(t)
    # Numerical integration of t PDF from -inf to t
    # Use symmetry: integrate from 0 to |t|
    sign = 1.0 if t >= 0 else -1.0
    abs_t = abs(t)
    if abs_t == 0:
        return 0.5
    n_steps = 200
    h = abs_t / n_steps
    total = 0.0
    for i in range(n_steps + 1):
        x = i * h
        fx = _t_pdf(x, df)
        if i == 0 or i == n_steps:
            total += fx
        elif i % 2 == 1:
            total += 4.0 * fx
        else:
            total += 2.0 * fx
    total *= h / 3.0
    cdf = 0.5 + sign * total
    return max(0.0, min(1.0, cdf))


def _t_pdf(x: float, df: int) -> float:
    """Student's t probability density function."""
    coeff = math.gamma((df + 1) / 2.0) / (math.sqrt(df * math.pi) * math.gamma(df / 2.0))
    return coeff * (1.0 + x * x / df) ** (-(df + 1) / 2.0)


def _detect_change_points(
    values: list[float],
    min_segment: int = 4,
    threshold: float = 2.0,
) -> list[int]:
    """Detect change points via binary segmentation on mean shifts.

    Args:
        values: Input series (no NaN).
        min_segment: Minimum points per segment.
        threshold: Minimum standardized mean shift to split.

    Returns:
        Sorted list of change-point indices (split occurs *after* the index).
    """
    n = len(values)
    if n < 2 * min_segment:
        return []

    cps: list[int] = []
    _binary_segment(values, 0, n - 1, min_segment, threshold, cps)
    return sorted(cps)


def _binary_segment(
    values: list[float],
    lo: int,
    hi: int,
    min_segment: int,
    threshold: float,
    cps: list[int],
) -> None:
    """Recursive binary segmentation helper."""
    if hi - lo + 1 < 2 * min_segment:
        return

    best_idx = -1
    best_score = 0.0
    total_mean = _mean(values[lo:hi + 1])
    total_std = _std(values[lo:hi + 1], ddof=0)

    if total_std == 0:
        return

    for i in range(lo + min_segment, hi - min_segment + 2):
        left = values[lo:i]
        right = values[i:hi + 1]
        left_mean = _mean(left)
        right_mean = _mean(right)
        score = abs(left_mean - right_mean) / total_std
        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx > 0 and best_score >= threshold:
        cps.append(best_idx - 1)
        _binary_segment(values, lo, best_idx - 1, min_segment, threshold, cps)
        _binary_segment(values, best_idx, hi, min_segment, threshold, cps)


# ---------------------------------------------------------------------------
# Convenience: extract all features at once
# ---------------------------------------------------------------------------


def extract_features(
    values: Sequence[float],
    *,
    window: int = 7,
    lags: Sequence[int] = (1, 2, 7),
    period: int = 7,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Extract all time-series features in one call.

    Args:
        values: Input time series.
        window: Rolling window size.
        lags: Lag offsets.
        period: Seasonal period.
        alpha: Significance level for trend detection.

    Returns:
        Dictionary with keys: rolling, lags, seasonal, trend.
    """
    return {
        "rolling": rolling_stats(values, window),
        "lags": lag_features(values, lags),
        "seasonal": seasonal_decompose(values, period),
        "trend": detect_trend(values, alpha=alpha),
    }
