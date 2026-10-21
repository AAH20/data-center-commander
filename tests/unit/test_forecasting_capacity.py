"""Unit tests for dcc.forecasting.capacity module."""
import unittest
from datetime import datetime, timezone

from dcc.forecasting.capacity import (
    CapacityDataPoint,
    ForecastPoint,
    CapacityForecast,
    FORECASTABLE_DIMENSIONS,
    MIN_POINTS_LINEAR,
    MIN_POINTS_MOVING_AVG,
    MIN_POINTS_EXP_SMOOTHING,
    MAX_DAILY_GROWTH_RATE,
    MIN_COVERAGE_FOR_FORECAST,
    forecast_capacity,
    forecast_from_snapshots,
    select_best_method,
    compute_capacity_at_risk,
)


class TestCapacityDataPoint(unittest.TestCase):
    def test_creation(self):
        dp = CapacityDataPoint(
            observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            usable=100.0,
            reserved=50.0,
            policy_reserve=10.0,
            forecast_peak=None,
            quality_status="good",
            scenario="base",
        )
        self.assertEqual(dp.usable, 100.0)
        self.assertEqual(dp.committed, 60.0)
        self.assertAlmostEqual(dp.headroom, 40.0)
        self.assertAlmostEqual(dp.utilization, 0.6)

    def test_zero_usable(self):
        dp = CapacityDataPoint(
            observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            usable=0.0,
            reserved=0.0,
            policy_reserve=0.0,
            forecast_peak=None,
            quality_status="good",
            scenario="base",
        )
        self.assertEqual(dp.utilization, 0.0)


class TestForecastPoint(unittest.TestCase):
    def test_creation(self):
        fp = ForecastPoint(
            target_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            predicted_value=100.0,
            lower_bound=90.0,
            upper_bound=110.0,
            method="linear",
            confidence=0.9,
        )
        self.assertEqual(fp.predicted_value, 100.0)
        self.assertEqual(fp.confidence, 0.9)


class TestCapacityForecast(unittest.TestCase):
    def test_creation(self):
        cf = CapacityForecast(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="base",
            method="linear",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            data_points_used=10,
            history_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            history_end=datetime(2024, 1, 10, tzinfo=timezone.utc),
            forecast_horizon_days=30,
        )
        self.assertEqual(cf.facility_id, "f1")
        self.assertEqual(cf.dimension, "power_kw")

    def test_to_dict(self):
        cf = CapacityForecast(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="base",
            method="linear",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            data_points_used=10,
            history_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            history_end=datetime(2024, 1, 10, tzinfo=timezone.utc),
            forecast_horizon_days=30,
        )
        d = cf.to_dict()
        self.assertEqual(d["facility_id"], "f1")
        self.assertEqual(d["dimension"], "power_kw")


class TestForecastableDimensions(unittest.TestCase):
    def test_dimensions(self):
        self.assertIn("power_kw", FORECASTABLE_DIMENSIONS)
        self.assertIn("cooling_kw", FORECASTABLE_DIMENSIONS)
        self.assertIn("rack_u", FORECASTABLE_DIMENSIONS)


class TestForecastCapacity(unittest.TestCase):
    def test_forecast(self):
        points = [
            CapacityDataPoint(
                observed_at=datetime(2024, 1, i, tzinfo=timezone.utc),
                usable=100.0 + i,
                reserved=50.0,
                policy_reserve=10.0,
                forecast_peak=None,
                quality_status="good",
                scenario="base",
            )
            for i in range(1, 11)
        ]
        result = forecast_capacity(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="base",
            data_points=points,
            horizon_days=30,
        )
        self.assertIsInstance(result, CapacityForecast)


class TestForecastFromSnapshots(unittest.TestCase):
    def test_forecast(self):
        # forecast_from_snapshots is the raw-dict adapter: it parses snapshot
        # dicts (not CapacityDataPoint objects) and hands them to forecast_capacity.
        snapshots = [
            {
                "observed_at": datetime(2024, 1, i, tzinfo=timezone.utc),
                "usable": 100.0 + i,
                "reserved": 50.0,
                "policy_reserve": 10.0,
                "forecast_peak": None,
                "quality_status": "good",
                "scenario": "base",
            }
            for i in range(1, 11)
        ]
        result = forecast_from_snapshots(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="base",
            snapshots=snapshots,
            horizon_days=30,
        )
        self.assertIsInstance(result, CapacityForecast)
        self.assertEqual(result.data_points_used, len(snapshots))


class TestSelectBestMethod(unittest.TestCase):
    def test_select(self):
        points = [
            CapacityDataPoint(
                observed_at=datetime(2024, 1, i, tzinfo=timezone.utc),
                usable=100.0 + i,
                reserved=50.0,
                policy_reserve=10.0,
                forecast_peak=None,
                quality_status="good",
                scenario="base",
            )
            for i in range(1, 11)
        ]
        method = select_best_method(points)
        self.assertIsInstance(method, str)


class TestComputeCapacityAtRisk(unittest.TestCase):
    def test_compute(self):
        points = [
            CapacityDataPoint(
                observed_at=datetime(2024, 1, i, tzinfo=timezone.utc),
                usable=100.0 + i,
                reserved=50.0,
                policy_reserve=10.0,
                forecast_peak=None,
                quality_status="good",
                scenario="base",
            )
            for i in range(1, 11)
        ]
        forecast = forecast_capacity(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="base",
            data_points=points,
            horizon_days=30,
        )
        # compute_capacity_at_risk takes an existing forecast plus the capacity
        # threshold to breach, and returns a report dict (not a scalar float).
        result = compute_capacity_at_risk(forecast, threshold=110.0)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["threshold"], 110.0)
        self.assertEqual(result["dimension"], "power_kw")
        self.assertIn(result["severity"], {"none", "low", "medium", "high"})
        self.assertFalse(result["execution_permitted"])


if __name__ == "__main__":
    unittest.main()
