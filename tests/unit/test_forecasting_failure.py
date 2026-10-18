"""Unit tests for dcc.forecasting.failure module."""
import unittest
from datetime import datetime, timezone

from dcc.forecasting.failure import (
    TelemetryPoint,
    AssetRiskProfile,
    FailurePredictionResult,
    predict_equipment_failures,
    result_to_dict,
)


class TestTelemetryPoint(unittest.TestCase):
    def test_creation(self):
        tp = TelemetryPoint(
            observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            value=100.0,
        )
        self.assertEqual(tp.value, 100.0)
        self.assertEqual(tp.quality_status, "good")

    def test_with_metric_key(self):
        tp = TelemetryPoint(
            observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            value=100.0,
            metric_key="temperature",
        )
        self.assertEqual(tp.metric_key, "temperature")


class TestAssetRiskProfile(unittest.TestCase):
    def test_creation(self):
        p = AssetRiskProfile(
            asset_id="a1",
            asset_name="Server 1",
            asset_type="server",
            criticality="high",
            lifecycle_state="production",
            risk_score=0.7,
            risk_level="high",
        )
        self.assertEqual(p.asset_id, "a1")
        self.assertEqual(p.risk_score, 0.7)

    def test_contributing_factors(self):
        p = AssetRiskProfile(
            asset_id="a1",
            asset_name="Server 1",
            asset_type="server",
            criticality="high",
            lifecycle_state="production",
            risk_score=0.7,
            risk_level="high",
            contributing_factors=["high_temp", "old_age"],
        )
        self.assertEqual(len(p.contributing_factors), 2)

    def test_recommended_action(self):
        p = AssetRiskProfile(
            asset_id="a1",
            asset_name="Server 1",
            asset_type="server",
            criticality="high",
            lifecycle_state="production",
            risk_score=0.7,
            risk_level="high",
            recommended_action="replace",
        )
        self.assertEqual(p.recommended_action, "replace")


class TestFailurePredictionResult(unittest.TestCase):
    def test_creation(self):
        r = FailurePredictionResult(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            window_days=30,
            total_assets=100,
            assets_with_telemetry=80,
        )
        self.assertEqual(r.tenant_id, "t1")
        self.assertEqual(r.total_assets, 100)

    def test_with_profiles(self):
        p = AssetRiskProfile(
            asset_id="a1",
            asset_name="Server 1",
            asset_type="server",
            criticality="high",
            lifecycle_state="production",
            risk_score=0.7,
            risk_level="high",
        )
        r = FailurePredictionResult(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            window_days=30,
            total_assets=100,
            assets_with_telemetry=80,
            risk_profiles=[p],
        )
        self.assertEqual(len(r.risk_profiles), 1)


class TestPredictEquipmentFailures(unittest.TestCase):
    def test_predict(self):
        rows = [
            {"asset_id": "a1", "value_numeric": 100.0, "observed_at": "2024-01-01T00:00:00Z", "metric_key": "temperature"},
            {"asset_id": "a1", "value_numeric": 105.0, "observed_at": "2024-01-01T01:00:00Z", "metric_key": "temperature"},
        ]
        assets = [
            {"asset_id": "a1", "name": "Server 1", "asset_type": "server", "criticality": "high", "lifecycle_state": "production"},
        ]
        result = predict_equipment_failures(
            tenant_id="t1",
            telemetry_rows=rows,
            assets=assets,
        )
        self.assertIsInstance(result, FailurePredictionResult)

    def test_empty_telemetry(self):
        result = predict_equipment_failures(
            tenant_id="t1",
            telemetry_rows=[],
            assets=[],
        )
        self.assertIsInstance(result, FailurePredictionResult)


class TestResultToDict(unittest.TestCase):
    def test_to_dict(self):
        r = FailurePredictionResult(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            window_days=30,
            total_assets=100,
            assets_with_telemetry=80,
        )
        d = result_to_dict(r)
        self.assertIsInstance(d, dict)
        self.assertEqual(d["tenant_id"], "t1")


if __name__ == "__main__":
    unittest.main()
