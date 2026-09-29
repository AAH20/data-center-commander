"""Tests for the time-series interval alignment engine."""
import datetime as dt
import unittest

from dcc.validation.intervals import (
    Aggregation,
    DataPoint,
    Gap,
    TimeSeries,
    UpsampleMethod,
    align_series,
    align_timestamp,
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

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _ts(seconds: int) -> dt.datetime:
    return EPOCH + dt.timedelta(seconds=seconds)


def _make_series(name: str, interval: int, values: list[float]) -> TimeSeries:
    return TimeSeries(
        name=name,
        interval=interval,
        points=[DataPoint(timestamp=_ts(i * interval), value=v) for i, v in enumerate(values)],
    )


class IntervalHelpersTests(unittest.TestCase):
    def test_interval_seconds(self):
        self.assertEqual(interval_seconds("1min"), 60)
        self.assertEqual(interval_seconds("5min"), 300)
        self.assertEqual(interval_seconds("15min"), 900)
        self.assertEqual(interval_seconds("1hr"), 3600)

    def test_interval_seconds_case_insensitive(self):
        self.assertEqual(interval_seconds("1MIN"), 60)
        self.assertEqual(interval_seconds("5Min"), 300)

    def test_interval_seconds_unknown(self):
        with self.assertRaises(ValueError):
            interval_seconds("2min")

    def test_interval_name(self):
        self.assertEqual(interval_name(60), "1min")
        self.assertEqual(interval_name(300), "5min")
        self.assertEqual(interval_name(900), "15min")
        self.assertEqual(interval_name(3600), "1hr")

    def test_interval_name_unknown(self):
        with self.assertRaises(ValueError):
            interval_name(120)

    def test_floor_timestamp(self):
        self.assertEqual(floor_timestamp(_ts(0), 300), _ts(0))
        self.assertEqual(floor_timestamp(_ts(299), 300), _ts(0))
        self.assertEqual(floor_timestamp(_ts(300), 300), _ts(300))
        self.assertEqual(floor_timestamp(_ts(301), 300), _ts(300))
        self.assertEqual(floor_timestamp(_ts(599), 300), _ts(300))
        self.assertEqual(floor_timestamp(_ts(600), 300), _ts(600))

    def test_floor_timestamp_1hr(self):
        self.assertEqual(floor_timestamp(_ts(3599), 3600), _ts(0))
        self.assertEqual(floor_timestamp(_ts(3600), 3600), _ts(3600))
        self.assertEqual(floor_timestamp(_ts(3601), 3600), _ts(3600))

    def test_align_timestamp_alias(self):
        self.assertEqual(align_timestamp(_ts(900), 300), _ts(900))
        self.assertEqual(align_timestamp(_ts(901), 300), _ts(900))

    def test_floor_timestamp_invalid(self):
        with self.assertRaises(ValueError):
            floor_timestamp(_ts(0), 0)
        with self.assertRaises(ValueError):
            floor_timestamp(_ts(0), -1)


class DataPointTests(unittest.TestCase):
    def test_dataclass(self):
        dp = DataPoint(timestamp=_ts(0), value=42.0)
        self.assertEqual(dp.timestamp, _ts(0))
        self.assertEqual(dp.value, 42.0)


class TimeSeriesTests(unittest.TestCase):
    def test_sorted_on_construction(self):
        ts = TimeSeries(
            name="test",
            interval=60,
            points=[
                DataPoint(timestamp=_ts(120), value=2.0),
                DataPoint(timestamp=_ts(0), value=1.0),
                DataPoint(timestamp=_ts(60), value=3.0),
            ],
        )
        self.assertEqual(ts.timestamps(), [_ts(0), _ts(60), _ts(120)])

    def test_start_end(self):
        ts = _make_series("s", 60, [1.0, 2.0, 3.0])
        self.assertEqual(ts.start, _ts(0))
        self.assertEqual(ts.end, _ts(120))

    def test_empty_series(self):
        ts = TimeSeries(name="empty", interval=60)
        self.assertIsNone(ts.start)
        self.assertIsNone(ts.end)
        self.assertEqual(ts.values(), [])

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            TimeSeries(name="bad", interval=0)
        with self.assertRaises(ValueError):
            TimeSeries(name="bad", interval=-1)


class UpsampleTests(unittest.TestCase):
    def test_upsample_5min_to_1min_forward_fill(self):
        ts = _make_series("s", 300, [10.0, 20.0, 30.0])
        result = upsample(ts, 60, UpsampleMethod.FORWARD_FILL)
        self.assertEqual(result.interval, 60)
        self.assertEqual(len(result.points), 11)  # 0,60,120,...,600
        self.assertEqual(result.values(), [10.0] * 5 + [20.0] * 5 + [30.0])

    def test_upsample_1hr_to_5min_forward_fill(self):
        ts = _make_series("s", 3600, [100.0, 200.0])
        result = upsample(ts, 300, UpsampleMethod.FORWARD_FILL)
        self.assertEqual(result.interval, 300)
        self.assertEqual(len(result.points), 13)
        self.assertEqual(result.values(), [100.0] * 12 + [200.0])

    def test_upsample_1hr_to_15min_forward_fill(self):
        ts = _make_series("s", 3600, [5.0])
        result = upsample(ts, 900, UpsampleMethod.FORWARD_FILL)
        self.assertEqual(result.interval, 900)
        self.assertEqual(len(result.points), 1)  # single point at t=0
        self.assertEqual(result.values(), [5.0])

    def test_upsample_linear(self):
        ts = _make_series("s", 300, [0.0, 100.0])
        result = upsample(ts, 60, UpsampleMethod.LINEAR)
        self.assertEqual(result.interval, 60)
        self.assertEqual(len(result.points), 6)  # 0, 60, 120, 180, 240, 300
        self.assertAlmostEqual(result.values()[0], 0.0)
        self.assertAlmostEqual(result.values()[1], 20.0)
        self.assertAlmostEqual(result.values()[2], 40.0)
        self.assertAlmostEqual(result.values()[3], 60.0)
        self.assertAlmostEqual(result.values()[4], 80.0)
        self.assertAlmostEqual(result.values()[5], 100.0)

    def test_upsample_step_alias(self):
        ts = _make_series("s", 300, [1.0, 2.0])
        r1 = upsample(ts, 60, UpsampleMethod.FORWARD_FILL)
        r2 = upsample(ts, 60, UpsampleMethod.STEP)
        self.assertEqual(r1.values(), r2.values())

    def test_upsample_same_interval_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            upsample(ts, 300)

    def test_upsample_coarser_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            upsample(ts, 600)

    def test_upsample_non_multiple_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            upsample(ts, 70)

    def test_upsample_empty(self):
        ts = TimeSeries(name="empty", interval=300)
        result = upsample(ts, 60)
        self.assertEqual(result.points, [])

    def test_upsample_single_point_linear(self):
        ts = _make_series("s", 300, [42.0])
        result = upsample(ts, 60, UpsampleMethod.LINEAR)
        self.assertEqual(len(result.points), 1)
        self.assertEqual(result.points[0].value, 42.0)


class DownsampleTests(unittest.TestCase):
    def test_downsample_1min_to_5min_mean(self):
        ts = _make_series("s", 60, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
        result = downsample(ts, 300, Aggregation.MEAN)
        self.assertEqual(result.interval, 300)
        self.assertEqual(len(result.points), 2)
        self.assertAlmostEqual(result.values()[0], 30.0)  # mean(10,20,30,40,50)
        self.assertAlmostEqual(result.values()[1], 60.0)

    def test_downsample_1min_to_5min_sum(self):
        ts = _make_series("s", 60, [1.0, 2.0, 3.0, 4.0, 5.0])
        result = downsample(ts, 300, Aggregation.SUM)
        self.assertEqual(result.values(), [15.0])

    def test_downsample_1min_to_5min_min(self):
        ts = _make_series("s", 60, [5.0, 3.0, 8.0, 1.0, 9.0])
        result = downsample(ts, 300, Aggregation.MIN)
        self.assertEqual(result.values(), [1.0])

    def test_downsample_1min_to_5min_max(self):
        ts = _make_series("s", 60, [5.0, 3.0, 8.0, 1.0, 9.0])
        result = downsample(ts, 300, Aggregation.MAX)
        self.assertEqual(result.values(), [9.0])

    def test_downsample_1min_to_5min_first(self):
        ts = _make_series("s", 60, [5.0, 3.0, 8.0, 1.0, 9.0])
        result = downsample(ts, 300, Aggregation.FIRST)
        self.assertEqual(result.values(), [5.0])

    def test_downsample_1min_to_5min_last(self):
        ts = _make_series("s", 60, [5.0, 3.0, 8.0, 1.0, 9.0])
        result = downsample(ts, 300, Aggregation.LAST)
        self.assertEqual(result.values(), [9.0])

    def test_downsample_1min_to_5min_count(self):
        ts = _make_series("s", 60, [5.0, 3.0, 8.0, 1.0, 9.0])
        result = downsample(ts, 300, Aggregation.COUNT)
        self.assertEqual(result.values(), [5.0])

    def test_downsample_5min_to_1hr_mean(self):
        ts = _make_series("s", 300, [10.0] * 12)
        result = downsample(ts, 3600, Aggregation.MEAN)
        self.assertEqual(result.interval, 3600)
        self.assertEqual(len(result.points), 1)
        self.assertAlmostEqual(result.values()[0], 10.0)

    def test_downsample_1min_to_15min_mean(self):
        ts = _make_series("s", 60, [float(i) for i in range(15)])
        result = downsample(ts, 900, Aggregation.MEAN)
        self.assertEqual(result.interval, 900)
        self.assertEqual(len(result.points), 1)
        self.assertAlmostEqual(result.values()[0], 7.0)  # mean(0..14)

    def test_downsample_same_interval_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            downsample(ts, 300)

    def test_downsample_finer_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            downsample(ts, 60)

    def test_downsample_non_multiple_raises(self):
        ts = _make_series("s", 300, [1.0])
        with self.assertRaises(ValueError):
            downsample(ts, 700)

    def test_downsample_empty_raises(self):
        ts = TimeSeries(name="empty", interval=60)
        with self.assertRaises(ValueError):
            downsample(ts, 300)


class ResampleTests(unittest.TestCase):
    def test_resample_same_interval(self):
        ts = _make_series("s", 300, [1.0, 2.0, 3.0])
        result = resample(ts, 300)
        self.assertEqual(result.interval, 300)
        self.assertEqual(result.values(), [1.0, 2.0, 3.0])

    def test_resample_upsample(self):
        ts = _make_series("s", 300, [1.0, 2.0])
        result = resample(ts, 60)
        self.assertEqual(result.interval, 60)
        self.assertEqual(len(result.points), 6)  # 0, 60, 120, 180, 240, 300

    def test_resample_downsample(self):
        ts = _make_series("s", 60, [1.0, 2.0, 3.0, 4.0, 5.0])
        result = resample(ts, 300)
        self.assertEqual(result.interval, 300)
        self.assertEqual(len(result.points), 1)


class AlignSeriesTests(unittest.TestCase):
    def test_align_to_coarsest(self):
        s1 = _make_series("a", 60, [1.0] * 60)
        s2 = _make_series("b", 300, [2.0] * 12)
        result = align_series([s1, s2])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].interval, 300)
        self.assertEqual(result[1].interval, 300)

    def test_align_to_specific_interval(self):
        s1 = _make_series("a", 60, [1.0] * 60)
        s2 = _make_series("b", 3600, [2.0])
        result = align_series([s1, s2], target_interval=300)
        self.assertEqual(result[0].interval, 300)
        self.assertEqual(result[1].interval, 300)

    def test_align_empty(self):
        self.assertEqual(align_series([]), [])

    def test_align_single(self):
        s1 = _make_series("a", 60, [1.0] * 10)
        result = align_series([s1])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].interval, 60)


