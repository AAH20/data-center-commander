"""Tests for model drift detection."""
import math
import unittest
from datetime import datetime, timedelta, timezone

import importlib.util
import sys
from pathlib import Path

# Direct import to avoid broken __init__.py chain from parallel modules
_drift_path = str(Path(__file__).resolve().parents[1] / "src" / "dcc" / "forecasting" / "drift.py")
_spec = importlib.util.spec_from_file_location("dcc_drift", _drift_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["dcc_drift"] = _mod
_spec.loader.exec_module(_mod)

DriftDetector = _mod.DriftDetector
DriftMethod = _mod.DriftMethod
DriftResult = _mod.DriftResult
DriftSeverity = _mod.DriftSeverity
DriftThresholds = _mod.DriftThresholds
ModelPerformanceSnapshot = _mod.ModelPerformanceSnapshot
PerformanceTracker = _mod.PerformanceTracker
compute_ks_statistic = _mod.compute_ks_statistic
compute_psi = _mod.compute_psi
detect_drift = _mod.detect_drift


def _normal_samples(n: int, mean: float = 0.0, std: float = 1.0, seed: int = 42) -> list[float]:
    """Deterministic pseudo-normal samples (Box-Muller)."""
    import random
    rng = random.Random(seed)
    samples = []
    while len(samples) < n:
        u1 = max(rng.random(), 1e-10)
        u2 = rng.random()
        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        samples.append(mean + std * z)
    return samples


class TestPSI(unittest.TestCase):
    def test_identical_distributions_low_psi(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=0, std=1, seed=2)
        psi = compute_psi(ref, inc)
        self.assertLess(psi, 0.1)

    def test_shifted_distribution_high_psi(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=3, std=1, seed=2)
        psi = compute_psi(ref, inc)
        self.assertGreater(psi, 0.2)

    def test_empty_inputs_return_zero(self):
        self.assertEqual(compute_psi([], []), 0.0)
        self.assertEqual(compute_psi([1.0], []), 0.0)


class TestKS(unittest.TestCase):
    def test_identical_distributions_high_pvalue(self):
        ref = _normal_samples(200, seed=1)
        inc = _normal_samples(200, seed=2)
        stat, p = compute_ks_statistic(ref, inc)
        self.assertGreater(p, 0.05)

    def test_different_distributions_low_pvalue(self):
        ref = _normal_samples(200, mean=0, seed=1)
        inc = _normal_samples(200, mean=5, seed=2)
        stat, p = compute_ks_statistic(ref, inc)
        self.assertLess(p, 0.05)


class TestDriftDetector(unittest.TestCase):
    def test_requires_reference(self):
        det = DriftDetector(min_samples=10)
        with self.assertRaises(RuntimeError):
            det.detect([1.0] * 20)

    def test_requires_min_samples(self):
        det = DriftDetector(min_samples=50)
        with self.assertRaises(ValueError):
            det.set_reference([1.0] * 10)

    def test_no_drift_for_similar_data(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=0, std=1, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        for r in results:
            self.assertFalse(r.detected, f"{r.method.value} falsely detected drift")

    def test_detects_mean_shift(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=2, std=1, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        mean_shift = next(r for r in results if r.method == DriftMethod.MEAN_SHIFT)
        self.assertTrue(mean_shift.detected)
        self.assertIn(mean_shift.severity, (DriftSeverity.LOW, DriftSeverity.HIGH))

    def test_detects_variance_shift(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=0, std=3, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        var_shift = next(r for r in results if r.method == DriftMethod.VARIANCE_SHIFT)
        self.assertTrue(var_shift.detected)

    def test_psi_detects_distribution_change(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=1.5, std=1.5, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        psi_result = next(r for r in results if r.method == DriftMethod.PSI)
        self.assertTrue(psi_result.detected)

    def test_cusum_detects_sustained_shift(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=1.0, std=1, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        cusum = next(r for r in results if r.method == DriftMethod.CUSUM)
        self.assertTrue(cusum.detected)

    def test_custom_thresholds(self):
        thresholds = DriftThresholds(psi_low=0.01, psi_high=0.05)
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=0.5, std=1, seed=2)
        results = detect_drift(ref, inc, min_samples=30, thresholds=thresholds)
        psi_result = next(r for r in results if r.method == DriftMethod.PSI)
        self.assertTrue(psi_result.detected)

    def test_result_serialization(self):
        result = DriftResult(
            method=DriftMethod.PSI,
            severity=DriftSeverity.LOW,
            score=0.15,
            threshold=0.1,
            detected=True,
            details={"test": True},
        )
        d = result.to_dict()
        self.assertEqual(d["method"], "psi")
        self.assertEqual(d["severity"], "low")
        self.assertTrue(d["detected"])
        self.assertIn("timestamp", d)

    def test_history_tracking(self):
        det = DriftDetector(min_samples=30)
        ref = _normal_samples(200, seed=1)
        det.set_reference(ref)
        det.detect(_normal_samples(200, seed=2))
        det.detect(_normal_samples(200, seed=3))
        self.assertEqual(len(det.history), 2 * len(det.methods))

    def test_summary(self):
        det = DriftDetector(min_samples=30)
        ref = _normal_samples(200, seed=1)
        det.set_reference(ref)
        det.detect(_normal_samples(200, seed=2))
        s = det.summary()
        self.assertGreater(s["total_checks"], 0)
        self.assertIn("by_severity", s)
        self.assertIn("by_method", s)


class TestPerformanceSnapshot(unittest.TestCase):
    def test_compute_derived(self):
        snap = ModelPerformanceSnapshot(
            model_id="m1",
            tenant_id="t1",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            errors=[1.0, -2.0, 3.0, -4.0],
            metadata={"actual_values": [10.0, 10.0, 10.0, 10.0]},
        )
        snap.compute_derived()
        assert snap.mae is not None
        assert snap.rmse is not None
        assert snap.bias is not None
        self.assertAlmostEqual(snap.mae, 2.5)
        self.assertAlmostEqual(snap.rmse, math.sqrt(7.5))
        self.assertAlmostEqual(snap.bias, -0.5)
        self.assertIsNotNone(snap.mape)

    def test_empty_errors(self):
        snap = ModelPerformanceSnapshot(
            model_id="m1",
            tenant_id="t1",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
        )
        snap.compute_derived()
        self.assertIsNone(snap.mae)


class TestPerformanceTracker(unittest.TestCase):
    def test_tracks_snapshots(self):
        tracker = PerformanceTracker("model1", "tenant1", window_size=5, reference_windows=3)
        now = datetime.now(timezone.utc)
        for i in range(10):
            snap = ModelPerformanceSnapshot(
                model_id="model1",
                tenant_id="tenant1",
                window_start=now + timedelta(hours=i),
                window_end=now + timedelta(hours=i + 1),
                errors=_normal_samples(50, mean=0, std=1, seed=i),
            )
            snap.compute_derived()
            tracker.record(snap)
        self.assertEqual(tracker.snapshot_count, 10)
        self.assertIsNotNone(tracker.reference)

    def test_detects_degradation(self):
        tracker = PerformanceTracker("model1", "tenant1", window_size=5, reference_windows=3)
        now = datetime.now(timezone.utc)
        # Record good performance
        for i in range(5):
            snap = ModelPerformanceSnapshot(
                model_id="model1",
                tenant_id="tenant1",
                window_start=now + timedelta(hours=i),
                window_end=now + timedelta(hours=i + 1),
                errors=_normal_samples(50, mean=0, std=1, seed=i),
            )
            snap.compute_derived()
            tracker.record(snap)
        # Record degraded performance
        results = []
        for i in range(5, 8):
            snap = ModelPerformanceSnapshot(
                model_id="model1",
                tenant_id="tenant1",
                window_start=now + timedelta(hours=i),
                window_end=now + timedelta(hours=i + 1),
                errors=_normal_samples(50, mean=5, std=3, seed=i),
            )
            snap.compute_derived()
            results.extend(tracker.record(snap))
        # At least one method should detect drift
        self.assertTrue(any(r.detected for r in results))


class TestDriftThresholds(unittest.TestCase):
    def test_defaults(self):
        t = DriftThresholds()
        self.assertEqual(t.psi_low, 0.10)
        self.assertEqual(t.psi_high, 0.20)
        self.assertEqual(t.ks_alpha, 0.05)

    def test_custom(self):
        t = DriftThresholds(psi_low=0.05, cusum_threshold=3.0)
        self.assertEqual(t.psi_low, 0.05)
        self.assertEqual(t.cusum_threshold, 3.0)


class TestEdgeCases(unittest.TestCase):
    def test_constant_reference(self):
        ref = [5.0] * 100
        inc = [5.0] * 100
        results = detect_drift(ref, inc, min_samples=30)
        for r in results:
            self.assertFalse(r.detected)

    def test_single_value_incoming(self):
        ref = _normal_samples(100, seed=1)
        det = DriftDetector(min_samples=30)
        det.set_reference(ref)
        with self.assertRaises(ValueError):
            det.detect([1.0])

    def test_very_large_shift(self):
        ref = _normal_samples(200, mean=0, std=1, seed=1)
        inc = _normal_samples(200, mean=100, std=1, seed=2)
        results = detect_drift(ref, inc, min_samples=30)
        # At least one method should detect the massive shift
        self.assertTrue(any(r.detected for r in results))

    def test_get_recent_detections_filter(self):
        det = DriftDetector(min_samples=30)
        ref = _normal_samples(200, seed=1)
        det.set_reference(ref)
        det.detect(_normal_samples(200, seed=2))
        recent = det.get_recent_detections(severity=DriftSeverity.NONE)
        self.assertIsInstance(recent, list)


if __name__ == "__main__":
    unittest.main()
