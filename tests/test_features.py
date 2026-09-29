"""Tests for the time-series feature extraction engine."""
import math
import unittest

from dcc.forecasting.features import (
    LagFeature,
    RollingStats,
    SeasonalDecomposition,
    TrendResult,
    detect_trend,
    extract_features,
    lag_features,
    rolling_stats,
    seasonal_decompose,
)


class RollingStatsTests(unittest.TestCase):
    def test_basic_rolling_window(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = rolling_stats(values, window=3)
        self.assertEqual(len(result), 3)
        # First result at index 2: window [1, 2, 3]
        self.assertEqual(result[0].index, 2)
        self.assertEqual(result[0].mean, 2.0)
        self.assertEqual(result[0].min, 1.0)
        self.assertEqual(result[0].max, 3.0)
        self.assertEqual(result[0].median, 2.0)
        self.assertEqual(result[0].count, 3)

    def test_rolling_with_min_periods(self):
        values = [10.0, 20.0, 30.0]
        result = rolling_stats(values, window=3, min_periods=1)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].index, 0)
        self.assertEqual(result[0].mean, 10.0)
        self.assertEqual(result[1].mean, 15.0)
        self.assertEqual(result[2].mean, 20.0)

    def test_rolling_std(self):
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = rolling_stats(values, window=8)
        self.assertEqual(len(result), 1)
        # Population std of [2,4,4,4,5,5,7,9] = 2.0, sample std = 2.138...
        self.assertAlmostEqual(result[0].mean, 5.0)
        self.assertGreater(result[0].std, 2.0)
        self.assertLess(result[0].std, 2.2)

    def test_rolling_percentiles(self):
        values = list(range(1, 101))  # 1..100
        result = rolling_stats(values, window=100)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].p05, 5.95, places=1)
        self.assertAlmostEqual(result[0].p95, 95.05, places=1)

    def test_rolling_with_nan_values(self):
        values = [1.0, float("nan"), 3.0, 4.0, 5.0]
        result = rolling_stats(values, window=3, min_periods=2)
        # Index 1: window [1, nan] -> only 1 valid, skip
        # Index 2: window [1, nan, 3] -> 2 valid
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].index, 2)
        self.assertEqual(result[0].count, 2)

    def test_rolling_empty_series(self):
        result = rolling_stats([], window=3)
        self.assertEqual(result, [])

    def test_rolling_window_larger_than_series(self):
        values = [1.0, 2.0]
        result = rolling_stats(values, window=5, min_periods=1)
        self.assertEqual(len(result), 2)

    def test_invalid_window(self):
        with self.assertRaises(ValueError):
            rolling_stats([1.0], window=0)
        with self.assertRaises(ValueError):
            rolling_stats([1.0], window=-1)

    def test_invalid_min_periods(self):
        with self.assertRaises(ValueError):
            rolling_stats([1.0], window=3, min_periods=0)