class MergeAlignedTests(unittest.TestCase):
    def test_merge_basic(self):
        s1 = _make_series("power", 300, [100.0, 200.0, 300.0])
        s2 = _make_series("temp", 300, [20.0, 25.0, 30.0])
        rows = merge_aligned([s1, s2])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["power"], 100.0)
        self.assertEqual(rows[0]["temp"], 20.0)
        self.assertIn("timestamp", rows[0])

    def test_merge_with_gaps(self):
        s1 = TimeSeries(
            name="a",
            interval=300,
            points=[DataPoint(timestamp=_ts(0), value=1.0), DataPoint(timestamp=_ts(600), value=3.0)],
        )
        s2 = _make_series("b", 300, [10.0, 20.0, 30.0])
        rows = merge_aligned([s1, s2])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["a"], 1.0)
        self.assertIsNone(rows[1]["a"])
        self.assertEqual(rows[2]["a"], 3.0)

    def test_merge_empty(self):
        self.assertEqual(merge_aligned([]), [])

    def test_merge_different_intervals_raises(self):
        s1 = _make_series("a", 60, [1.0])
        s2 = _make_series("b", 300, [2.0])
        with self.assertRaises(ValueError):
            merge_aligned([s1, s2])


class GapDetectionTests(unittest.TestCase):
    def test_no_gaps(self):
        ts = _make_series("s", 300, [1.0, 2.0, 3.0, 4.0])
        gaps = detect_gaps(ts)
        self.assertEqual(gaps, [])

    def test_single_gap(self):
        ts = TimeSeries(
            name="s",
            interval=300,
            points=[
                DataPoint(timestamp=_ts(0), value=1.0),
                DataPoint(timestamp=_ts(300), value=2.0),
                DataPoint(timestamp=_ts(1200), value=5.0),
            ],
        )
        gaps = detect_gaps(ts)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].start, _ts(600))
        self.assertEqual(gaps[0].end, _ts(900))
        self.assertEqual(gaps[0].expected_points, 2)

    def test_multiple_gaps(self):
        ts = TimeSeries(
            name="s",
            interval=300,
            points=[
                DataPoint(timestamp=_ts(0), value=1.0),
                DataPoint(timestamp=_ts(900), value=4.0),
                DataPoint(timestamp=_ts(1200), value=5.0),
                DataPoint(timestamp=_ts(2100), value=8.0),
            ],
        )
        gaps = detect_gaps(ts)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0].expected_points, 2)
        self.assertEqual(gaps[1].expected_points, 2)

    def test_max_missing_tolerance(self):
        ts = TimeSeries(
            name="s",
            interval=300,
            points=[
                DataPoint(timestamp=_ts(0), value=1.0),
                DataPoint(timestamp=_ts(600), value=3.0),
            ],
        )
        # 1 missing point — within tolerance
        self.assertEqual(detect_gaps(ts, max_missing=1), [])
        # 0 tolerance — should report
        gaps = detect_gaps(ts, max_missing=0)
        self.assertEqual(len(gaps), 1)

    def test_empty_and_single(self):
        self.assertEqual(detect_gaps(TimeSeries(name="e", interval=300)), [])
        self.assertEqual(detect_gaps(_make_series("s", 300, [1.0])), [])


