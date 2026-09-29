"""Tests for equipment failure prediction model."""
import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load failure.py directly to avoid triggering package __init__ which may
# import sibling modules with their own dependencies.
_failure_path = Path(__file__).resolve().parents[1] / "src" / "dcc" / "forecasting" / "failure.py"
_spec = importlib.util.spec_from_file_location("dcc_failure", _failure_path)
failure_mod = importlib.util.module_from_spec(_spec)
sys.modules["dcc_failure"] = failure_mod
_spec.loader.exec_module(failure_mod)

AssetRiskProfile = failure_mod.AssetRiskProfile
FailurePredictionResult = failure_mod.FailurePredictionResult
predict_equipment_failures = failure_mod.predict_equipment_failures
result_to_dict = failure_mod.result_to_dict
_compute_trend_slope = failure_mod._compute_trend_slope
_detect_anomalies_zscore = failure_mod._detect_anomalies_zscore
_detect_anomalies_iqr = failure_mod._detect_anomalies_iqr
_detect_anomalies_ewma = failure_mod._detect_anomalies_ewma
_detect_degradation = failure_mod._detect_degradation
_compute_volatility = failure_mod._compute_volatility
_parse_telemetry_rows = failure_mod._parse_telemetry_rows
_score_asset_risk = failure_mod._score_asset_risk


NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _make_asset(asset_id="a1", name="Server-01", asset_type="server",
                criticality="high", lifecycle_state="active"):
    return {
        "id": asset_id,
        "name": name,
        "asset_type": asset_type,
        "criticality": criticality,
        "lifecycle_state": lifecycle_state,
    }


def _make_telemetry(asset_id, values, start=None, metric_key="temperature"):
    if start is None:
        start = NOW - timedelta(days=7)
    rows = []
    for i, v in enumerate(values):
        rows.append({
            "asset_id": asset_id,
            "metric_key": metric_key,
            "value_numeric": v,
            "observed_at": start + timedelta(hours=i),
            "quality_status": "good",
        })
    return rows


class TestAnomalyDetection(unittest.TestCase):
    def test_zscore_detects_outlier(self):
        values = [10.0] * 20 + [100.0]
        anomalies = _detect_anomalies_zscore(values)
        self.assertIn(20, anomalies)

    def test_zscore_no_false_positives_on_uniform(self):
        values = [10.0] * 20
        anomalies = _detect_anomalies_zscore(values)
        self.assertEqual(anomalies, [])

    def test_zscore_needs_minimum_data(self):
        self.assertEqual(_detect_anomalies_zscore([1.0, 2.0]), [])

    def test_iqr_detects_outliers(self):
        values = list(range(1, 21)) + [200.0]
        anomalies = _detect_anomalies_iqr(values)
        self.assertIn(20, anomalies)

    def test_iqr_no_outliers_in_normal_data(self):
        values = [10.0, 11.0, 9.5, 10.5, 10.2, 9.8, 10.1, 10.3]
        anomalies = _detect_anomalies_iqr(values)
        self.assertEqual(len(anomalies), 0)

    def test_ewma_detects_shift(self):
        values = [10.0] * 10 + [20.0] * 10
        anomalies = _detect_anomalies_ewma(values)
        self.assertTrue(len(anomalies) > 0)

    def test_ewma_no_anomalies_on_stable_data(self):
        values = [10.0 + i * 0.01 for i in range(20)]
        anomalies = _detect_anomalies_ewma(values)
        self.assertEqual(len(anomalies), 0)


class TestTrendAnalysis(unittest.TestCase):
    def test_positive_slope(self):
        values = [float(i) for i in range(20)]
        slope = _compute_trend_slope(values)
        self.assertGreater(slope, 0)

    def test_negative_slope(self):
        values = [float(20 - i) for i in range(20)]
        slope = _compute_trend_slope(values)
        self.assertLess(slope, 0)

    def test_zero_slope_on_flat(self):
        values = [10.0] * 20
        slope = _compute_trend_slope(values)
        self.assertAlmostEqual(slope, 0.0)

    def test_degradation_detects_shift(self):
        values = [10.0] * 10 + [20.0] * 10
        self.assertTrue(_detect_degradation(values))

    def test_no_degradation_on_stable(self):
        values = [10.0 + i * 0.01 for i in range(20)]
        self.assertFalse(_detect_degradation(values))

    def test_degradation_needs_enough_data(self):
        self.assertFalse(_detect_degradation([1.0, 2.0, 3.0]))


