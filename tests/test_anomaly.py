"""Tests for statistical anomaly detection."""
import math
import unittest

from dcc.quality.anomaly import (
    Anomaly,
    AnomalyReport,
    detect_all,
    iqr_detect,
    seasonal_decompose_detect,
    zscore_detect,
)


class ZScoreTests(unittest.TestCase):
    def test_detects_obvious_outlier(self):
        values = [10.0] * 20 + [100.0] + [10.0] * 20
        report = zscore_detect(values, threshold=3.0)
        self.assertEqual(report.method, "zscore")
        self.assertEqual(report.total_points, 41)
        self.assertGreaterEqual(report.anomaly_count, 1)
        # The outlier at index 20 should be detected
        outlier_indices = [a.index for a in report.anomalies]
        self.assertIn(20, outlier_indices)

    def test_no_anomalies_in_uniform_data(self):
        values = [10.0] * 50
        report = zscore_detect(values, threshold=3.0)
        self.assertEqual(report.anomaly_count, 0)

    def test_severity_classification(self):
        values = [0.0] * 30 + [100.0]
        report = zscore_detect(values, threshold=2.0)
        self.assertGreaterEqual(report.anomaly_count, 1)
        # A value of 100 among zeros should be high severity
        for a in report.anomalies:
            if a.index == 30:
                self.assertEqual(a.severity, "high")

    def test_rolling_window(self):
        # Non-stationary: first half ~10, second half ~100
        values = [10.0 + i * 0.1 for i in range(50)] + [100.0 + i * 0.1 for i in range(50)]
        report = zscore_detect(values, threshold=3.0, window=10)
        self.assertEqual(report.method, "zscore_rolling")
        self.assertEqual(report.total_points, 100)

    def test_with_timestamps(self):
        values = [1.0, 2.0, 3.0, 100.0, 2.0]
        timestamps = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
        report = zscore_detect(values, timestamps, threshold=2.0)
        for a in report.anomalies:
            if a.index == 3:
                self.assertEqual(a.timestamp, 4000.0)

    def test_empty_values_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([])

    def test_none_in_values_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([1.0, None, 3.0])

    def test_non_finite_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([1.0, float("nan"), 3.0])
        with self.assertRaises(ValueError):
            zscore_detect([1.0, float("inf"), 3.0])

    def test_invalid_threshold_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([1.0, 2.0, 3.0], threshold=0)
        with self.assertRaises(ValueError):
            zscore_detect([1.0, 2.0, 3.0], threshold=-1)

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([1.0, 2.0, 3.0], window=1)

    def test_timestamp_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            zscore_detect([1.0, 2.0, 3.0], timestamps=[1.0, 2.0])

    def test_to_dict_serializable(self):
        values = [1.0] * 10 + [50.0]
        report = zscore_detect(values, threshold=2.0)
        d = report.to_dict()
        self.assertIn("method", d)
        self.assertIn("anomaly_count", d)
        self.assertIn("anomalies", d)
        self.assertIn("statistics", d)
        # Should be JSON-serializable
        import json
        json.dumps(d)