class CoverageReportTests(unittest.TestCase):
    def test_full_coverage(self):
        s1 = _make_series("a", 300, [1.0, 2.0, 3.0])
        s2 = _make_series("b", 300, [10.0, 20.0, 30.0])
        report = coverage_report([s1, s2], 300)
        self.assertTrue(report.complete)
        self.assertEqual(report.total_expected, 3)
        self.assertEqual(report.per_series["a"]["missing"], 0)
        self.assertEqual(report.per_series["b"]["missing"], 0)

    def test_partial_coverage(self):
        s1 = _make_series("a", 300, [1.0, 2.0, 3.0])
        s2 = TimeSeries(
            name="b",
            interval=300,
            points=[DataPoint(timestamp=_ts(0), value=10.0)],
        )
        report = coverage_report([s1, s2], 300)
        self.assertFalse(report.complete)
        self.assertEqual(report.per_series["b"]["missing"], 2)

    def test_empty_series_list(self):
        report = coverage_report([], 300)
        self.assertEqual(report.total_expected, 0)
        self.assertTrue(report.complete)

    def test_custom_range(self):
        s1 = _make_series("a", 300, [1.0, 2.0, 3.0])
        report = coverage_report([s1], 300, start=_ts(0), end=_ts(600))
        self.assertEqual(report.total_expected, 3)


