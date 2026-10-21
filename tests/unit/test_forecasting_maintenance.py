"""Unit tests for dcc.forecasting.maintenance module."""
import unittest
from datetime import datetime, timezone

from dcc.forecasting.maintenance import (
    MaintenanceConstraint,
    MaintenanceWindow,
    MaintenanceSchedule,
    optimize_maintenance_windows,
    schedule_to_dict,
    build_forecast_from_observations,
)


class TestMaintenanceConstraint(unittest.TestCase):
    def test_creation(self):
        c = MaintenanceConstraint()
        self.assertEqual(c.min_notice_hours, 24.0)
        self.assertEqual(c.max_consecutive_hours, 8.0)

    def test_custom(self):
        c = MaintenanceConstraint(
            min_notice_hours=48.0,
            max_consecutive_hours=12.0,
            preferred_start_hour=2,
            preferred_end_hour=6,
        )
        self.assertEqual(c.min_notice_hours, 48.0)
        self.assertEqual(c.preferred_start_hour, 2)


class TestMaintenanceWindow(unittest.TestCase):
    def test_creation(self):
        w = MaintenanceWindow(
            asset_id="a1",
            asset_name="Server 1",
            start=datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            predicted_load_kw=50.0,
            load_pct_of_peak=0.3,
            risk_score=0.7,
            risk_level="high",
            confidence="medium",
        )
        self.assertEqual(w.asset_id, "a1")
        self.assertEqual(w.duration_hours, 4.0)

    def test_with_rationale(self):
        w = MaintenanceWindow(
            asset_id="a1",
            asset_name="Server 1",
            start=datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            predicted_load_kw=50.0,
            load_pct_of_peak=0.3,
            risk_score=0.7,
            risk_level="high",
            confidence="medium",
            rationale=["low_load_period"],
        )
        self.assertEqual(len(w.rationale), 1)


class TestMaintenanceSchedule(unittest.TestCase):
    def test_creation(self):
        s = MaintenanceSchedule(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            horizon_days=30,
        )
        self.assertEqual(s.tenant_id, "t1")
        self.assertEqual(s.windows, [])

    def test_with_windows(self):
        w = MaintenanceWindow(
            asset_id="a1",
            asset_name="Server 1",
            start=datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            predicted_load_kw=50.0,
            load_pct_of_peak=0.3,
            risk_score=0.7,
            risk_level="high",
            confidence="medium",
        )
        s = MaintenanceSchedule(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            horizon_days=30,
            windows=[w],
        )
        self.assertEqual(len(s.windows), 1)


class TestOptimizeMaintenanceWindows(unittest.TestCase):
    def test_optimize(self):
        from dcc.forecasting.failure import AssetRiskProfile
        from dcc.forecasting.load import ForecastPoint

        assets = [
            AssetRiskProfile(
                asset_id="a1",
                asset_name="Server 1",
                asset_type="server",
                criticality="high",
                lifecycle_state="production",
                risk_score=0.7,
                risk_level="high",
            ),
        ]
        forecast = [
            ForecastPoint(
                timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc),
                predicted=100.0 - i * 5,
            )
            for i in range(24)
        ]
        constraints = MaintenanceConstraint()
        # Signature is keyword-only and tenant-scoped: tenant_id + risk_profiles
        # (not "assets"). Anchor "now" to the forecast window.
        result = optimize_maintenance_windows(
            tenant_id="t1",
            risk_profiles=assets,
            forecast_points=forecast,
            constraints=constraints,
            now=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self.assertIsInstance(result, MaintenanceSchedule)
        self.assertEqual(result.tenant_id, "t1")


class TestScheduleToDict(unittest.TestCase):
    def test_to_dict(self):
        s = MaintenanceSchedule(
            tenant_id="t1",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            horizon_days=30,
        )
        d = schedule_to_dict(s)
        self.assertIsInstance(d, dict)
        self.assertEqual(d["tenant_id"], "t1")


class TestBuildForecastFromObservations(unittest.TestCase):
    def test_build(self):
        from dcc.forecasting.load import LoadObservation

        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=100.0 - i * 2)
            for i in range(24)
        ]
        result = build_forecast_from_observations(obs)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
