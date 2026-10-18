"""Unit tests for dcc.validation.intervals module."""
import unittest
import datetime as dt

from dcc.validation.intervals import (
    INTERVAL_1MIN,
    INTERVAL_5MIN,
    INTERVAL_15MIN,
    INTERVAL_1HR,
    interval_seconds,
    interval_name,
    floor_timestamp,
    ceil_timestamp,
    align_timestamp,
    DataPoint,
    TimeSeries,
    Aggregation,
    UpsampleMethod,
    Gap,
    CoverageReport,
    upsample,
    downsample,
    resample,
    align_series,
    merge_aligned,
    detect_gaps,
    coverage_report,
)


class TestIntervalConstants(unittest.TestCase):
    def test_interval_values(self):
        self.assertEqual(INTERVAL_1MIN, 60)
        self.assertEqual(INTERVAL_5MIN, 300)
        self.assertEqual(INTERVAL_15MIN, 900)
        self.assertEqual(INTERVAL_1HR, 3600)


class TestIntervalSeconds(unittest.TestCase):
    def test_1min(self):
        self.assertEqual(interval_seconds("1min"), 60)

    def test_5min(self):
        self.assertEqual(interval_seconds("5min"), 300)

    def test_15min(self):
        self.assertEqual(interval_seconds("15min"), 900)

    def test_1hr(self):
        self.assertEqual(interval_seconds("1hr"), 3600)

    def test_case_insensitive(self):
        self.assertEqual(interval_seconds("5MIN"), 300)

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            interval_seconds("invalid")


class TestIntervalName(unittest.TestCase):
    def test_60(self):
        self.assertEqual(interval_name(60), "1min")

    def test_300(self):
        self.assertEqual(interval_name(300), "5min")

    def test_900(self):
        self.assertEqual(interval_name(900), "15min")

    def test_3600(self):
        self.assertEqual(interval_name(3600), "1hr")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            interval_name(123)


class TestFloorTimestamp(unittest.TestCase):
    def test_exact_boundary(self):
        ts = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        result = floor_timestamp(ts, 300)
        self.assertEqual(result, ts)

    def test_within_interval(self):
        ts = dt.datetime(2024, 1, 1, 0, 3, tzinfo=dt.timezone.utc)
        result = floor_timestamp(ts, 300)
        expected = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(result, expected)

    def test_invalid_interval(self):
        ts = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        with self.assertRaises(ValueError):
            floor_timestamp(ts, 0)


class TestCeilTimestamp(unittest.TestCase):
    def test_exact_boundary(self):
        ts = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        result = ceil_timestamp(ts, 300)
        self.assertEqual(result, ts)

    def test_within_interval(self):
        ts = dt.datetime(2024, 1, 1, 0, 3, tzinfo=dt.timezone.utc)
        result = ceil_timestamp(ts, 300)
        expected = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        self.assertEqual(result, expected)

    def test_invalid_interval(self):
        ts = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        with self.assertRaises(ValueError):
            ceil_timestamp(ts, 0)


class TestAlignTimestamp(unittest.TestCase):
    def test_align(self):
        ts = dt.datetime(2024, 1, 1, 0, 3, tzinfo=dt.timezone.utc)
        result = align_timestamp(ts, 300)
        expected = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(result, expected)


class TestDataPoint(unittest.TestCase):
    def test_creation(self):
        ts = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        dp = DataPoint(timestamp=ts, value=100.0)
        self.assertEqual(dp.timestamp, ts)
        self.assertEqual(dp.value, 100.0)


class TestTimeSeries(unittest.TestCase):
    def test_creation(self):
        ts = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
        dp = DataPoint(timestamp=ts, value=100.0)
        series = TimeSeries(name="test", interval=300, points=[dp])
        self.assertEqual(series.name, "test")
        self.assertEqual(series.interval, 300)
        self.assertEqual(len(series.points), 1)

    def test_empty_series(self):
        series = TimeSeries(name="test", interval=300)
        self.assertIsNone(series.start)
        self.assertIsNone(series.end)
        self.assertEqual(series.values(), [])

    def test_start_end(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        self.assertEqual(series.start, ts1)
        self.assertEqual(series.end, ts2)

    def test_values(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        self.assertEqual(series.values(), [100.0, 200.0])

    def test_timestamps(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        self.assertEqual(series.timestamps(), [ts1, ts2])

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            TimeSeries(name="test", interval=0)

    def test_sorted_points(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp2, dp1])
        self.assertEqual(series.points[0].timestamp, ts1)


class TestUpsample(unittest.TestCase):
    def test_upsample_forward_fill(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        result = upsample(series, 60, UpsampleMethod.FORWARD_FILL)
        self.assertEqual(result.interval, 60)
        self.assertGreater(len(result.points), 2)


class TestDownsample(unittest.TestCase):
    def test_downsample_mean(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 1, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=60, points=[dp1, dp2])
        result = downsample(series, 300, Aggregation.MEAN)
        self.assertEqual(result.interval, 300)
        self.assertEqual(len(result.points), 1)
        self.assertAlmostEqual(result.points[0].value, 150.0)


class TestResample(unittest.TestCase):
    def test_resample_up(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        result = resample(series, 60)
        self.assertEqual(result.interval, 60)

    def test_resample_down(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 1, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=60, points=[dp1, dp2])
        result = resample(series, 300)
        self.assertEqual(result.interval, 300)


class TestAlignSeries(unittest.TestCase):
    def test_align_same_interval(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        s1 = TimeSeries(name="a", interval=300, points=[dp1])
        s2 = TimeSeries(name="b", interval=300, points=[dp2])
        result = align_series([s1, s2])
        self.assertEqual(len(result), 2)

    def test_align_different_intervals(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 1, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        s1 = TimeSeries(name="a", interval=300, points=[dp1])
        s2 = TimeSeries(name="b", interval=60, points=[dp2])
        result = align_series([s1, s2])
        self.assertEqual(len(result), 2)


class TestMergeAligned(unittest.TestCase):
    def test_merge(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        s1 = TimeSeries(name="a", interval=300, points=[dp1])
        s2 = TimeSeries(name="b", interval=300, points=[dp2])
        result = merge_aligned([s1, s2])
        self.assertIsInstance(result, list)


class TestDetectGaps(unittest.TestCase):
    def test_no_gaps(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        gaps = detect_gaps(series)
        self.assertEqual(gaps, [])

    def test_with_gaps(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 15, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        series = TimeSeries(name="test", interval=300, points=[dp1, dp2])
        gaps = detect_gaps(series)
        self.assertGreater(len(gaps), 0)


class TestCoverageReport(unittest.TestCase):
    def test_coverage(self):
        ts1 = dt.datetime(2024, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
        ts2 = dt.datetime(2024, 1, 1, 0, 5, tzinfo=dt.timezone.utc)
        dp1 = DataPoint(timestamp=ts1, value=100.0)
        dp2 = DataPoint(timestamp=ts2, value=200.0)
        s1 = TimeSeries(name="a", interval=300, points=[dp1, dp2])
        report = coverage_report([s1], 300)
        self.assertIsInstance(report, CoverageReport)


if __name__ == "__main__":
    unittest.main()
