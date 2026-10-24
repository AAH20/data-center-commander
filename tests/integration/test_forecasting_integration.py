"""Integration tests for forecasting modules.

Tests backtesting, calibration, capacity forecasting, drift detection,
failure prediction, features, load forecasting, maintenance, and price forecasting.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal


class TestBacktestIntegration(unittest.TestCase):
    """Integration tests for backtesting."""

    def test_mae_calculation(self):
        from dcc.forecasting.backtest import mae
        result = mae([1, 2, 3], [1, 2, 3])
        self.assertEqual(result, 0.0)

    def test_mae_with_errors(self):
        from dcc.forecasting.backtest import mae
        result = mae([1, 2, 3], [2, 3, 4])
        self.assertEqual(result, 1.0)

    def test_mae_rejects_mismatched_lengths(self):
        from dcc.forecasting.backtest import mae
        with self.assertRaises(ValueError):
            mae([1, 2], [1])

    def test_rmse_calculation(self):
        from dcc.forecasting.backtest import rmse
        result = rmse([1, 2, 3], [1, 2, 3])
        self.assertEqual(result, 0.0)

    def test_rmse_with_errors(self):
        from dcc.forecasting.backtest import rmse
        result = rmse([1, 2, 3], [2, 3, 4])
        self.assertAlmostEqual(result, 1.0)

    def test_mape_calculation(self):
        from dcc.forecasting.backtest import mape
        result = mape([100, 200], [110, 190])
        # mean of |10/100| and |10/200| == 7.5%
        self.assertAlmostEqual(result, 7.5)

    def test_mape_skips_zero_actuals(self):
        from dcc.forecasting.backtest import mape
        result = mape([0, 100], [50, 110])
        self.assertAlmostEqual(result, 10.0)

    def test_walk_forward(self):
        from dcc.forecasting.backtest import walk_forward

        def naive(history):
            return [history[-1]]

        result = walk_forward(
            data=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            model=naive,
            min_train_size=3,
            step_size=1,
            horizon=1,
        )
        self.assertIsNotNone(result)

    def test_cross_validate(self):
        from dcc.forecasting.backtest import cross_validate

        def naive(history):
            return [history[-1]]

        result = cross_validate(
            data=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            model=naive,
            n_splits=3,
        )
        self.assertIsNotNone(result)

    def test_evaluate_forecast(self):
        from dcc.forecasting.backtest import evaluate_forecast
        result = evaluate_forecast(
            actual=[1, 2, 3, 4, 5],
            predicted=[1.1, 2.1, 2.9, 4.1, 4.9],
        )
        self.assertIsNotNone(result)


class TestCalibrationIntegration(unittest.TestCase):
    """Integration tests for forecast calibration."""

    def test_match_forecast_actual_pairs(self):
        from dcc.forecasting.calibration import match_forecast_actual_pairs, ForecastPoint, ActualPoint
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=11.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].error, -1.0)

    def test_match_with_tolerance(self):
        from dcc.forecasting.calibration import match_forecast_actual_pairs, ForecastPoint, ActualPoint
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.5, value=11.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals, tolerance=1.0)
        self.assertEqual(len(pairs), 1)

    def test_match_rejects_negative_tolerance(self):
        from dcc.forecasting.calibration import match_forecast_actual_pairs, ForecastPoint, ActualPoint
        with self.assertRaises(ValueError):
            match_forecast_actual_pairs([], [], tolerance=-1.0)

    def test_calibrate_forecasts_bias(self):
        from dcc.forecasting.calibration import calibrate_forecasts, ForecastPoint, ActualPoint, CalibrationMethod
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=12.0)]
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.BIAS)
        self.assertIsNotNone(result)

    def test_calibrate_forecasts_multiplicative(self):
        from dcc.forecasting.calibration import calibrate_forecasts, ForecastPoint, ActualPoint, CalibrationMethod
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=12.0)]
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.MULTIPLICATIVE)
        self.assertIsNotNone(result)

    def test_apply_bias_correction(self):
        from dcc.forecasting.calibration import apply_bias_correction, ForecastPoint
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        # bias is the mean error (forecast - actual) and is *subtracted*.
        result = apply_bias_correction(forecasts, bias=2.0)
        self.assertEqual(result[0].value, 8.0)

    def test_apply_multiplicative_correction(self):
        from dcc.forecasting.calibration import apply_multiplicative_correction, ForecastPoint
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        result = apply_multiplicative_correction(forecasts, scale_factor=1.2)
        self.assertEqual(result[0].value, 12.0)

    def test_compute_calibration_metrics(self):
        from dcc.forecasting.calibration import compute_calibration_metrics, MatchedPair
        pairs = [MatchedPair(timestamp=1.0, forecast=10.0, actual=12.0, error=-2.0)]
        metrics = compute_calibration_metrics(pairs)
        self.assertIsNotNone(metrics)


class TestCapacityForecastIntegration(unittest.TestCase):
    """Integration tests for capacity forecasting."""

    def test_forecast_capacity_linear(self):
        from dcc.forecasting.capacity import forecast_capacity, CapacityDataPoint
        points = [
            CapacityDataPoint(observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), usable=100, reserved=50, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
            CapacityDataPoint(observed_at=datetime(2026, 2, 1, tzinfo=timezone.utc), usable=110, reserved=55, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
            CapacityDataPoint(observed_at=datetime(2026, 3, 1, tzinfo=timezone.utc), usable=120, reserved=60, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
        ]
        result = forecast_capacity(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="current",
            data_points=points,
            horizon_days=30,
        )
        self.assertIsNotNone(result)

    def test_forecast_capacity_moving_average(self):
        from dcc.forecasting.capacity import forecast_capacity, CapacityDataPoint
        points = [
            CapacityDataPoint(observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), usable=100, reserved=50, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
            CapacityDataPoint(observed_at=datetime(2026, 2, 1, tzinfo=timezone.utc), usable=110, reserved=55, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
        ]
        result = forecast_capacity(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="current",
            data_points=points,
            horizon_days=30,
            method="moving_average",
        )
        self.assertIsNotNone(result)

    def test_forecast_capacity_exponential_smoothing(self):
        from dcc.forecasting.capacity import forecast_capacity, CapacityDataPoint
        points = [
            CapacityDataPoint(observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), usable=100, reserved=50, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
            CapacityDataPoint(observed_at=datetime(2026, 2, 1, tzinfo=timezone.utc), usable=110, reserved=55, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
            CapacityDataPoint(observed_at=datetime(2026, 3, 1, tzinfo=timezone.utc), usable=120, reserved=60, policy_reserve=10, forecast_peak=None, quality_status="good", scenario="current"),
        ]
        result = forecast_capacity(
            facility_id="f1",
            dimension="power_kw",
            unit="kW",
            scenario="current",
            data_points=points,
            horizon_days=30,
            method="exponential_smoothing",
        )
        self.assertIsNotNone(result)

    def test_capacity_data_point_properties(self):
        from dcc.forecasting.capacity import CapacityDataPoint
        point = CapacityDataPoint(
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usable=100, reserved=60, policy_reserve=10,
            forecast_peak=None, quality_status="good", scenario="current",
        )
        self.assertEqual(point.committed, 70)
        self.assertEqual(point.headroom, 30)
        self.assertAlmostEqual(point.utilization, 0.7)

    def test_capacity_data_point_zero_usable(self):
        from dcc.forecasting.capacity import CapacityDataPoint
        point = CapacityDataPoint(
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            usable=0, reserved=0, policy_reserve=0,
            forecast_peak=None, quality_status="good", scenario="current",
        )
        self.assertEqual(point.utilization, 0.0)


class TestDriftDetectionIntegration(unittest.TestCase):
    """Integration tests for drift detection."""

    def test_detect_drift_psi(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.PSI},
        )
        self.assertIsNotNone(result)

    def test_detect_drift_ks(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.KS},
        )
        self.assertIsNotNone(result)

    def test_detect_drift_cusum(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.CUSUM},
        )
        self.assertIsNotNone(result)

    def test_detect_drift_error_rate(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.ERROR_RATE},
        )
        self.assertIsNotNone(result)

    def test_detect_drift_mean_shift(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.MEAN_SHIFT},
        )
        self.assertIsNotNone(result)

    def test_detect_drift_variance_shift(self):
        from dcc.forecasting.drift import detect_drift, DriftMethod
        result = detect_drift(
            reference=[1, 2, 3, 4, 5] * 10,
            incoming=[1, 2, 3, 4, 5] * 10,
            methods={DriftMethod.VARIANCE_SHIFT},
        )
        self.assertIsNotNone(result)

    def test_compute_psi(self):
        from dcc.forecasting.drift import compute_psi
        result = compute_psi([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
        self.assertIsNotNone(result)

    def test_compute_ks_statistic(self):
        from dcc.forecasting.drift import compute_ks_statistic
        result = compute_ks_statistic([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
        self.assertIsNotNone(result)

    def test_drift_detector_class(self):
        from dcc.forecasting.drift import DriftDetector, DriftMethod
        detector = DriftDetector(methods={DriftMethod.PSI})
        self.assertIsNotNone(detector)

    def test_drift_result_to_dict(self):
        from dcc.forecasting.drift import DriftResult, DriftMethod, DriftSeverity
        from datetime import datetime, timezone
        result = DriftResult(
            method=DriftMethod.PSI,
            severity=DriftSeverity.NONE,
            score=0.05,
            threshold=0.10,
            detected=False,
        )
        d = result.to_dict()
        self.assertIn("method", d)
        self.assertIn("severity", d)

    def test_model_performance_snapshot(self):
        from dcc.forecasting.drift import ModelPerformanceSnapshot
        from datetime import datetime, timezone
        snapshot = ModelPerformanceSnapshot(
            model_id="m1",
            tenant_id="t1",
            window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            errors=[1.0, 2.0, 3.0],
        )
        snapshot.compute_derived()
        self.assertIsNotNone(snapshot.mae)

    def test_performance_tracker(self):
        from dcc.forecasting.drift import PerformanceTracker
        tracker = PerformanceTracker(model_id="m1", tenant_id="t1")
        self.assertIsNotNone(tracker)


class TestFailurePredictionIntegration(unittest.TestCase):
    """Integration tests for failure prediction."""

    def test_predict_equipment_failures(self):
        from dcc.forecasting.failure import predict_equipment_failures
        result = predict_equipment_failures(
            tenant_id="t1",
            assets=[
                {"asset_id": "a1", "name": "Server 1", "asset_type": "server", "criticality": "high", "lifecycle_state": "active"},
            ],
            telemetry_rows=[],
            window_days=30,
        )
        self.assertIsNotNone(result)

    def test_predict_with_telemetry(self):
        from dcc.forecasting.failure import predict_equipment_failures
        result = predict_equipment_failures(
            tenant_id="t1",
            assets=[
                {"asset_id": "a1", "name": "Server 1", "asset_type": "server", "criticality": "high", "lifecycle_state": "active"},
            ],
            telemetry_rows=[
                {"asset_id": "a1", "value_numeric": 80.0, "observed_at": "2026-01-01T00:00:00Z", "quality_status": "good", "metric_key": "temperature"},
            ],
            window_days=30,
        )
        self.assertIsNotNone(result)

    def test_result_to_dict(self):
        from dcc.forecasting.failure import predict_equipment_failures, result_to_dict
        result = predict_equipment_failures(
            tenant_id="t1",
            assets=[],
            telemetry_rows=[],
            window_days=30,
        )
        d = result_to_dict(result)
        self.assertIsNotNone(d)

    def test_asset_risk_profile(self):
        from dcc.forecasting.failure import AssetRiskProfile
        profile = AssetRiskProfile(
            asset_id="a1",
            asset_name="Server 1",
            asset_type="server",
            criticality="high",
            lifecycle_state="active",
            risk_score=0.5,
            risk_level="medium",
        )
        self.assertEqual(profile.risk_score, 0.5)


class TestFeaturesIntegration(unittest.TestCase):
    """Integration tests for feature extraction."""

    def test_rolling_stats(self):
        from dcc.forecasting.features import rolling_stats
        result = rolling_stats([1, 2, 3, 4, 5], window=3)
        self.assertIsNotNone(result)

    def test_lag_features(self):
        from dcc.forecasting.features import lag_features
        result = lag_features([1, 2, 3, 4, 5], lags=[1, 2])
        self.assertIsNotNone(result)

    def test_seasonal_decomposition(self):
        from dcc.forecasting.features import seasonal_decompose
        result = seasonal_decompose([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], period=3)
        self.assertIsNotNone(result)

    def test_trend_detection(self):
        from dcc.forecasting.features import detect_trend
        result = detect_trend([1, 2, 3, 4, 5])
        self.assertIsNotNone(result)

    def test_validate_series(self):
        from dcc.forecasting.features import _validate_series
        result = _validate_series([1, 2, 3])
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_validate_series_with_none(self):
        from dcc.forecasting.features import _validate_series
        result = _validate_series([1, None, 3])
        self.assertEqual(len(result), 3)


class TestLoadForecastingIntegration(unittest.TestCase):
    """Integration tests for load forecasting."""

    def test_aggregate_to_hourly(self):
        from dcc.forecasting.load import aggregate_to_hourly, LoadObservation
        obs = [
            LoadObservation(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=100),
            LoadObservation(timestamp=datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc), value=200),
        ]
        result = aggregate_to_hourly(obs)
        self.assertEqual(len(result), 1)

    def test_aggregate_to_daily(self):
        from dcc.forecasting.load import aggregate_to_daily, LoadObservation
        obs = [
            LoadObservation(timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), value=100),
            LoadObservation(timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), value=200),
        ]
        result = aggregate_to_daily(obs)
        self.assertEqual(len(result), 1)

    def test_compute_metrics(self):
        from dcc.forecasting.load import compute_metrics
        result = compute_metrics([1, 2, 3], [1, 2, 3])
        self.assertIsNotNone(result)

    def test_detect_anomalies(self):
        from dcc.forecasting.load import detect_anomalies, LoadObservation
        # detect_anomalies() takes LoadObservation objects, not bare numbers.
        observations = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=value,
            )
            for hour, value in enumerate([1, 2, 3, 100, 5])
        ]
        result = detect_anomalies(observations)
        self.assertIsNotNone(result)

    def test_select_best_model(self):
        from dcc.forecasting.load import select_best_model, LoadObservation
        history = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=float(value),
            )
            for hour, value in enumerate(range(1, 25))
        ]
        result = select_best_model(history)
        self.assertIsNotNone(result)

    def test_moving_average_forecaster(self):
        from dcc.forecasting.load import MovingAverageForecaster, LoadObservation
        history = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=float(value),
            )
            for hour, value in enumerate([1, 2, 3, 4, 5])
        ]
        forecaster = MovingAverageForecaster(window=3)
        result = forecaster.forecast(history, horizon=2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.points), 2)

    def test_exponential_smoothing_forecaster(self):
        from dcc.forecasting.load import ExponentialSmoothingForecaster, LoadObservation
        history = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=float(value),
            )
            for hour, value in enumerate([1, 2, 3, 4, 5])
        ]
        forecaster = ExponentialSmoothingForecaster(alpha=0.3)
        result = forecaster.forecast(history, horizon=2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.points), 2)

    def test_linear_trend_forecaster(self):
        from dcc.forecasting.load import LinearTrendForecaster, LoadObservation
        history = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=float(value),
            )
            for hour, value in enumerate([1, 2, 3, 4, 5])
        ]
        forecaster = LinearTrendForecaster()
        result = forecaster.forecast(history, horizon=2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.points), 2)

    def test_holt_winters_forecaster(self):
        from dcc.forecasting.load import HoltWintersForecaster, LoadObservation
        history = [
            LoadObservation(
                timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                value=float(value),
            )
            for hour, value in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9])
        ]
        # HoltWintersForecaster takes alpha/beta, not season_length.
        forecaster = HoltWintersForecaster(alpha=0.3, beta=0.1)
        result = forecaster.forecast(history, horizon=2)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.points), 2)


class TestMaintenanceIntegration(unittest.TestCase):
    """Integration tests for maintenance scheduling."""

    def test_compute_load_profile(self):
        from dcc.forecasting.maintenance import _compute_load_profile
        from dcc.forecasting.load import ForecastPoint
        points = [
            ForecastPoint(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), predicted=100),
            ForecastPoint(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), predicted=50),
        ]
        result = _compute_load_profile(points)
        self.assertEqual(result["peak_kw"], 100)
        self.assertEqual(result["min_kw"], 50)

    def test_compute_load_profile_empty(self):
        from dcc.forecasting.maintenance import _compute_load_profile
        result = _compute_load_profile([])
        self.assertEqual(result["peak_kw"], 0)

    def test_maintenance_constraint_defaults(self):
        from dcc.forecasting.maintenance import MaintenanceConstraint
        constraint = MaintenanceConstraint()
        self.assertEqual(constraint.min_notice_hours, 24.0)
        self.assertEqual(constraint.max_consecutive_hours, 8.0)

    def test_maintenance_window_creation(self):
        from dcc.forecasting.maintenance import MaintenanceWindow
        window = MaintenanceWindow(
            asset_id="a1",
            asset_name="Server 1",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            duration_hours=2.0,
            predicted_load_kw=50.0,
            load_pct_of_peak=0.5,
            risk_score=0.3,
            risk_level="low",
            confidence="high",
        )
        self.assertEqual(window.duration_hours, 2.0)

    def test_maintenance_schedule_creation(self):
        from dcc.forecasting.maintenance import MaintenanceSchedule
        from datetime import datetime, timezone
        schedule = MaintenanceSchedule(
            tenant_id="t1",
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            horizon_days=30,
        )
        self.assertEqual(schedule.horizon_days, 30)

    def test_recommend_maintenance_windows(self):
        from dcc.forecasting.maintenance import optimize_maintenance_windows
        from dcc.forecasting.load import ForecastPoint
        from dcc.forecasting.failure import AssetRiskProfile
        forecast_points = [
            ForecastPoint(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), predicted=100),
            ForecastPoint(timestamp=datetime(2026, 1, 1, 1, tzinfo=timezone.utc), predicted=50),
        ]
        risk_profiles = [
            AssetRiskProfile(
                asset_id="a1", asset_name="Server 1", asset_type="server",
                criticality="high", lifecycle_state="active",
                risk_score=0.5, risk_level="medium",
            ),
        ]
        # The scheduling entry point is optimize_maintenance_windows(); it takes
        # risk_profiles + forecast_points keyword-only and returns a schedule.
        result = optimize_maintenance_windows(
            tenant_id="t1",
            risk_profiles=risk_profiles,
            forecast_points=forecast_points,
            horizon_days=30,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(result)


class TestPriceForecastingIntegration(unittest.TestCase):
    """Integration tests for price forecasting."""

    def test_build_flat_tariff(self):
        from dcc.forecasting.price import build_flat_tariff
        spec = build_flat_tariff(currency="USD", timezone="UTC", rate=0.12)
        self.assertIsNotNone(spec)
        self.assertEqual(float(spec.energy_rates["flat"]), 0.12)

    def test_build_tou_tariff(self):
        from dcc.forecasting.price import build_tou_tariff
        spec = build_tou_tariff(
            currency="USD",
            timezone="UTC",
            rates={"peak": 0.25, "off_peak": 0.10},
        )
        self.assertIsNotNone(spec)
        self.assertEqual(set(spec.energy_rates), {"peak", "off_peak"})

    def test_build_tiered_tariff(self):
        from dcc.forecasting.price import build_tiered_tariff
        spec = build_tiered_tariff(
            currency="USD",
            timezone="UTC",
            tier_thresholds=[1000],
            tier_rates=[0.15, 0.10],
        )
        self.assertIsNotNone(spec)
        self.assertEqual([float(t) for t in spec.tier_thresholds], [1000.0])

    def test_forecast_prices(self):
        from dcc.forecasting.price import forecast_prices, build_flat_tariff
        spec = build_flat_tariff(currency="USD", timezone="UTC", rate=0.12)
        result = forecast_prices(
            spec,
            daily_kwh=1000,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            days=7,
        )
        self.assertIsNotNone(result)

    def test_validate_tariff_spec(self):
        from dcc.forecasting.price import validate_tariff_spec, build_flat_tariff, TariffSpec
        spec = build_flat_tariff(currency="USD", timezone="UTC", rate=0.12)
        # validate_tariff_spec() accepts the raw dict form and returns a TariffSpec.
        result = validate_tariff_spec(spec.to_dict())
        self.assertIsInstance(result, TariffSpec)

    def test_tariff_spec_to_dict(self):
        from dcc.forecasting.price import build_flat_tariff
        spec = build_flat_tariff(currency="USD", timezone="UTC", rate=0.12)
        d = spec.to_dict()
        self.assertIn("currency", d)

    def test_price_point_to_dict(self):
        from dcc.forecasting.price import PricePoint
        from decimal import Decimal
        point = PricePoint(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period="peak",
            energy_rate=Decimal("0.25"),
            demand_rate=None,
            estimated_cost=Decimal("250"),
            currency="USD",
        )
        d = point.to_dict()
        self.assertIn("period", d)


if __name__ == "__main__":
    unittest.main()