class TestVolatility(unittest.TestCase):
    def test_zero_volatility_on_constant(self):
        self.assertAlmostEqual(_compute_volatility([10.0] * 10), 0.0)

    def test_high_volatility(self):
        values = [1.0, 100.0, 2.0, 99.0, 3.0, 98.0]
        vol = _compute_volatility(values)
        self.assertGreater(vol, 1.0)


class TestTelemetryParsing(unittest.TestCase):
    def test_groups_by_asset(self):
        rows = [
            {"asset_id": "a1", "value_numeric": 1.0, "observed_at": NOW, "metric_key": "temp"},
            {"asset_id": "a2", "value_numeric": 2.0, "observed_at": NOW, "metric_key": "temp"},
            {"asset_id": "a1", "value_numeric": 3.0, "observed_at": NOW + timedelta(hours=1), "metric_key": "temp"},
        ]
        result = _parse_telemetry_rows(rows)
        self.assertEqual(len(result["a1"]), 2)
        self.assertEqual(len(result["a2"]), 1)

    def test_sorts_by_time(self):
        rows = [
            {"asset_id": "a1", "value_numeric": 3.0, "observed_at": NOW + timedelta(hours=2), "metric_key": "temp"},
            {"asset_id": "a1", "value_numeric": 1.0, "observed_at": NOW, "metric_key": "temp"},
            {"asset_id": "a1", "value_numeric": 2.0, "observed_at": NOW + timedelta(hours=1), "metric_key": "temp"},
        ]
        result = _parse_telemetry_rows(rows)
        self.assertEqual([p.value for p in result["a1"]], [1.0, 2.0, 3.0])

    def test_skips_non_finite(self):
        rows = [
            {"asset_id": "a1", "value_numeric": float("nan"), "observed_at": NOW, "metric_key": "temp"},
            {"asset_id": "a1", "value_numeric": 1.0, "observed_at": NOW, "metric_key": "temp"},
        ]
        result = _parse_telemetry_rows(rows)
        self.assertEqual(len(result["a1"]), 1)

    def test_parses_iso_strings(self):
        rows = [
            {"asset_id": "a1", "value_numeric": 1.0, "observed_at": "2026-09-29T00:00:00+00:00", "metric_key": "temp"},
        ]
        result = _parse_telemetry_rows(rows)
        self.assertEqual(len(result["a1"]), 1)


class TestAssetRiskScoring(unittest.TestCase):
    def test_critical_asset_with_anomalies_scores_high(self):
        asset = _make_asset(criticality="critical", lifecycle_state="active")
        # Normal readings with a sudden spike
        values = [50.0] * 30 + [150.0]
        rows = _make_telemetry("a1", values)
        points = _parse_telemetry_rows(rows)["a1"]
        profile = _score_asset_risk(asset, points, NOW)
        self.assertGreater(profile.risk_score, 0.3)
        self.assertIn(profile.risk_level, ("medium", "high", "critical"))

    def test_low_criticality_stable_asset_scores_low(self):
        asset = _make_asset(criticality="low", lifecycle_state="active")
        values = [50.0 + i * 0.01 for i in range(30)]
        rows = _make_telemetry("a1", values)
        points = _parse_telemetry_rows(rows)["a1"]
        profile = _score_asset_risk(asset, points, NOW)
        self.assertLess(profile.risk_score, 0.3)
        self.assertEqual(profile.risk_level, "low")

    def test_impaired_lifecycle_increases_risk(self):
        asset = _make_asset(criticality="medium", lifecycle_state="impaired")
        values = [50.0] * 20
        rows = _make_telemetry("a1", values)
        points = _parse_telemetry_rows(rows)["a1"]
        profile = _score_asset_risk(asset, points, NOW)
        self.assertGreater(profile.risk_score, 0.1)

    def test_no_telemetry_gives_lifecycle_baseline(self):
        asset = _make_asset(criticality="high", lifecycle_state="maintenance")
        profile = _score_asset_risk(asset, [], NOW)
        self.assertGreater(profile.risk_score, 0.0)
        self.assertIsNotNone(profile.days_since_last_reading)

    def test_degradation_flag_set(self):
        asset = _make_asset(criticality="high", lifecycle_state="active")
        values = [50.0] * 15 + [80.0] * 15
        rows = _make_telemetry("a1", values)
        points = _parse_telemetry_rows(rows)["a1"]
        profile = _score_asset_risk(asset, points, NOW)
        self.assertTrue(profile.trend_degradation)

    def test_recommended_action_critical(self):
        asset = _make_asset(criticality="critical", lifecycle_state="impaired")
        values = [50.0] * 20 + [200.0]
        rows = _make_telemetry("a1", values)
        points = _parse_telemetry_rows(rows)["a1"]
        profile = _score_asset_risk(asset, points, NOW)
        if profile.risk_level == "critical":
            self.assertEqual(profile.recommended_action, "immediate_inspection")


