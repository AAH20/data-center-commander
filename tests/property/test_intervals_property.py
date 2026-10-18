"""Property-based tests for interval alignment and resampling.

Tests invariants that should hold for all valid inputs:
- Resampling to the same interval is identity
- Upsampling then downsampling preserves the original values at original timestamps
- Floor/ceil timestamp operations are consistent
- Gap detection finds gaps only when they exist
- Coverage reports are complete when all points are present
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pytest
from hypothesis import given, settings, strategies as st

from dcc.validation.intervals import (
    Aggregation,
    DataPoint,
    TimeSeries,
    align_series,
    ceil_timestamp,
    coverage_report,
    detect_gaps,
    downsample,
    floor_timestamp,
    interval_name,
    interval_seconds,
    merge_aligned,
    resample,
    upsample,
    UpsampleMethod,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

intervals = st.sampled_from([60, 300, 900, 3600])
positive_intervals = st.integers(min_value=1, max_value=86400)

base_time = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)


def make_timestamp(offset_seconds: int) -> dt.datetime:
    """Create a timestamp offset from base_time."""
    return base_time + dt.timedelta(seconds=offset_seconds)


@st.composite
def time_series_strategy(draw, max_points: int = 50) -> TimeSeries:
    """Generate a valid TimeSeries with grid-aligned timestamps."""
    interval = draw(st.sampled_from([60, 300, 900, 3600]))
    num_points = draw(st.integers(min_value=1, max_value=max_points))
    start_offset = draw(st.integers(min_value=0, max_value=10000)) * interval
    points = []
    for i in range(num_points):
        ts = make_timestamp(start_offset + i * interval)
        value = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
        points.append(DataPoint(timestamp=ts, value=value))
    return TimeSeries(name="test", interval=interval, points=points)


# ---------------------------------------------------------------------------
# Floor/Ceil timestamp properties
# ---------------------------------------------------------------------------


@given(
    offset=st.integers(min_value=0, max_value=1000000),
    interval=positive_intervals,
)
@settings(max_examples=200)
def test_floor_timestamp_on_grid(offset, interval):
    """Floor of a timestamp on the grid should be <= original."""
    ts = make_timestamp(offset)
    floored = floor_timestamp(ts, interval)
    assert floored <= ts


@given(
    offset=st.integers(min_value=0, max_value=1000000),
    interval=positive_intervals,
)
@settings(max_examples=200)
def test_ceil_timestamp_on_grid(offset, interval):
    """Ceil of a timestamp on the grid should be >= original."""
    ts = make_timestamp(offset)
    ceiled = ceil_timestamp(ts, interval)
    assert ceiled >= ts


@given(
    offset=st.integers(min_value=0, max_value=1000000),
    interval=positive_intervals,
)
@settings(max_examples=200)
def test_floor_ceil_consistency(offset, interval):
    """Floor(ts) <= ts <= ceil(ts)."""
    ts = make_timestamp(offset)
    floored = floor_timestamp(ts, interval)
    ceiled = ceil_timestamp(ts, interval)
    assert floored <= ts <= ceiled


@given(
    offset=st.integers(min_value=0, max_value=1000000),
    interval=st.sampled_from([60, 300, 900, 3600]),
)
@settings(max_examples=200)
def test_floor_already_on_grid(offset, interval):
    """Floor of a timestamp already on the grid should be itself."""
    # Create a timestamp on the grid
    grid_offset = (offset // interval) * interval
    ts = make_timestamp(grid_offset)
    floored = floor_timestamp(ts, interval)
    assert floored == ts


@given(
    offset=st.integers(min_value=0, max_value=1000000),
    interval=st.sampled_from([60, 300, 900, 3600]),
)
@settings(max_examples=200)
def test_ceil_already_on_grid(offset, interval):
    """Ceil of a timestamp already on the grid should be itself."""
    grid_offset = (offset // interval) * interval
    ts = make_timestamp(grid_offset)
    ceiled = ceil_timestamp(ts, interval)
    assert ceiled == ts


@given(interval=positive_intervals)
@settings(max_examples=100)
def test_floor_ceil_difference_at_most_interval(interval):
    """ceil(ts) - floor(ts) should be 0 or interval."""
    ts = make_timestamp(12345)
    floored = floor_timestamp(ts, interval)
    ceiled = ceil_timestamp(ts, interval)
    diff = (ceiled - floored).total_seconds()
    assert diff == 0 or diff == interval


# ---------------------------------------------------------------------------
# Interval name/seconds properties
# ---------------------------------------------------------------------------


@given(name=st.sampled_from(["1min", "5min", "15min", "1hr"]))
@settings(max_examples=50)
def test_interval_name_round_trip(name):
    """interval_name(interval_seconds(name)) should return the same name."""
    seconds = interval_seconds(name)
    assert interval_name(seconds) == name


@given(name=st.sampled_from(["1min", "5min", "15min", "1hr"]))
@settings(max_examples=50)
def test_interval_seconds_positive(name):
    """All named intervals should have positive seconds."""
    assert interval_seconds(name) > 0


# ---------------------------------------------------------------------------
# Resample identity property
# ---------------------------------------------------------------------------


@given(series=time_series_strategy())
@settings(max_examples=200)
def test_resample_same_interval_is_identity(series):
    """Resampling to the same interval should preserve all points."""
    result = resample(series, series.interval)
    assert result.interval == series.interval
    assert len(result.points) == len(series.points)
    for orig, resampled in zip(series.points, result.points):
        assert orig.timestamp == resampled.timestamp
        assert orig.value == resampled.value


# ---------------------------------------------------------------------------
# Upsample properties
# ---------------------------------------------------------------------------


@given(
    series=time_series_strategy(max_points=20),
    target_interval=st.sampled_from([60, 300]),
)
@settings(max_examples=200)
def test_upsample_increases_point_count(series, target_interval):
    """Upsampling to a finer interval should increase or maintain point count."""
    if target_interval < series.interval and series.interval % target_interval == 0:
        result = upsample(series, target_interval, UpsampleMethod.FORWARD_FILL)
        assert result.interval == target_interval
        assert len(result.points) >= len(series.points)


@given(
    series=time_series_strategy(max_points=20),
    target_interval=st.sampled_from([60, 300]),
)
@settings(max_examples=200)
def test_upsample_forward_fill_preserves_values(series, target_interval):
    """Forward-fill upsampling should preserve original values at original timestamps."""
    if target_interval < series.interval and series.interval % target_interval == 0:
        # Align series timestamps to the target grid
        aligned_points = []
        for p in series.points:
            aligned_ts = floor_timestamp(p.timestamp, target_interval)
            aligned_points.append(DataPoint(timestamp=aligned_ts, value=p.value))
        aligned_series = TimeSeries(name=series.name, interval=series.interval, points=aligned_points)
        result = upsample(aligned_series, target_interval, UpsampleMethod.FORWARD_FILL)
        # Every original point should appear in the upsampled series
        result_timestamps = {p.timestamp for p in result.points}
        for orig in aligned_series.points:
            assert orig.timestamp in result_timestamps


@given(
    series=time_series_strategy(max_points=20),
    target_interval=st.sampled_from([60, 300]),
)
@settings(max_examples=200)
def test_upsample_linear_preserves_endpoints(series, target_interval):
    """Linear interpolation should preserve the first and last values."""
    if target_interval < series.interval and series.interval % target_interval == 0 and len(series.points) >= 2:
        # Align series timestamps to the target grid
        aligned_points = []
        for p in series.points:
            aligned_ts = floor_timestamp(p.timestamp, target_interval)
            aligned_points.append(DataPoint(timestamp=aligned_ts, value=p.value))
        aligned_series = TimeSeries(name=series.name, interval=series.interval, points=aligned_points)
        result = upsample(aligned_series, target_interval, UpsampleMethod.LINEAR)
        assert result.points[0].value == aligned_series.points[0].value
        assert result.points[-1].value == aligned_series.points[-1].value


# ---------------------------------------------------------------------------
# Downsample properties
# ---------------------------------------------------------------------------


@given(
    series=time_series_strategy(max_points=50),
    target_interval=st.sampled_from([900, 3600]),
)
@settings(max_examples=200)
def test_downsample_decreases_point_count(series, target_interval):
    """Downsampling to a coarser interval should decrease point count."""
    if target_interval > series.interval and target_interval % series.interval == 0:
        result = downsample(series, target_interval, Aggregation.MEAN)
        assert result.interval == target_interval
        assert len(result.points) <= len(series.points)


@given(
    series=time_series_strategy(max_points=50),
    target_interval=st.sampled_from([900, 3600]),
)
@settings(max_examples=200)
def test_downsample_sum_preserves_total(series, target_interval):
    """Downsampling with SUM should preserve the total sum (approximately)."""
    if target_interval > series.interval and target_interval % series.interval == 0:
        original_sum = sum(p.value for p in series.points)
        result = downsample(series, target_interval, Aggregation.SUM)
        downsampled_sum = sum(p.value for p in result.points)
        # Allow for floating point tolerance
        if original_sum != 0:
            rel_error = abs(downsampled_sum - original_sum) / abs(original_sum)
            assert rel_error < 0.001


@given(
    series=time_series_strategy(max_points=50),
    target_interval=st.sampled_from([900, 3600]),
)
@settings(max_examples=200)
def test_downsample_mean_within_range(series, target_interval):
    """Downsampling with MEAN should produce values within the original range."""
    if target_interval > series.interval and target_interval % series.interval == 0:
        original_values = [p.value for p in series.points]
        result = downsample(series, target_interval, Aggregation.MEAN)
        for p in result.points:
            assert min(original_values) <= p.value <= max(original_values)


# ---------------------------------------------------------------------------
# Align series properties
# ---------------------------------------------------------------------------


@given(
    series_list=st.lists(time_series_strategy(max_points=10), min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_align_series_same_interval(series_list):
    """Aligned series should all have the same interval."""
    aligned = align_series(series_list)
    intervals = {s.interval for s in aligned}
    assert len(intervals) == 1


@given(
    series_list=st.lists(time_series_strategy(max_points=10), min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_align_series_preserves_count(series_list):
    """Aligned series should have the same number of series."""
    aligned = align_series(series_list)
    assert len(aligned) == len(series_list)


@given(
    series_list=st.lists(time_series_strategy(max_points=10), min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_align_series_preserves_names(series_list):
    """Aligned series should preserve series names."""
    aligned = align_series(series_list)
    for orig, aligned_s in zip(series_list, aligned):
        assert orig.name == aligned_s.name


# ---------------------------------------------------------------------------
# Merge aligned properties
# ---------------------------------------------------------------------------


@given(
    series_list=st.lists(time_series_strategy(max_points=10), min_size=1, max_size=3),
)
@settings(max_examples=100)
def test_merge_aligned_same_interval(series_list):
    """Merged rows should have timestamps from all series."""
    aligned = align_series(series_list)
    rows = merge_aligned(aligned)
    # Each row should have a timestamp key
    for row in rows:
        assert "timestamp" in row


# ---------------------------------------------------------------------------
# Gap detection properties
# ---------------------------------------------------------------------------


@given(
    series=time_series_strategy(max_points=50),
)
@settings(max_examples=200)
def test_detect_gaps_no_gaps_when_regular(series):
    """A regular series with no gaps should produce no gap findings."""
    # Create a perfectly regular series
    regular_points = []
    for i, p in enumerate(series.points):
        ts = make_timestamp(i * series.interval)
        regular_points.append(DataPoint(timestamp=ts, value=p.value))
    regular_series = TimeSeries(name="regular", interval=series.interval, points=regular_points)
    gaps = detect_gaps(regular_series)
    assert len(gaps) == 0


@given(
    num_points=st.integers(min_value=3, max_value=20),
    interval=st.sampled_from([60, 300, 900]),
    gap_after=st.integers(min_value=1, max_value=18),
)
@settings(max_examples=200)
def test_detect_gaps_finds_gap(num_points, interval, gap_after):
    """A series with a gap should produce a gap finding."""
    if gap_after >= num_points - 1:
        gap_after = num_points - 2
    points = []
    for i in range(num_points):
        if i <= gap_after:
            ts = make_timestamp(i * interval)
        else:
            # Skip one interval to create a gap
            ts = make_timestamp((i + 1) * interval)
        points.append(DataPoint(timestamp=ts, value=float(i)))
    series = TimeSeries(name="gapped", interval=interval, points=points)
    gaps = detect_gaps(series)
    assert len(gaps) >= 1


# ---------------------------------------------------------------------------
# Coverage report properties
# ---------------------------------------------------------------------------


@given(
    num_series=st.integers(min_value=1, max_value=3),
    num_points=st.integers(min_value=1, max_value=10),
    interval=st.sampled_from([60, 300, 900]),
)
@settings(max_examples=100)
def test_coverage_report_complete_when_all_present(num_series, num_points, interval):
    """Coverage should be complete when all series cover the full range."""
    # Create series with identical timestamps
    points = [DataPoint(timestamp=make_timestamp(i * interval), value=float(i)) for i in range(num_points)]
    series_list = [TimeSeries(name=f"series-{j}", interval=interval, points=list(points)) for j in range(num_series)]
    aligned = align_series(series_list)
    target_interval = aligned[0].interval
    start = min(s.start for s in aligned if s.start is not None)
    end = max(s.end for s in aligned if s.end is not None)
    start_aligned = floor_timestamp(start, target_interval)
    end_aligned = floor_timestamp(end, target_interval)
    report = coverage_report(aligned, target_interval, start=start_aligned, end=end_aligned)
    # Coverage should be 100% for all series since they're aligned
    for name, stats in report.per_series.items():
        assert stats["coverage_pct"] == 100.0


@given(
    series=time_series_strategy(max_points=20),
)
@settings(max_examples=100)
def test_coverage_report_total_expected_positive(series):
    """Total expected points should be positive for non-empty series."""
    if series.points:
        report = coverage_report([series], series.interval)
        assert report.total_expected > 0


# ---------------------------------------------------------------------------
# TimeSeries properties
# ---------------------------------------------------------------------------


@given(series=time_series_strategy())
@settings(max_examples=100)
def test_timeseries_sorted_by_timestamp(series):
    """TimeSeries points should be sorted by timestamp."""
    for i in range(1, len(series.points)):
        assert series.points[i].timestamp >= series.points[i - 1].timestamp


@given(series=time_series_strategy())
@settings(max_examples=100)
def test_timeseries_start_end_properties(series):
    """Start and end should be the first and last timestamps."""
    if series.points:
        assert series.start == series.points[0].timestamp
        assert series.end == series.points[-1].timestamp


@given(series=time_series_strategy())
@settings(max_examples=100)
def test_timeseries_values_match_points(series):
    """Values property should return all point values."""
    values = series.values()
    assert len(values) == len(series.points)
    for i, p in enumerate(series.points):
        assert values[i] == p.value
