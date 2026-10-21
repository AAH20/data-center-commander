"""Unit tests for dcc.forecasting.drift module."""
import unittest
from datetime import datetime, timezone

from dcc.forecasting.drift import (
    DriftMethod,
    DriftSeverity,
    DriftThresholds,
    DriftResult,
    ModelPerformanceSnapshot,
    DriftDetector,
    PerformanceTracker,
    detect_drift,
    compute_psi,
    compute_ks_statistic,
)


class TestDriftMethod(unittest.TestCase):
    def test_method_values(self):
        self.assertEqual(DriftMethod.PSI.value, "psi")
        self.assertEqual(DriftMethod.KS.value, "ks")
        self.assertEqual(DriftMethod.CUSUM.value, "cusum")
        self.assertEqual(DriftMethod.ERROR_RATE.value, "error_rate")
        self.assertEqual(DriftMethod.MEAN_SHIFT.value, "mean_shift")
        self.assertEqual(DriftMethod.VARIANCE_SHIFT.value, "variance_shift")


class TestDriftSeverity(unittest.TestCase):
    def test_severity_values(self):
        self.assertEqual(DriftSeverity.NONE.value, "none")
        self.assertEqual(DriftSeverity.LOW.value, "low")
        self.assertEqual(DriftSeverity.MEDIUM.value, "medium")
        self.assertEqual(DriftSeverity.HIGH.value, "high")
        self.assertEqual(DriftSeverity.CRITICAL.value, "critical")


class TestDriftThresholds(unittest.TestCase):
    def test_defaults(self):
        t = DriftThresholds()
        self.assertEqual(t.psi_low, 0.10)
        self.assertEqual(t.psi_high, 0.20)
        self.assertEqual(t.ks_alpha, 0.05)


class TestDriftResult(unittest.TestCase):
    def test_creation(self):
        r = DriftResult(
            method=DriftMethod.PSI,
            severity=DriftSeverity.LOW,
            score=0.15,
            threshold=0.10,
            detected=True,
        )
        self.assertEqual(r.method, DriftMethod.PSI)
        self.assertTrue(r.detected)

    def test_to_dict(self):
        r = DriftResult(
            method=DriftMethod.PSI,
            severity=DriftSeverity.LOW,
            score=0.15,
            threshold=0.10,
            detected=True,
        )
        d = r.to_dict()
        self.assertEqual(d["method"], "psi")
        self.assertTrue(d["detected"])


class TestModelPerformanceSnapshot(unittest.TestCase):
    def test_creation(self):
        s = ModelPerformanceSnapshot(
            model_id="m1",
            tenant_id="t1",
            window_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )
        self.assertEqual(s.model_id, "m1")
        self.assertEqual(s.predictions, 0)

    def test_compute_derived(self):
        s = ModelPerformanceSnapshot(
            model_id="m1",
            tenant_id="t1",
            window_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            errors=[1.0, -1.0, 2.0, -2.0],
        )
        s.compute_derived()
        self.assertIsNotNone(s.mae)
        self.assertIsNotNone(s.rmse)
        self.assertIsNotNone(s.bias)


class TestDriftDetector(unittest.TestCase):
    def test_creation(self):
        d = DriftDetector()
        self.assertIsNotNone(d)

    def test_detect(self):
        d = DriftDetector()
        reference = [float(i) for i in range(100)]
        current = [float(i) + 10 for i in range(100)]
        # detect() only takes the incoming window; the baseline is installed
        # separately via set_reference().
        d.set_reference(reference)
        result = d.detect(current)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(r, DriftResult) for r in result))
        self.assertTrue(any(r.detected for r in result))


class TestPerformanceTracker(unittest.TestCase):
    def test_creation(self):
        # PerformanceTracker is per-model/tenant, so both ids are required.
        t = PerformanceTracker(model_id="m1", tenant_id="t1")
        self.assertIsNotNone(t)
        self.assertIsNone(t.reference)

    def test_record(self):
        t = PerformanceTracker(model_id="m1", tenant_id="t1", reference_windows=2)
        t.record(
            ModelPerformanceSnapshot(
                model_id="m1",
                tenant_id="t1",
                window_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                window_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
                predictions=2,
                actuals=2,
                errors=[0.1, 0.1],
            )
        )
        # snapshot_count is a property, not a method.
        self.assertEqual(t.snapshot_count, 1)


class TestDetectDrift(unittest.TestCase):
    def test_detect(self):
        reference = [float(i) for i in range(100)]
        current = [float(i) for i in range(100)]
        # Module-level detect_drift runs every enabled method and returns one
        # DriftResult per method.
        result = detect_drift(reference, current)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertTrue(all(isinstance(r, DriftResult) for r in result))
        # Identical distributions: the distribution-comparing methods must stay
        # quiet. CUSUM is deliberately order-sensitive and does alarm on a
        # monotone ramp, so it is excluded from this check.
        by_method = {r.method: r for r in result}
        self.assertFalse(by_method[DriftMethod.MEAN_SHIFT].detected)
        self.assertFalse(by_method[DriftMethod.PSI].detected)


class TestComputePsi(unittest.TestCase):
    def test_psi(self):
        reference = [float(i) for i in range(100)]
        current = [float(i) for i in range(100)]
        result = compute_psi(reference, current)
        self.assertGreaterEqual(result, 0)


class TestComputeKsStatistic(unittest.TestCase):
    def test_ks(self):
        reference = [float(i) for i in range(100)]
        current = [float(i) for i in range(100)]
        # Returns a (statistic, p_value) tuple.
        result = compute_ks_statistic(reference, current)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        statistic, p_value = result
        self.assertGreaterEqual(statistic, 0.0)
        self.assertGreaterEqual(p_value, 0.0)
        self.assertLessEqual(p_value, 1.0)


if __name__ == "__main__":
    unittest.main()