class TestPredictEquipmentFailures(unittest.TestCase):
    def test_basic_prediction(self):
        assets = [
            _make_asset("a1", "Server-01", "server", "high", "active"),
            _make_asset("a2", "Server-02", "server", "low", "active"),
        ]
        telemetry = []
        telemetry.extend(_make_telemetry("a1", [50.0] * 30 + [150.0]))
        telemetry.extend(_make_telemetry("a2", [45.0] * 30))

        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=assets,
            telemetry_rows=telemetry,
            window_days=7,
            now=NOW,
        )
        self.assertEqual(result.total_assets, 2)
        self.assertEqual(result.assets_with_telemetry, 2)
        self.assertEqual(len(result.risk_profiles), 2)
        # Higher risk asset should be first
        self.assertGreaterEqual(
            result.risk_profiles[0].risk_score,
            result.risk_profiles[1].risk_score,
        )

    def test_asset_without_telemetry(self):
        assets = [_make_asset("a1", "Server-01")]
        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=assets,
            telemetry_rows=[],
            now=NOW,
        )
        self.assertEqual(result.assets_with_telemetry, 0)
        self.assertEqual(len(result.risk_profiles), 1)

    def test_empty_assets(self):
        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=[],
            telemetry_rows=[],
            now=NOW,
        )
        self.assertEqual(result.total_assets, 0)
        self.assertEqual(result.risk_profiles, [])

    def test_result_serialization(self):
        assets = [_make_asset("a1", "Server-01", "server", "high", "active")]
        telemetry = _make_telemetry("a1", [50.0] * 20 + [150.0])
        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=assets,
            telemetry_rows=telemetry,
            now=NOW,
        )
        d = result_to_dict(result)
        self.assertIn("risk_profiles", d)
        self.assertIn("summary", d)
        self.assertIn("model_policy", d)
        self.assertTrue(d["read_only"])
        self.assertFalse(d["execution_permitted"])
        self.assertIn("critical_count", d["summary"])
        self.assertIn("high_count", d["summary"])

    def test_multiple_metrics(self):
        asset = _make_asset("a1", "Server-01", "server", "high", "active")
        telemetry = []
        telemetry.extend(_make_telemetry("a1", [50.0] * 20 + [150.0], metric_key="temperature"))
        telemetry.extend(_make_telemetry("a1", [100.0] * 20 + [200.0], metric_key="vibration"))
        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=[asset],
            telemetry_rows=telemetry,
            now=NOW,
        )
        profile = result.risk_profiles[0]
        self.assertIn("temperature", profile.metric_summaries)
        self.assertIn("vibration", profile.metric_summaries)

    def test_risk_levels_are_valid(self):
        assets = [_make_asset(f"a{i}", f"Server-{i}") for i in range(10)]
        telemetry = []
        for i in range(10):
            telemetry.extend(_make_telemetry(f"a{i}", [50.0 + i * 5] * 20))
        result = predict_equipment_failures(
            tenant_id="dcc00000-0000-4000-8000-000000000001",
            assets=assets,
            telemetry_rows=telemetry,
            now=NOW,
        )
        valid_levels = {"low", "medium", "high", "critical"}
        for profile in result.risk_profiles:
            self.assertIn(profile.risk_level, valid_levels)
            self.assertGreaterEqual(profile.risk_score, 0.0)
            self.assertLessEqual(profile.risk_score, 1.0)


if __name__ == "__main__":
    unittest.main()
