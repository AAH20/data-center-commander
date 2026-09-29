"""Tests for maintenance scheduling optimization."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from dcc.forecasting.failure import AssetRiskProfile
from dcc.forecasting.load import ForecastPoint, LoadObservation
from dcc.forecasting.maintenance import (
    MaintenanceConstraint,
    MaintenanceWindow,
    build_forecast_from_observations,
    optimize_maintenance_windows,
    schedule_to_dict,
)


def _make_risk_profile(
    asset_id: str = "asset-1",
    asset_name: str = "UPS A01",
    risk_score: float = 0.7,
    risk_level: str = "high",
    criticality: str = "high",
    lifecycle_state: str = "active",
    anomaly_count: int = 5,
) -> AssetRiskProfile:
    return AssetRiskProfile(
        asset_id=asset_id,
        asset_name=asset_name,
        asset_type="ups",
        criticality=criticality,
        lifecycle_state=lifecycle_state,
        risk_score=risk_score,
        risk_level=risk_level,
        contributing_factors=["test factor"],
        metric_summaries={"temperature": {"count": 100, "mean": 45.0}},
        anomaly_count=anomaly_count,
        trend_degradation=True,
        days_since_last_reading=1,
        recommended_action="schedule_maintenance",
    )


def _make_forecast(
    *,
    peak_kw: float = 1000.0,
    low_kw: float = 400.0,
    hours: int = 48,
    interval_minutes: int = 60,
    start: datetime | None = None,
) -> list[ForecastPoint]:
    """Create a synthetic forecast with daily low-load periods."""
    if start is None:
        start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    points = []
    for i in range(hours):
        ts = start + timedelta(minutes=interval_minutes * i)
        hour_of_day = ts.hour
        # Simulate daily cycle: low at night (0-6), high during day
        if 0 <= hour_of_day < 6:
            value = low_kw
        elif 6 <= hour_of_day < 12:
            value = (peak_kw - low_kw) * 0.5 + low_kw
        elif 12 <= hour_of_day < 18:
            value = peak_kw
        else:
            value = (peak_kw - low_kw) * 0.7 + low_kw
        points.append(ForecastPoint(timestamp=ts, predicted=value))
    return points


def _make_observations(
    *,
    count: int = 168,
    interval_minutes: int = 60,
    start: datetime | None = None,
) -> list[LoadObservation]:
    """Create synthetic load observations."""
    if start is None:
        start = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
    obs = []
    for i in range(count):
        ts = start + timedelta(minutes=interval_minutes * i)
        hour_of_day = ts.hour
        if 0 <= hour_of_day < 6:
            value = 400.0
        elif 6 <= hour_of_day < 12:
            value = 700.0
        elif 12 <= hour_of_day < 18:
            value = 1000.0
        else:
            value = 800.0
        obs.append(LoadObservation(timestamp=ts, value=value, unit="kW"))
    return obs


class TestMaintenanceConstraint(unittest.TestCase):
    def test_defaults(self):
        c = MaintenanceConstraint()
        self.assertEqual(c.min_notice_hours, 24.0)
        self.assertEqual(c.max_consecutive_hours, 8.0)
        self.assertEqual(c.preferred_start_hour, 0)
        self.assertEqual(c.preferred_end_hour, 6)
        self.assertTrue(c.require_low_load)
        self.assertAlmostEqual(c.low_load_threshold_pct, 0.60)

    def test_custom_constraints(self):
        c = MaintenanceConstraint(
            min_notice_hours=48.0,
            max_consecutive_hours=4.0,
            preferred_start_hour=22,
            preferred_end_hour=4,
            blackout_weekdays=frozenset({5, 6}),
        )
        self.assertEqual(c.min_notice_hours, 48.0)
        self.assertEqual(c.max_consecutive_hours, 4.0)
        self.assertEqual(c.preferred_start_hour, 22)
        self.assertEqual(c.preferred_end_hour, 4)
        self.assertEqual(c.blackout_weekdays, frozenset({5, 6}))


class TestOptimizeMaintenanceWindows(unittest.TestCase):
    def test_basic_scheduling(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [
            _make_risk_profile("a1", "UPS A01", 0.8, "high", "critical"),
            _make_risk_profile("a2", "CRAC B01", 0.5, "medium", "high"),
            _make_risk_profile("a3", "PDU C01", 0.2, "low", "medium"),
        ]
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        self.assertEqual(schedule.tenant_id, "test-tenant")
        self.assertGreater(len(schedule.windows), 0)
        # Critical asset should be scheduled first
        self.assertEqual(schedule.windows[0].asset_id, "a1")
        self.assertEqual(schedule.windows[0].risk_level, "high")

    def test_no_forecast_no_windows(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [_make_risk_profile()]
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=[],
            now=now,
        )
        self.assertEqual(len(schedule.windows), 0)
        self.assertEqual(len(schedule.unscheduled), 1)

    def test_no_risk_profiles(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=[],
            forecast_points=forecast,
            now=now,
        )
        self.assertEqual(len(schedule.windows), 0)
        self.assertEqual(len(schedule.unscheduled), 0)

    def test_existing_windows_avoided(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [
            _make_risk_profile("a1", "UPS A01", 0.8, "high", "critical"),
            _make_risk_profile("a2", "CRAC B01", 0.7, "high", "high"),
        ]
        forecast = _make_forecast(start=now)
        # Pre-schedule a window for a1
        existing = [
            MaintenanceWindow(
                asset_id="a1",
                asset_name="UPS A01",
                start=now + timedelta(hours=1),
                end=now + timedelta(hours=5),
                duration_hours=4.0,
                predicted_load_kw=400.0,
                load_pct_of_peak=0.4,
                risk_score=0.8,
                risk_level="high",
                confidence="high",
            )
        ]
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            existing_windows=existing,
            now=now,
        )
        # Should have the existing window plus a new one for a2
        self.assertEqual(len(schedule.windows), 2)
        asset_ids = {w.asset_id for w in schedule.windows}
        self.assertIn("a1", asset_ids)
        self.assertIn("a2", asset_ids)

    def test_low_risk_with_no_low_load_goes_unscheduled(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [
            _make_risk_profile("a1", "UPS A01", 0.1, "low", "low"),
        ]
        # Forecast with no low-load periods (always high)
        forecast = [
            ForecastPoint(
                timestamp=now + timedelta(hours=i),
                predicted=1000.0,
            )
            for i in range(48)
        ]
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        self.assertEqual(len(schedule.windows), 0)
        self.assertEqual(len(schedule.unscheduled), 1)
        self.assertEqual(schedule.unscheduled[0]["asset_id"], "a1")

    def test_window_within_low_load_period(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [_make_risk_profile("a1", "UPS A01", 0.8, "high", "critical")]
        forecast = _make_forecast(start=now, peak_kw=1000.0, low_kw=400.0)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        self.assertGreater(len(schedule.windows), 0)
        window = schedule.windows[0]
        # Window should be during low-load hours (0-6)
        self.assertLess(window.load_pct_of_peak, 0.6)
        self.assertGreaterEqual(window.start.hour, 0)
        self.assertLess(window.start.hour, 12)

    def test_confidence_levels(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        # Profile with telemetry data
        profile_with_data = _make_risk_profile("a1", "UPS A01", 0.8, "high", "critical")
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=[profile_with_data],
            forecast_points=forecast,
            now=now,
        )
        if schedule.windows:
            self.assertIn(schedule.windows[0].confidence, ("high", "medium", "low"))


class TestScheduleToDict(unittest.TestCase):
    def test_serialization(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [_make_risk_profile()]
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        result = schedule_to_dict(schedule)
        self.assertEqual(result["tenant_id"], "test-tenant")
        self.assertIn("windows", result)
        self.assertIn("unscheduled", result)
        self.assertIn("summary", result)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["execution_permitted"])
        self.assertIn("total_windows", result["summary"])
        self.assertIn("total_unscheduled", result["summary"])
        self.assertIn("high_risk_scheduled", result["summary"])
        self.assertIn("mean_load_pct_of_peak", result["summary"])

    def test_window_serialization(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [_make_risk_profile()]
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        result = schedule_to_dict(schedule)
        if result["windows"]:
            w = result["windows"][0]
            self.assertIn("asset_id", w)
            self.assertIn("asset_name", w)
            self.assertIn("start", w)
            self.assertIn("end", w)
            self.assertIn("duration_hours", w)
            self.assertIn("predicted_load_kw", w)
            self.assertIn("load_pct_of_peak", w)
            self.assertIn("risk_score", w)
            self.assertIn("risk_level", w)
            self.assertIn("confidence", w)
            self.assertIn("rationale", w)
            self.assertIn("conflicts", w)


class TestBuildForecastFromObservations(unittest.TestCase):
    def test_returns_forecast_points(self):
        obs = _make_observations(count=168)
        points = build_forecast_from_observations(obs, horizon_hours=48)
        self.assertGreater(len(points), 0)
        self.assertLessEqual(len(points), 48)
        for p in points:
            self.assertIsInstance(p, ForecastPoint)
            self.assertGreater(p.predicted, 0)

    def test_empty_observations(self):
        points = build_forecast_from_observations([], horizon_hours=48)
        self.assertEqual(len(points), 0)

    def test_small_observations_fallback(self):
        obs = _make_observations(count=3)
        points = build_forecast_from_observations(obs, horizon_hours=24)
        self.assertGreater(len(points), 0)


class TestGreedyPriority(unittest.TestCase):
    def test_critical_scheduled_before_medium(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [
            _make_risk_profile("a1", "Low Risk", 0.3, "medium", "medium"),
            _make_risk_profile("a2", "Critical Risk", 0.9, "critical", "critical"),
        ]
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        self.assertGreater(len(schedule.windows), 0)
        # Critical asset should be first
        self.assertEqual(schedule.windows[0].asset_id, "a2")

    def test_higher_risk_scheduled_first(self):
        now = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        profiles = [
            _make_risk_profile("a1", "Medium", 0.5, "medium", "high"),
            _make_risk_profile("a2", "High", 0.8, "high", "high"),
        ]
        forecast = _make_forecast(start=now)
        schedule = optimize_maintenance_windows(
            tenant_id="test-tenant",
            risk_profiles=profiles,
            forecast_points=forecast,
            now=now,
        )
        self.assertGreater(len(schedule.windows), 0)
        self.assertEqual(schedule.windows[0].asset_id, "a2")


if __name__ == "__main__":
    unittest.main()