class IQRTests(unittest.TestCase):
    def test_detects_outliers(self):
        values = list(range(1, 101)) + [200, -100]
        report = iqr_detect(values, k=1.5)
        self.assertEqual(report.method, "iqr")
        self.assertEqual(report.total_points, 102)
        outlier_indices = [a.index for a in report.anomalies]
        self.assertIn(100, outlier_indices)  # 200
        self.assertIn(101, outlier_indices)  # -100

    def test_no_outliers_in_normal_data(self):
        values = list(range(1, 101))
        report = iqr_detect(values, k=1.5)
        self.assertEqual(report.anomaly_count, 0)

    def test_extreme_k_finds_fewer_outliers(self):
        values = list(range(1, 101)) + [200]
        report_15 = iqr_detect(values, k=1.5)
        report_30 = iqr_detect(values, k=3.0)
        self.assertGreaterEqual(report_15.anomaly_count, report_30.anomaly_count)

    def test_statistics_populated(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        report = iqr_detect(values)
        self.assertIn("q1", report.statistics)
        self.assertIn("q3", report.statistics)
        self.assertIn("iqr", report.statistics)
        self.assertIn("lower_fence", report.statistics)
        self.assertIn("upper_fence", report.statistics)

    def test_invalid_k_raises(self):
        with self.assertRaises(ValueError):
            iqr_detect([1.0, 2.0, 3.0], k=0)
        with self.assertRaises(ValueError):
            iqr_detect([1.0, 2.0, 3.0], k=-1)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            iqr_detect([])


class SeasonalDecomposeTests(unittest.TestCase):
    def test_detects_anomaly_in_seasonal_data(self):
        # Create data with daily seasonality (period=24) and one anomaly
        values = []
        for day in range(5):
            for hour in range(24):
                # Sinusoidal pattern with amplitude 10, mean 50
                values.append(50 + 10 * math.sin(2 * math.pi * hour / 24))
        # Inject anomaly at hour 12 of day 3
        values[3 * 24 + 12] = 200.0
        report = seasonal_decompose_detect(values, period=24, threshold=3.0)
        self.assertEqual(report.method, "seasonal_decompose")
        self.assertEqual(report.total_points, 120)
        self.assertGreaterEqual(report.anomaly_count, 1)
        # The injected anomaly should be detected
        anomaly_indices = [a.index for a in report.anomalies]
        self.assertIn(3 * 24 + 12, anomaly_indices)

    def test_few_anomalies_in_clean_seasonal_data(self):
        values = []
        for day in range(5):
            for hour in range(24):
                values.append(50 + 10 * math.sin(2 * math.pi * hour / 24))
        report = seasonal_decompose_detect(values, period=24, threshold=3.0)
        # Edge effects in moving average may cause a few false positives
        self.assertLess(report.anomaly_count, 10)

    def test_requires_two_full_periods(self):
        values = [1.0] * 10
        with self.assertRaises(ValueError):
            seasonal_decompose_detect(values, period=24)

    def test_invalid_period_raises(self):
        values = [1.0] * 50
        with self.assertRaises(ValueError):
            seasonal_decompose_detect(values, period=1)

    def test_invalid_threshold_raises(self):
        values = [1.0] * 50
        with self.assertRaises(ValueError):
            seasonal_decompose_detect(values, period=24, threshold=0)

    def test_statistics_populated(self):
        values = []
        for day in range(5):
            for hour in range(24):
                values.append(50 + 10 * math.sin(2 * math.pi * hour / 24))
        report = seasonal_decompose_detect(values, period=24)
        self.assertIn("period", report.statistics)
        self.assertIn("residual_mean", report.statistics)
        self.assertIn("residual_std", report.statistics)
        self.assertIn("seasonal_amplitude", report.statistics)


class DetectAllTests(unittest.TestCase):
    def test_returns_all_methods(self):
        values = [10.0] * 30 + [100.0] + [10.0] * 30
        results = detect_all(values, seasonal_period=7)
        self.assertIn("zscore", results)
        self.assertIn("iqr", results)
        self.assertIn("seasonal", results)
        self.assertIsInstance(results["zscore"], AnomalyReport)
        self.assertIsInstance(results["iqr"], AnomalyReport)
        self.assertIsInstance(results["seasonal"], AnomalyReport)

    def test_all_detect_injected_anomaly(self):
        values = [10.0] * 30 + [100.0] + [10.0] * 30
        results = detect_all(values, seasonal_period=7)
        for method, report in results.items():
            with self.subTest(method=method):
                self.assertGreaterEqual(report.anomaly_count, 1)


class AnomalyDataclassTests(unittest.TestCase):
    def test_anomaly_fields(self):
        a = Anomaly(
            index=5,
            timestamp=1000.0,
            value=42.0,
            expected=10.0,
            deviation=3.2,
            method="zscore",
            severity="high",
        )
        self.assertEqual(a.index, 5)
        self.assertEqual(a.timestamp, 1000.0)
        self.assertEqual(a.value, 42.0)
        self.assertEqual(a.expected, 10.0)
        self.assertEqual(a.deviation, 3.2)
        self.assertEqual(a.method, "zscore")
        self.assertEqual(a.severity, "high")

    def test_anomaly_report_defaults(self):
        r = AnomalyReport(method="test", total_points=10)
        self.assertEqual(r.anomaly_count, 0)
        self.assertEqual(r.anomaly_rate, 0.0)
        self.assertEqual(r.anomalies, [])
        self.assertEqual(r.statistics, {})

    def test_anomaly_rate_calculation(self):
        r = AnomalyReport(
            method="test",
            total_points=100,
            anomalies=[
                Anomaly(0, None, 1, 0, 1, "test", "low"),
                Anomaly(1, None, 1, 0, 1, "test", "low"),
            ],
        )
        self.assertEqual(r.anomaly_count, 2)
        self.assertAlmostEqual(r.anomaly_rate, 0.02)


if __name__ == "__main__":
    unittest.main()
