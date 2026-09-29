"""Time-series interval alignment engine.

Aligns data sampled at different intervals (1min, 5min, 15min, 1hr) to a
common interval grid. Supports upsampling (forward-fill, linear interpolation),
downsampling (aggregation), and multi-series alignment.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

# ---------------------------------------------------------------------------
# Interval definitions
# ---------------------------------------------------------------------------

INTERVAL_1MIN = 60
INTERVAL_5MIN = 300
INTERVAL_15MIN = 900
INTERVAL_1HR = 3600

_INTERVAL_SECONDS: dict[str, int] = {
    "1min": INTERVAL_1MIN,
    "5min": INTERVAL_5MIN,
    "15min": INTERVAL_15MIN,
    "1hr": INTERVAL_1HR,
}


def interval_seconds(name: str) -> int:
    """Return the duration in seconds for a named interval."""
    key = name.strip().lower()
    if key not in _INTERVAL_SECONDS:
        raise ValueError(
            f"unknown interval {name!r}; expected one of {sorted(_INTERVAL_SECONDS)}"
        )
    return _INTERVAL_SECONDS[key]


def interval_name(seconds: int) -> str:
    """Return the canonical name for a duration in seconds."""
    for name, secs in _INTERVAL_SECONDS.items():
        if secs == seconds:
            return name
    raise ValueError(f"no canonical interval for {seconds}s")


def floor_timestamp(ts: dt.datetime, interval: int) -> dt.datetime:
    """Floor a datetime to the nearest interval boundary (UTC epoch)."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    delta = (ts - epoch).total_seconds()
    floored = int(delta // interval) * interval
    return epoch + dt.timedelta(seconds=floored)


def ceil_timestamp(ts: dt.datetime, interval: int) -> dt.datetime:
    """Ceil a datetime to the nearest interval boundary (UTC epoch)."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    floored = floor_timestamp(ts, interval)
    if floored == ts:
        return ts
    return floored + dt.timedelta(seconds=interval)


def align_timestamp(ts: dt.datetime, interval: int) -> dt.datetime:
    """Alias for floor_timestamp — align a timestamp to the interval grid."""
    return floor_timestamp(ts, interval)


# ---------------------------------------------------------------------------
# Data point and series types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DataPoint:
    """A single timestamped observation."""

    timestamp: dt.datetime
    value: float


@dataclass(slots=True)
class TimeSeries:
    """A named time series with a fixed sampling interval."""

    name: str
    interval: int  # seconds
    points: list[DataPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError("interval must be positive")
        self.points.sort(key=lambda p: p.timestamp)

    @property
    def start(self) -> dt.datetime | None:
        return self.points[0].timestamp if self.points else None

    @property
    def end(self) -> dt.datetime | None:
        return self.points[-1].timestamp if self.points else None

    def values(self) -> list[float]:
        return [p.value for p in self.points]

    def timestamps(self) -> list[dt.datetime]:
        return [p.timestamp for p in self.points]


# ---------------------------------------------------------------------------
# Aggregation methods for downsampling
# ---------------------------------------------------------------------------


class Aggregation(Enum):
    """Supported aggregation methods when downsampling."""

    MEAN = "mean"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    FIRST = "first"
    LAST = "last"
    COUNT = "count"


def _aggregate(values: list[float], method: Aggregation) -> float:
    """Aggregate a list of floats using the specified method."""
    if not values:
        raise ValueError("cannot aggregate empty list")
    if method is Aggregation.MEAN:
        return sum(values) / len(values)
    if method is Aggregation.SUM:
        return sum(values)
    if method is Aggregation.MIN:
        return min(values)
    if method is Aggregation.MAX:
        return max(values)
    if method is Aggregation.FIRST:
        return values[0]
    if method is Aggregation.LAST:
        return values[-1]
    if method is Aggregation.COUNT:
        return float(len(values))
    raise ValueError(f"unsupported aggregation: {method}")


# ---------------------------------------------------------------------------
# Upsampling strategies
# ---------------------------------------------------------------------------


class UpsampleMethod(Enum):
    """Supported strategies when upsampling to a finer interval."""

    FORWARD_FILL = "forward_fill"
    LINEAR = "linear"
    STEP = "step"  # same as forward_fill, explicit alias


def _forward_fill(
    points: Sequence[DataPoint], target_interval: int
) -> list[DataPoint]:
    """Upsample by carrying the last known value forward."""
    if not points:
        return []
    result: list[DataPoint] = []
    start = floor_timestamp(points[0].timestamp, target_interval)
    end = floor_timestamp(points[-1].timestamp, target_interval)
    current = start
    src_idx = 0
    while current <= end:
        while (
            src_idx + 1 < len(points)
            and points[src_idx + 1].timestamp <= current
        ):
            src_idx += 1
        result.append(DataPoint(timestamp=current, value=points[src_idx].value))
        current += dt.timedelta(seconds=target_interval)
    return result


def _linear_interpolate(
    points: Sequence[DataPoint], target_interval: int
) -> list[DataPoint]:
    """Upsample by linearly interpolating between known points."""
    if not points:
        return []
    if len(points) == 1:
        return [DataPoint(timestamp=floor_timestamp(points[0].timestamp, target_interval), value=points[0].value)]

    result: list[DataPoint] = []
    start = floor_timestamp(points[0].timestamp, target_interval)
    end = floor_timestamp(points[-1].timestamp, target_interval)
    current = start
    src_idx = 0
    while current <= end:
        # Advance src_idx so that points[src_idx] <= current < points[src_idx+1]
        while (
            src_idx + 1 < len(points)
            and points[src_idx + 1].timestamp <= current
        ):
            src_idx += 1
        if src_idx + 1 >= len(points):
            # Past the last point — use its value
            result.append(DataPoint(timestamp=current, value=points[-1].value))
        elif points[src_idx].timestamp == current:
            result.append(DataPoint(timestamp=current, value=points[src_idx].value))
        else:
            # Interpolate between src_idx and src_idx+1
            t0 = points[src_idx].timestamp
            t1 = points[src_idx + 1].timestamp
            v0 = points[src_idx].value
            v1 = points[src_idx + 1].value
            total = (t1 - t0).total_seconds()
            elapsed = (current - t0).total_seconds()
            frac = elapsed / total if total > 0 else 0.0
            result.append(
                DataPoint(timestamp=current, value=v0 + frac * (v1 - v0))
            )
        current += dt.timedelta(seconds=target_interval)
    return result


def upsample(
    series: TimeSeries,
    target_interval: int,
    method: UpsampleMethod = UpsampleMethod.FORWARD_FILL,
) -> TimeSeries:
    """Upsample a series to a finer interval.

    Args:
        series: The source time series.
        target_interval: The desired interval in seconds (must be finer than
            the source interval).
        method: The upsampling strategy.

    Returns:
        A new TimeSeries at the target interval.
    """
    if target_interval <= 0:
        raise ValueError("target_interval must be positive")
    if target_interval >= series.interval:
        raise ValueError(
            f"target_interval ({target_interval}s) must be finer than "
            f"source interval ({series.interval}s)"
        )
    if series.interval % target_interval != 0:
        raise ValueError(
            f"source interval ({series.interval}s) must be an integer "
            f"multiple of target interval ({target_interval}s)"
        )

    if method in (UpsampleMethod.FORWARD_FILL, UpsampleMethod.STEP):
        new_points = _forward_fill(series.points, target_interval)
    elif method is UpsampleMethod.LINEAR:
        new_points = _linear_interpolate(series.points, target_interval)
    else:
        raise ValueError(f"unsupported upsample method: {method}")

    return TimeSeries(name=series.name, interval=target_interval, points=new_points)


# ---------------------------------------------------------------------------
# Downsampling
# ---------------------------------------------------------------------------


def downsample(
    series: TimeSeries,
    target_interval: int,
    method: Aggregation = Aggregation.MEAN,
) -> TimeSeries:
    """Downsample a series to a coarser interval.

    Args:
        series: The source time series.
        target_interval: The desired interval in seconds (must be coarser than
            the source interval).
        method: The aggregation method to apply within each target bucket.

    Returns:
        A new TimeSeries at the target interval.
    """
    if target_interval <= 0:
        raise ValueError("target_interval must be positive")
    if target_interval <= series.interval:
        raise ValueError(
            f"target_interval ({target_interval}s) must be coarser than "
            f"source interval ({series.interval}s)"
        )
    if target_interval % series.interval != 0:
        raise ValueError(
            f"target interval ({target_interval}s) must be an integer "
            f"multiple of source interval ({series.interval}s)"
        )
    if not series.points:
        raise ValueError("cannot downsample an empty series")

    buckets: dict[dt.datetime, list[float]] = {}
    for point in series.points:
        bucket_start = floor_timestamp(point.timestamp, target_interval)
        buckets.setdefault(bucket_start, []).append(point.value)

    new_points = [
        DataPoint(timestamp=ts, value=_aggregate(vals, method))
        for ts, vals in sorted(buckets.items())
    ]
    return TimeSeries(name=series.name, interval=target_interval, points=new_points)


# ---------------------------------------------------------------------------
# Resample (general: up or down)
# ---------------------------------------------------------------------------


def resample(
    series: TimeSeries,
    target_interval: int,
    *,
    upsample_method: UpsampleMethod = UpsampleMethod.FORWARD_FILL,
    downsample_method: Aggregation = Aggregation.MEAN,
) -> TimeSeries:
    """Resample a series to any target interval.

    Automatically chooses upsampling or downsampling based on the relationship
    between the source and target intervals.
    """
    if target_interval == series.interval:
        return TimeSeries(
            name=series.name,
            interval=series.interval,
            points=list(series.points),
        )
    if target_interval < series.interval:
        return upsample(series, target_interval, upsample_method)
    return downsample(series, target_interval, downsample_method)


# ---------------------------------------------------------------------------
# Multi-series alignment
# ---------------------------------------------------------------------------


def align_series(
    series_list: Sequence[TimeSeries],
    target_interval: int | None = None,
    *,
    upsample_method: UpsampleMethod = UpsampleMethod.FORWARD_FILL,
    downsample_method: Aggregation = Aggregation.MEAN,
) -> list[TimeSeries]:
    """Align multiple time series to a common interval.

    If *target_interval* is not provided, the coarsest interval among the
    input series is used (minimising data loss).

    Args:
        series_list: The time series to align.
        target_interval: The common interval in seconds, or None to auto-select.
        upsample_method: Strategy for upsampling.
        downsample_method: Aggregation for downsampling.

    Returns:
        A list of TimeSeries all at the same interval.
    """
    if not series_list:
        return []
    if target_interval is None:
        target_interval = max(s.interval for s in series_list)
    return [
        resample(
            s,
            target_interval,
            upsample_method=upsample_method,
            downsample_method=downsample_method,
        )
        for s in series_list
    ]


def merge_aligned(
    series_list: Sequence[TimeSeries],
) -> list[dict[str, Any]]:
    """Merge aligned series into row-oriented dicts keyed by timestamp.

    All series must share the same interval. The output is a list of dicts
    with a ``timestamp`` key plus one key per series name.
    """
    if not series_list:
        return []
    intervals = {s.interval for s in series_list}
    if len(intervals) != 1:
        raise ValueError("all series must share the same interval to merge")

    # Build a common timestamp index
    all_timestamps: set[dt.datetime] = set()
    for s in series_list:
        all_timestamps.update(s.timestamps())

    # Index each series by timestamp
    indexed: list[dict[dt.datetime, float]] = []
    for s in series_list:
        indexed.append({p.timestamp: p.value for p in s.points})

    rows: list[dict[str, Any]] = []
    for ts in sorted(all_timestamps):
        row: dict[str, Any] = {"timestamp": ts.isoformat()}
        for s, idx in zip(series_list, indexed):
            row[s.name] = idx.get(ts)  # None if missing
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Gap:
    """A detected gap in a time series."""

    start: dt.datetime
    end: dt.datetime
    expected_points: int


def detect_gaps(
    series: TimeSeries,
    *,
    max_missing: int = 0,
) -> list[Gap]:
    """Detect gaps in a regularly-sampled time series.

    Args:
        series: The time series to check.
        max_missing: Maximum number of consecutive missing points to tolerate.
            Gaps with more missing points than this are reported.

    Returns:
        A list of Gap objects sorted by start time.
    """
    if len(series.points) < 2:
        return []
    gaps: list[Gap] = []
    for i in range(1, len(series.points)):
        prev_ts = series.points[i - 1].timestamp
        curr_ts = series.points[i].timestamp
        expected_delta = dt.timedelta(seconds=series.interval)
        actual_delta = curr_ts - prev_ts
        if actual_delta > expected_delta:
            missing = int(actual_delta.total_seconds() / series.interval) - 1
            if missing > max_missing:
                gaps.append(
                    Gap(
                        start=prev_ts + expected_delta,
                        end=curr_ts - expected_delta,
                        expected_points=missing,
                    )
                )
    return gaps


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Summary of interval coverage across multiple series."""

    target_interval: int
    total_expected: int
    per_series: dict[str, dict[str, Any]]

    @property
    def complete(self) -> bool:
        return all(
            s["missing"] == 0 for s in self.per_series.values()
        )


def coverage_report(
    series_list: Sequence[TimeSeries],
    target_interval: int,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> CoverageReport:
    """Report how well each series covers the expected time range.

    Args:
        series_list: The aligned series to analyse.
        target_interval: The common interval in seconds.
        start: Start of the range (defaults to the earliest point across series).
        end: End of the range (defaults to the latest point across series).

    Returns:
        A CoverageReport with per-series statistics.
    """
    if not series_list:
        return CoverageReport(target_interval=target_interval, total_expected=0, per_series={})

    if start is None:
        start = min(s.start for s in series_list if s.start is not None)  # type: ignore[arg-type]
    if end is None:
        end = max(s.end for s in series_list if s.end is not None)  # type: ignore[arg-type]

    start_aligned = floor_timestamp(start, target_interval)
    end_aligned = floor_timestamp(end, target_interval)
    total_expected = int(
        (end_aligned - start_aligned).total_seconds() / target_interval
    ) + 1

    per_series: dict[str, dict[str, Any]] = {}
    for s in series_list:
        present = {p.timestamp for p in s.points}
        missing = 0
        current = start_aligned
        while current <= end_aligned:
            if current not in present:
                missing += 1
            current += dt.timedelta(seconds=target_interval)
        per_series[s.name] = {
            "present": len(present),
            "missing": missing,
            "coverage_pct": round(
                (total_expected - missing) / total_expected * 100, 2
            )
            if total_expected > 0
            else 100.0,
        }

    return CoverageReport(
        target_interval=target_interval,
        total_expected=total_expected,
        per_series=per_series,
    )
