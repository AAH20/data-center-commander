"""Unit tests for dcc.forecasting.features module."""
import unittest

from dcc.forecasting.features import (
    RollingStats,
    LagFeature,
    SeasonalDecomposition,
    TrendResult,
    rolling_stats,
    lag_features,
    seasonal_decompose,
    detect_trend,
    extract_features,
)


class TestRollingStats(unittest.TestCase):
    def test_creation(self):
        rs = RollingStats(
            index=5,
            window_start=0,
            window_end=5,
            count=5,
            mean=10.0,
            std=2.0,
            min=8.0,
            max=12.0,
            median=10.0,
            p05=8.5,
            p95=11.5,
        )
        self.assertEqual(rs.index, 5)
        self.assertEqual(rs.mean, 10.0)


class TestLagFeature(unittest.TestCase):
    def test_creation(self):
        lf = LagFeature(index=5, lag=1, value=10.0)
        self.assertEqual(lf.index, 5)
        self.assertEqual(lf.lag, 1)
        self.assertEqual(lf.value, 10.0)

    def test_none_value(self):
        lf = LagFeature(index=0, lag=1, value=None)
        self.assertIsNone(lf.value)


class TestSeasonalDecomposition(unittest.TestCase):
    def test_creation(self):
        sd = SeasonalDecomposition(
            trend=[1.0, 2.0, 3.0],
            seasonal=[0.1, 0.2, 0.3],
            residual=[0.0, 0.0, 0.0],
            period=3,
        )
        self.assertEqual(len(sd.trend), 3)
        self.assertEqual(sd.period, 3)


class TestTrendResult(unittest.TestCase):
    def test_creation(self):
        tr = TrendResult(
            slope=1.0,
            intercept=0.0,
            r_squared=0.95,
            p_value=0.01,
            direction="increasing",
        )
        self.assertEqual(tr.slope, 1.0)
        self.assertEqual(tr.direction, "increasing")


class TestRollingStats(unittest.TestCase):
    def test_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_stats(values, window=3)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_window_size(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_stats(values, window=3)
        self.assertIsInstance(result, list)


class TestLagFeatures(unittest.TestCase):
    def test_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = lag_features(values, lags=[1, 2])
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_single_lag(self):
        values = [1.0, 2.0, 3.0]
        result = lag_features(values, lags=[1])
        self.assertIsInstance(result, list)


class TestSeasonalDecompose(unittest.TestCase):
    def test_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = seasonal_decompose(values, period=3)
        self.assertIsInstance(result, SeasonalDecomposition)
        self.assertEqual(result.period, 3)

    def test_with_nans(self):
        values = [1.0, 2.0, float("nan"), 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = seasonal_decompose(values, period=3)
        self.assertIsInstance(result, SeasonalDecomposition)


class TestDetectTrend(unittest.TestCase):
    def test_increasing(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = detect_trend(values)
        self.assertIsInstance(result, TrendResult)
        self.assertEqual(result.direction, "increasing")

    def test_decreasing(self):
        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = detect_trend(values)
        self.assertIsInstance(result, TrendResult)
        self.assertEqual(result.direction, "decreasing")

    def test_flat(self):
        values = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = detect_trend(values)
        self.assertIsInstance(result, TrendResult)
        self.assertEqual(result.direction, "flat")


class TestExtractFeatures(unittest.TestCase):
    def test_extract(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = extract_features(values)
        self.assertIsInstance(result, dict)

    def test_with_seasonality(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = extract_features(values, seasonality=3)
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