class IntegrationTests(unittest.TestCase):
    def test_1min_5min_15min_1hr_alignment(self):
        """Full workflow: align 1min, 5min, 15min, 1hr series to 5min."""
        s1 = _make_series("1min_data", 60, [float(i) for i in range(60)])
        s2 = _make_series("5min_data", 300, [float(i * 5) for i in range(12)])
        s3 = _make_series("15min_data", 900, [float(i * 15) for i in range(4)])
        s4 = _make_series("1hr_data", 3600, [100.0, 200.0])

        aligned = align_series([s1, s2, s3, s4], target_interval=300)
        self.assertEqual(len(aligned), 4)
        for s in aligned:
            self.assertEqual(s.interval, 300)

        # 1min: 0..3300 = 12 pts; 5min: 0..3300 = 12 pts; 15min: 0..2700 = 10 pts; 1hr: 0..3600 = 13 pts
        self.assertEqual(len(aligned[0].points), 12)
        self.assertEqual(len(aligned[1].points), 12)
        self.assertEqual(len(aligned[2].points), 10)
        self.assertEqual(len(aligned[3].points), 13)

        # Merge and verify
        rows = merge_aligned(aligned)
        self.assertEqual(len(rows), 13)

    def test_downsample_then_align(self):
        """Downsample 1min to 5min, then align with native 5min."""
        s1 = _make_series("high_res", 60, [10.0, 20.0, 30.0, 40.0, 50.0])
        s2 = _make_series("low_res", 300, [30.0])

        s1_down = downsample(s1, 300, Aggregation.MEAN)
        aligned = align_series([s1_down, s2])
        self.assertEqual(aligned[0].interval, 300)
        self.assertEqual(aligned[1].interval, 300)
        self.assertEqual(aligned[0].values(), [30.0])
        self.assertEqual(aligned[1].values(), [30.0])


if __name__ == "__main__":
    unittest.main()