class LagFeatureTests(unittest.TestCase):
    def test_basic_lags(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = lag_features(values, lags=[1, 2])
        self.assertEqual(len(result), 5)
        # Index 0: lag1=None, lag2=None
        self.assertIsNone(result[0][0].value)
        self.assertIsNone(result[0][1].value)
        # Index 1: lag1=10, lag2=None
        self.assertEqual(result[1][0].value, 10.0)
        self.assertIsNone(result[1][1].value)
        # Index 2: lag1=20, lag2=10
        self.assertEqual(result[2][0].value, 20.0)
        self.assertEqual(result[2][1].value, 10.0)
        # Index 4: lag1=40, lag2=30
        self.assertEqual(result[4][0].value, 40.0)
        self.assertEqual(result[4][1].value, 30.0)

    def test_lag_with_nan(self):
        values = [1.0, float("nan"), 3.0]
        result = lag_features(values, lags=[1])
        self.assertEqual(result[0][0].value, None)
        self.assertEqual(result[1][0].value, 1.0)
        # lag of NaN should be None
        self.assertIsNone(result[2][0].value)

    def test_single_lag(self):
        values = [5.0, 10.0, 15.0]
        result = lag_features(values, lags=[1])
        self.assertEqual(len(result), 3)
        self.assertEqual(len(result[0]), 1)

    def test_empty_lags_raises(self):
        with self.assertRaises(ValueError):
            lag_features([1.0, 2.0], lags=[])

    def test_invalid_lag_raises(self):
        with self.assertRaises(ValueError):
            lag_features([1.0, 2.0], lags=[0])
        with self.assertRaises(ValueError):
            lag_features([1.0, 2.0], lags=[-1])


class SeasonalDecompositionTests(unittest.TestCase):
    def test_basic_decomposition(self):
        # Simple series with period=4: [1,2,3,4, 1,2,3,4, 1,2,3,4]
        values = [1.0, 2.0, 3.0, 4.0] * 3
        result = seasonal_decompose(values, period=4)
        self.assertEqual(len(result.trend), 12)
        self.assertEqual(len(result.seasonal), 12)
        self.assertEqual(len(result.residual), 12)
        self.assertEqual(result.period, 4)

    def test_seasonal_pattern_recovery(self):
        # Series: trend + seasonal + noise
        # trend: 0,1,2,...,11
        # seasonal (period=4): +1, 0, -1, 0
        seasonal = [1.0, 0.0, -1.0, 0.0]
        values = [float(i) + seasonal[i % 4] for i in range(12)]
        result = seasonal_decompose(values, period=4)
        # Seasonal component should roughly match the pattern
        for i in range(12):
            expected_seasonal = seasonal[i % 4]
            self.assertAlmostEqual(result.seasonal[i], expected_seasonal, delta=0.5)

    def test_trend_recovery(self):
        # Pure linear trend, no seasonality
        values = [float(i) for i in range(20)]
        result = seasonal_decompose(values, period=4)
        # Trend should be close to the original values
        for i in range(2, 18):
            t = result.trend[i]
            if t is not None:
                self.assertAlmostEqual(t, float(i), delta=1.0)

    def test_residual_near_zero_for_perfect_seasonal(self):
        # Perfect repeating pattern
        values = [1.0, 2.0, 3.0, 4.0] * 5
        result = seasonal_decompose(values, period=4)
        # Residuals should be near zero where trend is defined
        for i in range(2, 18):
            r = result.residual[i]
            if r is not None:
                self.assertAlmostEqual(r, 0.0, delta=0.1)

    def test_insufficient_data(self):
        values = [1.0, 2.0]
        result = seasonal_decompose(values, period=4)
        self.assertEqual(len(result.trend), 2)
        self.assertTrue(all(t is None for t in result.trend))

    def test_even_period(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = seasonal_decompose(values, period=4)
        self.assertEqual(len(result.trend), 8)

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            seasonal_decompose([1.0, 2.0], period=1)
        with self.assertRaises(ValueError):
            seasonal_decompose([1.0, 2.0], period=0)

    def test_seasonal_centered(self):
        # Seasonal profile should have mean ~0
        values = [float(i) + [2.0, 0.0, -2.0, 0.0][i % 4] for i in range(20)]
        result = seasonal_decompose(values, period=4)
        # Average of seasonal component should be near zero
        seasonal_mean = sum(result.seasonal) / len(result.seasonal)
        self.assertAlmostEqual(seasonal_mean, 0.0, delta=0.1)


class TrendDetectionTests(unittest.TestCase):
    def test_increasing_trend(self):
        values = [float(i) for i in range(20)]
        result = detect_trend(values)
        self.assertEqual(result.direction, "increasing")
        self.assertGreater(result.slope, 0)
        self.assertGreater(result.r_squared, 0.99)
        self.assertIsNotNone(result.p_value)
        assert result.p_value is not None
        self.assertLess(result.p_value, 0.01)

    def test_decreasing_trend(self):
        values = [float(20 - i) for i in range(20)]
        result = detect_trend(values)
        self.assertEqual(result.direction, "decreasing")
        self.assertLess(result.slope, 0)

    def test_flat_trend(self):
        values = [5.0] * 20
        result = detect_trend(values)
        self.assertEqual(result.direction, "flat")
        self.assertAlmostEqual(result.slope, 0.0)

    def test_noisy_flat_trend(self):
        import random
        random.seed(42)
        values = [5.0 + random.gauss(0, 0.5) for _ in range(50)]
        result = detect_trend(values)
        self.assertEqual(result.direction, "flat")

    def test_mann_kendall_increasing(self):
        values = [float(i) for i in range(30)]
        result = detect_trend(values, mk=True)
        self.assertIsNotNone(result.mann_kendall_tau)
        self.assertIsNotNone(result.mann_kendall_p)
        assert result.mann_kendall_tau is not None
        assert result.mann_kendall_p is not None
        self.assertGreater(result.mann_kendall_tau, 0.9)
        self.assertLess(result.mann_kendall_p, 0.001)

    def test_mann_kendall_decreasing(self):
        values = [float(30 - i) for i in range(30)]
        result = detect_trend(values, mk=True)
        self.assertIsNotNone(result.mann_kendall_tau)
        assert result.mann_kendall_tau is not None
        self.assertLess(result.mann_kendall_tau, -0.9)

    def test_change_point_detection(self):
        # Series with a clear shift at index 15
        values = [1.0] * 15 + [10.0] * 15
        result = detect_trend(values, change_points=True)
        self.assertTrue(len(result.change_points) > 0)
        # Change point should be near index 14-15
        self.assertTrue(any(13 <= cp <= 16 for cp in result.change_points))

    def test_no_change_points_in_stable_series(self):
        import random
        random.seed(42)
        values = [5.0 + random.gauss(0, 0.3) for _ in range(30)]
        result = detect_trend(values, change_points=True)
        self.assertEqual(len(result.change_points), 0)

    def test_short_series(self):
        result = detect_trend([1.0])
        self.assertEqual(result.direction, "flat")
        self.assertIsNone(result.p_value)

    def test_two_point_series(self):
        result = detect_trend([1.0, 2.0])
        self.assertIsNotNone(result.slope)
        self.assertIsNone(result.p_value)

    def test_invalid_alpha(self):
        with self.assertRaises(ValueError):
            detect_trend([1.0, 2.0, 3.0], alpha=0.0)
        with self.assertRaises(ValueError):
            detect_trend([1.0, 2.0, 3.0], alpha=1.0)

    def test_with_nan_values(self):
        values = [1.0, 2.0, float("nan"), 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = detect_trend(values)
        self.assertEqual(result.direction, "increasing")

    def test_r_squared_perfect_linear(self):
        values = [2.0 * i + 1.0 for i in range(20)]
        result = detect_trend(values)
        self.assertAlmostEqual(result.r_squared, 1.0, places=5)

    def test_intercept(self):
        values = [2.0 * i + 5.0 for i in range(20)]
        result = detect_trend(values)
        self.assertAlmostEqual(result.intercept, 5.0, delta=0.1)


class ExtractFeaturesTests(unittest.TestCase):
    def test_extract_all(self):
        values = [float(i) for i in range(30)]
        result = extract_features(values, window=7, lags=[1, 7], period=7)
        self.assertIn("rolling", result)
        self.assertIn("lags", result)
        self.assertIn("seasonal", result)
        self.assertIn("trend", result)
        self.assertIsInstance(result["rolling"][0], RollingStats)
        self.assertIsInstance(result["lags"][0][0], LagFeature)
        self.assertIsInstance(result["seasonal"], SeasonalDecomposition)
        self.assertIsInstance(result["trend"], TrendResult)

    def test_extract_with_defaults(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = extract_features(values)
        self.assertEqual(len(result["rolling"]), 4)  # window=7, 10-7+1=4
        self.assertEqual(len(result["lags"]), 10)
        self.assertEqual(len(result["seasonal"].trend), 10)


class EdgeCaseTests(unittest.TestCase):
    def test_all_nan(self):
        values = [float("nan")] * 10
        result = detect_trend(values)
        self.assertEqual(result.direction, "flat")

    def test_single_value(self):
        result = detect_trend([42.0])
        self.assertEqual(result.direction, "flat")
        self.assertEqual(result.slope, 0.0)

    def test_empty_series_rolling(self):
        result = rolling_stats([], window=3)
        self.assertEqual(result, [])

    def test_empty_series_lags(self):
        result = lag_features([], lags=[1])
        self.assertEqual(result, [])

    def test_empty_series_seasonal(self):
        result = seasonal_decompose([], period=4)
        self.assertEqual(len(result.trend), 0)

    def test_very_large_values(self):
        values = [1e15 + i for i in range(20)]
        result = detect_trend(values)
        self.assertEqual(result.direction, "increasing")

    def test_very_small_values(self):
        values = [1e-15 * i for i in range(20)]
        result = detect_trend(values)
        self.assertEqual(result.direction, "increasing")

    def test_mixed_positive_negative(self):
        values = [(-1.0) ** i * float(i) for i in range(20)]
        result = detect_trend(values)
        # Should not crash
        self.assertIn(result.direction, ("increasing", "decreasing", "flat"))


if __name__ == "__main__":
    unittest.main()
