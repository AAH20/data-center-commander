"""Tests for capacity demand forecasting."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from dcc.forecasting.capacity import (
    CapacityDataPoint,
    FORECASTABLE_DIMENSIONS,
    forecast_capacity,
    forecast_from_snapshots,
    select_best_method,
    compute_capacity_at_risk,
)


def _make_points(
    values: list[float],
    *,
    start_date: datetime | None = None,
    scenario: str = "test-scenario",
    quality: str = "good",
) -> list[CapacityDataPoint]:
    """Helper to create a list of CapacityDataPoint with daily spacing."""
    if start_date is None:
        start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = []
    for i, val in enumerate(values):
        points.append(
            CapacityDataPoint(
                observed_at=start_date + timedelta(days=i),
                usable=val,
                reserved=val * 0.6,
                policy_reserve=val * 0.1,
                forecast_peak=val * 0.8,
                quality_status=quality,
                scenario=scenario,
            )
        )
    return points


class CapacityForecastTests(unittest.TestCase):
    def test_linear_forecast_with_steady_growth(self):
        """Linear method should capture steady growth trend."""
        points = _make_points([100, 110, 120, 130, 140, 150, 160])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
            method="linear",
        )
        self.assertEqual(result.facility_id, "fac-001")
        self.assertEqual(result.dimension, "power_kw")
        self.assertEqual(result.method, "linear")
        self.assertEqual(len(result.forecast_points), 7)
        self.assertTrue(result.execution_permitted is False)
        # With steady growth, quality should be good
        self.assertIn(result.quality_status, ("good", "estimated"))
        # Last forecast point should be higher than last actual
        last_forecast = result.forecast_points[-1]
        self.assertGreater(last_forecast.predicted_value, 160)

    def test_forecast_respects_horizon_bounds(self):
        """Forecast should generate exactly horizon_days points."""
        points = _make_points([100, 110, 120])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=14,
            method="linear",
        )
        self.assertEqual(len(result.forecast_points), 14)
        # Check dates are consecutive days
        for i in range(1, len(result.forecast_points)):
            diff = (
                result.forecast_points[i].target_date
                - result.forecast_points[i - 1].target_date
            ).days
            self.assertEqual(diff, 1)

    def test_forecast_never_predicts_negative_capacity(self):
        """Forecast values should never be negative."""
        points = _make_points([10, 8, 6, 4, 2])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
            method="linear",
        )
        for point in result.forecast_points:
            self.assertGreaterEqual(point.predicted_value, 0.0)
            self.assertGreaterEqual(point.lower_bound, 0.0)

    def test_confidence_decreases_with_horizon(self):
        """Confidence should decrease as we forecast further out."""
        points = _make_points([100, 110, 120, 130, 140, 150, 160])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=30,
            method="linear",
        )
        # First point should have higher confidence than last
        self.assertGreater(
            result.forecast_points[0].confidence,
            result.forecast_points[-1].confidence,
        )

    def test_prediction_interval_widens_with_horizon(self):
        """Uncertainty bands should widen further into the future."""
        points = _make_points([100, 110, 120, 130, 140, 150, 160])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=30,
            method="linear",
        )
        first_width = (
            result.forecast_points[0].upper_bound - result.forecast_points[0].lower_bound
        )
        last_width = (
            result.forecast_points[-1].upper_bound - result.forecast_points[-1].lower_bound
        )
        self.assertGreater(last_width, first_width)

    def test_moving_average_method(self):
        """Moving average should produce flat forecast."""
        points = _make_points([100, 110, 120, 130, 140])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
            method="moving_average",
        )
        self.assertEqual(result.method, "moving_average")
        # All predictions should be the same (flat forecast)
        predicted_values = [p.predicted_value for p in result.forecast_points]
        self.assertTrue(all(v == predicted_values[0] for v in predicted_values))

    def test_exponential_smoothing_method(self):
        """Exponential smoothing should produce flat forecast."""
        points = _make_points([100, 110, 120, 130, 140])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
            method="exponential_smoothing",
        )
        self.assertEqual(result.method, "exponential_smoothing")
        predicted_values = [p.predicted_value for p in result.forecast_points]
        self.assertTrue(all(v == predicted_values[0] for v in predicted_values))

    def test_invalid_dimension_rejected(self):
        """Non-forecastable dimensions should be rejected."""
        points = _make_points([100, 110, 120])
        with self.assertRaises(ValueError, msg="dimension"):
            forecast_capacity(
                facility_id="fac-001",
                dimension="invalid_dimension",
                unit="kW",
                scenario="baseline",
                data_points=points,
            )

    def test_invalid_horizon_rejected(self):
        """Out-of-range horizons should be rejected."""
        points = _make_points([100, 110, 120])
        for bad_horizon in (0, -1, 366, 1000):
            with self.assertRaises(ValueError, msg="horizon"):
                forecast_capacity(
                    facility_id="fac-001",
                    dimension="power_kw",
                    unit="kW",
                    scenario="baseline",
                    data_points=points,
                    horizon_days=bad_horizon,
                )

    def test_insufficient_data_rejected(self):
        """Too few data points should be rejected."""
        points = _make_points([100])
        with self.assertRaises(ValueError, msg="data points"):
            forecast_capacity(
                facility_id="fac-001",
                dimension="power_kw",
                unit="kW",
                scenario="baseline",
                data_points=points,
                method="linear",
            )

    def test_all_forecastable_dimensions_accepted(self):
        """All defined forecastable dimensions should be accepted."""
        points = _make_points([100, 110, 120])
        for dim in FORECASTABLE_DIMENSIONS:
            result = forecast_capacity(
                facility_id="fac-001",
                dimension=dim,
                unit="unit",
                scenario="baseline",
                data_points=points,
            )
            self.assertEqual(result.dimension, dim)

    def test_forecast_from_snapshots_dict(self):
        """forecast_from_snapshots should parse raw dicts."""
        snapshots = [
            {
                "observed_at": "2026-01-01T00:00:00+00:00",
                "usable": 100.0,
                "reserved": 60.0,
                "policy_reserve": 10.0,
                "forecast_peak": 80.0,
                "quality_status": "good",
                "scenario": "baseline",
            },
            {
                "observed_at": "2026-01-02T00:00:00+00:00",
                "usable": 110.0,
                "reserved": 66.0,
                "policy_reserve": 11.0,
                "forecast_peak": 88.0,
                "quality_status": "good",
                "scenario": "baseline",
            },
            {
                "observed_at": "2026-01-03T00:00:00+00:00",
                "usable": 120.0,
                "reserved": 72.0,
                "policy_reserve": 12.0,
                "forecast_peak": 96.0,
                "quality_status": "good",
                "scenario": "baseline",
            },
        ]
        result = forecast_from_snapshots(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            snapshots=snapshots,
            horizon_days=7,
        )
        self.assertEqual(result.facility_id, "fac-001")
        self.assertEqual(len(result.forecast_points), 7)

    def test_forecast_from_snapshots_skips_invalid(self):
        """forecast_from_snapshots should skip malformed entries."""
        snapshots = [
            {
                "observed_at": "2026-01-01T00:00:00+00:00",
                "usable": 100.0,
                "reserved": 60.0,
                "policy_reserve": 10.0,
                "forecast_peak": 80.0,
                "quality_status": "good",
                "scenario": "baseline",
            },
            {"invalid": "data"},
            {
                "observed_at": "2026-01-03T00:00:00+00:00",
                "usable": 120.0,
                "reserved": 72.0,
                "policy_reserve": 12.0,
                "forecast_peak": 96.0,
                "quality_status": "good",
                "scenario": "baseline",
            },
        ]
        result = forecast_from_snapshots(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            snapshots=snapshots,
            horizon_days=7,
            method="moving_average",
        )
        self.assertEqual(result.data_points_used, 2)

    def test_select_best_method_with_clear_trend(self):
        """Should select linear when there's a clear trend."""
        points = _make_points([100, 110, 120, 130, 140, 150, 160, 170, 180, 190])
        method = select_best_method(points)
        self.assertEqual(method, "linear")

    def test_select_best_method_with_noisy_data(self):
        """Should select moving average for noisy data."""
        points = _make_points([100, 80, 120, 90, 110, 85, 115, 95, 105, 88])
        method = select_best_method(points)
        self.assertIn(method, ("moving_average", "exponential_smoothing"))

    def test_select_best_method_with_few_points(self):
        """Should select moving average with minimal data."""
        points = _make_points([100, 110])
        method = select_best_method(points)
        self.assertEqual(method, "moving_average")

    def test_compute_capacity_at_risk(self):
        """Should identify dates where forecast exceeds threshold."""
        points = _make_points([100, 110, 120, 130, 140, 150, 160])
        forecast = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=30,
            method="linear",
        )
        result = compute_capacity_at_risk(forecast, threshold=180.0)
        self.assertIn("at_risk_dates", result)
        self.assertIn("severity", result)
        self.assertIn(result["severity"], ("none", "low", "medium", "high"))
        self.assertTrue(result["execution_permitted"] is False)

    def test_compute_capacity_at_risk_no_breach(self):
        """Should return severity=none when threshold is never exceeded."""
        points = _make_points([100, 105, 110, 115, 120])
        forecast = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
            method="linear",
        )
        result = compute_capacity_at_risk(forecast, threshold=9999.0)
        self.assertEqual(result["severity"], "none")
        self.assertEqual(result["at_risk_count"], 0)

    def test_forecast_to_dict_serialization(self):
        """Forecast should serialize to a clean dict."""
        points = _make_points([100, 110, 120, 130, 140])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
        )
        d = result.to_dict()
        self.assertIn("facility_id", d)
        self.assertIn("dimension", d)
        self.assertIn("forecast_points", d)
        self.assertIn("quality_status", d)
        self.assertIn("provenance", d)
        self.assertIn("execution_permitted", d)
        self.assertFalse(d["execution_permitted"])
        self.assertEqual(len(d["forecast_points"]), 7)

    def test_forecast_with_stale_data_gets_flagged(self):
        """Stale data should be flagged in quality assessment."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        points = _make_points([100, 110, 120], start_date=old_date)
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
        )
        # Should have stale data reason code
        self.assertTrue(
            any("stale" in code for code in result.reason_codes),
            f"Expected stale data flag, got: {result.reason_codes}",
        )

    def test_forecast_with_synthetic_data_marks_provenance(self):
        """Synthetic data should be marked in provenance."""
        points = _make_points([100, 110, 120], quality="estimated")
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
        )
        self.assertTrue(result.provenance.get("synthetic"))

    def test_forecast_provenance_includes_label(self):
        """Provenance should include advisory label."""
        points = _make_points([100, 110, 120])
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=7,
        )
        self.assertIn("ADVISORY", result.provenance.get("label", ""))

    def test_data_point_utilization(self):
        """CapacityDataPoint utilization should compute correctly."""
        point = CapacityDataPoint(
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usable=100.0,
            reserved=60.0,
            policy_reserve=10.0,
            forecast_peak=80.0,
            quality_status="good",
            scenario="test",
        )
        self.assertEqual(point.committed, 70.0)
        self.assertEqual(point.headroom, 30.0)
        self.assertAlmostEqual(point.utilization, 0.7)

    def test_data_point_zero_usable(self):
        """Zero usable capacity should not cause division errors."""
        point = CapacityDataPoint(
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usable=0.0,
            reserved=0.0,
            policy_reserve=0.0,
            forecast_peak=0.0,
            quality_status="good",
            scenario="test",
        )
        self.assertEqual(point.utilization, 0.0)

    def test_forecast_sorts_unsorted_input(self):
        """Forecast should handle unsorted data points."""
        points = _make_points([100, 110, 120, 130, 140])
        # Reverse the list
        reversed_points = list(reversed(points))
        result = forecast_capacity(
            facility_id="fac-001",
            dimension="power_kw",
            unit="kW",
            scenario="baseline",
            data_points=reversed_points,
            horizon_days=7,
        )
        # Should still produce valid forecast
        self.assertEqual(len(result.forecast_points), 7)
        self.assertGreater(result.forecast_points[-1].predicted_value, 140)


if __name__ == "__main__":
    unittest.main()
