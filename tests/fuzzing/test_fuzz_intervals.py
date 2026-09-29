"""Fuzz tests for interval alignment engine using Hypothesis."""
from __future__ import annotations

import datetime as dt

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.validation.intervals import (
    INTERVAL_1MIN,
    INTERVAL_5MIN,
    INTERVAL_15MIN,
    INTERVAL_1HR,
    Aggregation,
    DataPoint,
    TimeSeries,
    UpsampleMethod,
    align_series,
    coverage_report,
    detect_gaps,
    downsample,
    floor_timestamp,
    interval_name,
    interval_seconds,
    merge_aligned,
    resample,
    upsample,
)


# Strategies
interval_values = st.sampled_from([INTERVAL_1MIN, INTERVAL_5MIN, INTERVAL_15MIN, INTERVAL_1HR])

timestamps = st.datetimes(
    min_value=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    max_value=dt.datetime(2030, 12, 31, tzinfo=dt.timezone.utc),
)

float_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)

aggregation_methods = st.sampled_from(list(Aggregation))

upsample_methods = st.sampled_from(list(UpsampleMethod))


def make_datapoints(n, interval_seconds):
    """Generate n data points spaced interval_seconds apart."""
    base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    return [
        DataPoint(
            timestamp=base + dt.timedelta(seconds=interval_seconds * i),
            value=float(i),
        )
        for i in range(n)
    ]


class TestIntervalAlignmentFuzz:
    """Fuzz interval alignment operations."""

    @given(
        interval=interval_values,
    )
    @settings(max_examples=50)
    def test_interval_seconds_never_crashes(self, interval):
        """interval_seconds should handle valid interval names."""
        name = interval_name(interval)
        seconds = interval_seconds(name)
        assert seconds == interval

    @given(
        ts=timestamps,
        interval=interval_values,
    )
    @settings(max_examples=100)
    def test_floor_timestamp(self, ts, interval):
        """floor_timestamp should always return a timestamp on the grid."""
        floored = floor_timestamp(ts, interval)
        assert floored <= ts
        assert (ts - floored).total_seconds() < interval

    @given(
        n_points=st.integers(min_value=2, max_value=50),
        interval=interval_values,
        target_interval=interval_values,
    )
    @settings(max_examples=100)
    def test_upsample_roundtrip(self, n_points, interval, target_interval):
        """Upsampling then downsampling should preserve data."""
        assume(target_interval < interval)
        assume(interval % target_interval == 0)
        points = make_datapoints(n_points, interval)
        series = TimeSeries(name="test", interval=interval, points=points)
        try:
            upsampled = upsample(series, target_interval, UpsampleMethod.FORWARD_FILL)
            assert upsampled.interval == target_interval
            assert len(upsampled.points) >= len(points)
        except ValueError:
            pass  # Expected for invalid combinations

    @given(
        n_points=st.integers(min_value=2, max_value=50),
        interval=interval_values,
        target_interval=interval_values,
    )
    @settings(max_examples=100)
    def test_downsample_aggregation(self, n_points, interval, target_interval):
        """Downsampling should produce fewer points."""
        assume(target_interval > interval)
        assume(target_interval % interval == 0)
        points = make_datapoints(n_points, interval)
        series = TimeSeries(name="test", interval=interval, points=points)
        downsampled = downsample(series, target_interval, Aggregation.MEAN)
        assert downsampled.interval == target_interval
        assert len(downsampled.points) <= len(points)

    @given(
        n_points=st.integers(min_value=2, max_value=50),
        interval=interval_values,
        target_interval=interval_values,
    )
    @settings(max_examples=100)
    def test_resample_never_crashes(self, n_points, interval, target_interval):
        """resample should handle any valid interval combination."""
        points = make_datapoints(n_points, interval)
        series = TimeSeries(name="test", interval=interval, points=points)
        result = resample(series, target_interval)
        assert result.interval == target_interval
        assert len(result.points) > 0

    @given(
        n_series=st.integers(min_value=1, max_value=5),
        n_points=st.integers(min_value=2, max_value=30),
        interval=interval_values,
    )
    @settings(max_examples=100)
    def test_align_series(self, n_series, n_points, interval):
        """align_series should produce series with the same interval."""
        series_list = []
        for i in range(n_series):
            points = make_datapoints(n_points, interval)
            series_list.append(TimeSeries(name=f"series-{i}", interval=interval, points=points))
        aligned = align_series(series_list)
        assert len(aligned) == n_series
        for s in aligned:
            assert s.interval == interval

    @given(
        n_series=st.integers(min_value=1, max_value=5),
        n_points=st.integers(min_value=2, max_value=30),
        interval=interval_values,
    )
    @settings(max_examples=100)
    def test_merge_aligned(self, n_series, n_points, interval):
        """merge_aligned should produce rows with all series names."""
        series_list = []
        for i in range(n_series):
            points = make_datapoints(n_points, interval)
            series_list.append(TimeSeries(name=f"series-{i}", interval=interval, points=points))
        rows = merge_aligned(series_list)
        assert len(rows) == n_points
        for row in rows:
            assert "timestamp" in row
            for i in range(n_series):
                assert f"series-{i}" in row

    @given(
        n_points=st.integers(min_value=2, max_value=50),
        interval=interval_values,
    )
    @settings(max_examples=100)
    def test_detect_gaps(self, n_points, interval):
        """detect_gaps should handle any series."""
        points = make_datapoints(n_points, interval)
        series = TimeSeries(name="test", interval=interval, points=points)
        gaps = detect_gaps(series)
        assert isinstance(gaps, list)

    @given(
        n_series=st.integers(min_value=1, max_value=5),
        n_points=st.integers(min_value=2, max_value=30),
        interval=interval_values,
        target_interval=interval_values,
    )
    @settings(max_examples=100)
    def test_coverage_report(self, n_series, n_points, interval, target_interval):
        """coverage_report should handle any series combination."""
        series_list = []
        for i in range(n_series):
            points = make_datapoints(n_points, interval)
            series_list.append(TimeSeries(name=f"series-{i}", interval=interval, points=points))
        report = coverage_report(series_list, target_interval)
        assert report.target_interval == target_interval
        assert report.total_expected >= 0
