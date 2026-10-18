"""Unit tests for dcc.quality.anomaly module."""
import unittest
import math

from dcc.quality.anomaly import (
    Anomaly,
    AnomalyReport,
    zscore_detect,
    iqr_detect,
    seasonal_decompose_detect,
    detect_all,
)


class TestAnomaly(unittest.TestCase):
    def test_creation(self):
        a = Anomaly(
            index=0,
            timestamp=100.0,
            value=10.0,
            expected=5.0,
            deviation=5.0,
            method="zscore",
            severity="high",
        )
        self.assertEqual(a.index, 0)
        self.assertEqual(a.timestamp, 100.0)
        self.assertEqual(a.value, 10.0)
        self.assertEqual(a.expected, 5.0)
        self.assertEqual(a.deviation, 5.0)
        self.assertEqual(a.method, "zscore")
        self.assertEqual(a.severity, "high")


class TestAnomalyReport(unittest.TestCase):
    def test_creation(self):
        r = AnomalyReport(method="zscore", total_points=100)
        self.assertEqual(r.method, "zscore")
        self.assertEqual(r.total_points, 100)
        self.assertEqual(r.anomalies, [])
        self.assertEqual(r.anomaly_count, 0)
        self.assertEqual(r.anomaly_rate, 0.0)

    def test_with_anomalies(self):
        a = Anomaly(index=0, timestamp=None, value=10.0, expected=5.0, deviation=5.0, method="zscore", severity="high")
        r = AnomalyReport(method="zscore", total_points=100, anomalies=[a])
        self.assertEqual(r.anomaly_count, 1)
        self.assertAlmostEqual(r.anomaly_rate, 0.01)

    def test_to_dict(self):
        a = Anomaly(index=0, timestamp=None, value=10.0, expected=5.0, deviation=5.0, method="zscore", severity="high")
        r = AnomalyReport(method="zscore", total_points=100, anomalies=[a])
        d = r.to_dict()
        self.assertEqual(d["method"], "zscore")
        self.assertEqual(d["total_points"], 100)
        self.assertEqual(d["anomaly_count"], 1)
        self.assertEqual(len(d["anomalies"]), 1)


class TestZscoreDetect(unittest.TestCase):
    def test_no_anomalies(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = zscore_detect(values)
        self.assertIsInstance(result, AnomalyReport)

    def test_with_anomalies(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        result = zscore_detect(values)
        self.assertIsInstance(result, AnomalyReport)
        self.assertGreater(result.anomaly_count, 0)

    def test_empty_values(self):
        with self.assertRaises(ValueError):
            zscore_detect([])

    def test_with_timestamps(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        timestamps = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = zscore_detect(values, timestamps=timestamps)
        self.assertIsInstance(result, AnomalyReport)

    def test_custom_threshold(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        result = zscore_detect(values, threshold=2.0)
        self.assertIsInstance(result, AnomalyReport)


class TestIqrDetect(unittest.TestCase):
    def test_no_anomalies(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = iqr_detect(values)
        self.assertIsInstance(result, AnomalyReport)

    def test_with_anomalies(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        result = iqr_detect(values)
        self.assertIsInstance(result, AnomalyReport)

    def test_empty_values(self):
        with self.assertRaises(ValueError):
            iqr_detect([])


class TestSeasonalDecomposeDetect(unittest.TestCase):
    def test_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        result = seasonal_decompose_detect(values, period=3)
        self.assertIsInstance(result, AnomalyReport)

    def test_with_anomalies(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        result = seasonal_decompose_detect(values, period=3)
        self.assertIsInstance(result, AnomalyReport)


class TestDetectAll(unittest.TestCase):
    def test_detect_all(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        result = detect_all(values)
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
