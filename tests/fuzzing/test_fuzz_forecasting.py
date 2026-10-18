"""Fuzz tests for forecasting modules using Hypothesis."""
from __future__ import annotations

import datetime as dt
import math

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.forecasting.capacity import (
    CapacityDataPoint,
    forecast_capacity,
    forecast_from_snapshots,
    select_best_method,
    compute_capacity_at_risk,
    FORECASTABLE_DIMENSIONS,
)

from dcc.forecasting.load import (
    LoadObservation,
    MovingAverageForecaster,
    ExponentialSmoothingForecaster,
    HoltWintersForecaster,
    LinearTrendForecaster,
    compute_metrics,
    detect_anomalies,
    aggregate_to_hourly,
    aggregate_to_daily,
)

from dcc.forecasting.backtest import (
    naive_forecast,
    seasonal_naive_forecast,
    moving_average_forecast,
    drift_forecast,
    walk_forward,
    cross_validate,
    evaluate_forecast,
)

from dcc.forecasting.calibration import (
    ForecastPoint,
    ActualPoint,
    CalibrationMethod,
    calibrate_forecasts,
    match_forecast_actual_pairs,
    compute_calibration_metrics,
)


# Strategies
float_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)

positive_floats = st.floats(min_value=0.001, max_value=1e6, allow_nan=False, allow_infinity=False)

timestamps = st.datetimes(
    min_value=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
    max_value=dt.datetime(2030, 12, 31, tzinfo=dt.timezone.utc),
)

dimensions = st.sampled_from(sorted(FORECASTABLE_DIMENSIONS))

forecast_methods = st.sampled_from(["linear", "moving_average", "exponential_smoothing"])


def make_capacity_points(n):
    """Generate n capacity data points."""
    base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    return [
        CapacityDataPoint(
            observed_at=base + dt.timedelta(days=i),
            usable=100.0 + i * 2,
            reserved=50.0,
            policy_reserve=10.0,
            forecast_peak=None,
            quality_status="good",
            scenario="baseline",
        )
        for i in range(n)
    ]


def make_load_observations(n):
    """Generate n load observations."""
    base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    return [
        LoadObservation(
            timestamp=base + dt.timedelta(hours=i),
            value=100.0 + i * 0.5,
            unit="kW",
            quality="good",
        )
        for i in range(n)
    ]


class TestCapacityForecastFuzz:
    """Fuzz capacity forecasting."""

    @given(
        n_points=st.integers(min_value=3, max_value=50),
        dimension=dimensions,
        horizon=st.integers(min_value=1, max_value=365),
        method=forecast_methods,
    )
    @settings(max_examples=100)
    def test_forecast_capacity_never_crashes(self, n_points, dimension, horizon, method):
        """forecast_capacity should handle any valid inputs."""
        points = make_capacity_points(n_points)
        result = forecast_capacity(
            facility_id="test-facility",
            dimension=dimension,
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=horizon,
            method=method,
        )
        assert result.dimension == dimension
        assert result.forecast_horizon_days == horizon
        assert len(result.forecast_points) == horizon

    @given(
        n_points=st.integers(min_value=3, max_value=50),
        dimension=dimensions,
        horizon=st.integers(min_value=1, max_value=365),
    )
    @settings(max_examples=100)
    def test_forecast_from_snapshots(self, n_points, dimension, horizon):
        """forecast_from_snapshots should handle any valid snapshots."""
        base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
        snapshots = [
            {
                "observed_at": (base + dt.timedelta(days=i)).isoformat(),
                "usable": 100.0 + i * 2,
                "reserved": 50.0,
                "policy_reserve": 10.0,
                "forecast_peak": None,
                "quality_status": "good",
                "scenario": "baseline",
            }
            for i in range(n_points)
        ]
        result = forecast_from_snapshots(
            facility_id="test-facility",
            dimension=dimension,
            unit="kW",
            scenario="baseline",
            snapshots=snapshots,
            horizon_days=horizon,
        )
        assert result.dimension == dimension
        assert len(result.forecast_points) == horizon

    @given(
        n_points=st.integers(min_value=3, max_value=50),
    )
    @settings(max_examples=100)
    def test_select_best_method(self, n_points):
        """select_best_method should return a valid method."""
        points = make_capacity_points(n_points)
        method = select_best_method(points)
        assert method in ("linear", "moving_average", "exponential_smoothing")

    @given(
        n_points=st.integers(min_value=3, max_value=50),
        dimension=dimensions,
        threshold=positive_floats,
    )
    @settings(max_examples=100)
    def test_compute_capacity_at_risk(self, n_points, dimension, threshold):
        """compute_capacity_at_risk should handle any valid inputs."""
        points = make_capacity_points(n_points)
        result = forecast_capacity(
            facility_id="test-facility",
            dimension=dimension,
            unit="kW",
            scenario="baseline",
            data_points=points,
            horizon_days=30,
        )
        risk = compute_capacity_at_risk(result, threshold)
        assert risk["threshold"] == threshold
        assert risk["at_risk_count"] >= 0


class TestLoadForecastFuzz:
    """Fuzz load forecasting."""

    @given(
        n_points=st.integers(min_value=5, max_value=100),
        horizon=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_moving_average_forecaster(self, n_points, horizon):
        """MovingAverageForecaster should handle any valid inputs."""
        obs = make_load_observations(n_points)
        forecaster = MovingAverageForecaster(window=min(24, n_points))
        result = forecaster.forecast(obs, horizon)
        assert len(result.points) == horizon
        assert result.training_points == n_points

    @given(
        n_points=st.integers(min_value=5, max_value=100),
        horizon=st.integers(min_value=1, max_value=50),
        alpha=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_exponential_smoothing_forecaster(self, n_points, horizon, alpha):
        """ExponentialSmoothingForecaster should handle any valid inputs."""
        obs = make_load_observations(n_points)
        forecaster = ExponentialSmoothingForecaster(alpha=alpha)
        result = forecaster.forecast(obs, horizon)
        assert len(result.points) == horizon

    @given(
        n_points=st.integers(min_value=5, max_value=100),
        horizon=st.integers(min_value=1, max_value=50),
        alpha=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
        beta=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_holt_winters_forecaster(self, n_points, horizon, alpha, beta):
        """HoltWintersForecaster should handle any valid inputs."""
        obs = make_load_observations(n_points)
        forecaster = HoltWintersForecaster(alpha=alpha, beta=beta)
        result = forecaster.forecast(obs, horizon)
        assert len(result.points) == horizon

    @given(
        n_points=st.integers(min_value=5, max_value=100),
        horizon=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_linear_trend_forecaster(self, n_points, horizon):
        """LinearTrendForecaster should handle any valid inputs."""
        obs = make_load_observations(n_points)
        forecaster = LinearTrendForecaster()
        result = forecaster.forecast(obs, horizon)
        assert len(result.points) == horizon

    @given(
        n_points=st.integers(min_value=3, max_value=100),
    )
    @settings(max_examples=100)
    def test_compute_metrics(self, n_points):
        """compute_metrics should handle any valid inputs."""
        actual = [float(i) for i in range(n_points)]
        predicted = [float(i + 1) for i in range(n_points)]
        metrics = compute_metrics(actual, predicted)
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics
        assert "r2" in metrics

    @given(
        n_points=st.integers(min_value=3, max_value=100),
        threshold=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_detect_anomalies(self, n_points, threshold):
        """detect_anomalies should handle any valid inputs."""
        obs = make_load_observations(n_points)
        anomalies = detect_anomalies(obs, threshold_std=threshold)
        assert isinstance(anomalies, list)

    @given(
        n_points=st.integers(min_value=5, max_value=100),
    )
    @settings(max_examples=100)
    def test_aggregate_to_hourly(self, n_points):
        """aggregate_to_hourly should handle any valid observations."""
        base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
        obs = [
            LoadObservation(
                timestamp=base + dt.timedelta(minutes=15 * i),
                value=100.0 + i,
                unit="kW",
            )
            for i in range(n_points)
        ]
        result = aggregate_to_hourly(obs)
        assert len(result) > 0
        assert len(result) <= n_points


class TestBacktestFuzz:
    """Fuzz backtesting functions."""

    @given(
        data=st.lists(float_values, min_size=10, max_size=100),
        horizon=st.integers(min_value=1, max_value=5),
        min_train=st.integers(min_value=2, max_value=20),
    )
    @settings(max_examples=100)
    def test_walk_forward(self, data, horizon, min_train):
        """walk_forward should handle any valid inputs."""
        assume(min_train + horizon <= len(data))
        def model(train):
            return naive_forecast(train, horizon)
        result = walk_forward(data, model, min_train_size=min_train, horizon=horizon)
        assert len(result.folds) > 0
        assert result.horizon == horizon

    @given(
        data=st.lists(float_values, min_size=10, max_size=100),
        n_splits=st.integers(min_value=2, max_value=5),
        horizon=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_cross_validate(self, data, n_splits, horizon):
        """cross_validate should handle any valid inputs."""
        try:
            def model(train):
                return naive_forecast(train, horizon)
            result = cross_validate(data, model, n_splits=n_splits, horizon=horizon)
            assert result.n_splits >= 2
        except ValueError:
            pass  # Expected for insufficient data

    @given(
        actual=st.lists(float_values, min_size=1, max_size=50),
        predicted=st.lists(float_values, min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_evaluate_forecast(self, actual, predicted):
        """evaluate_forecast should handle any valid inputs."""
        assume(len(actual) == len(predicted))
        metrics = evaluate_forecast(actual, predicted)
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics
        assert "smape" in metrics
        assert "bias" in metrics

    @given(
        data=st.lists(float_values, min_size=5, max_size=50),
        horizon=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_naive_forecast(self, data, horizon):
        """naive_forecast should handle any valid inputs."""
        result = naive_forecast(data, horizon)
        assert len(result) == horizon
        assert all(r == data[-1] for r in result)

    @given(
        data=st.lists(float_values, min_size=5, max_size=50),
        seasonality=st.integers(min_value=1, max_value=10),
        horizon=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_seasonal_naive_forecast(self, data, seasonality, horizon):
        """seasonal_naive_forecast should handle any valid inputs."""
        assume(len(data) >= seasonality)
        result = seasonal_naive_forecast(data, seasonality, horizon)
        assert len(result) == horizon

    @given(
        data=st.lists(float_values, min_size=5, max_size=50),
        window=st.integers(min_value=1, max_value=10),
        horizon=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_moving_average_forecast(self, data, window, horizon):
        """moving_average_forecast should handle any valid inputs."""
        assume(window <= len(data))
        result = moving_average_forecast(data, window, horizon)
        assert len(result) == horizon

    @given(
        data=st.lists(float_values, min_size=5, max_size=50),
        horizon=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_drift_forecast(self, data, horizon):
        """drift_forecast should handle any valid inputs."""
        result = drift_forecast(data, horizon)
        assert len(result) == horizon


class TestCalibrationFuzz:
    """Fuzz calibration functions."""

    @given(
        n_forecasts=st.integers(min_value=1, max_value=50),
        n_actuals=st.integers(min_value=1, max_value=50),
        method=st.sampled_from(list(CalibrationMethod)),
    )
    @settings(max_examples=100)
    def test_calibrate_forecasts(self, n_forecasts, n_actuals, method):
        """calibrate_forecasts should handle any valid inputs."""
        forecasts = [
            ForecastPoint(timestamp=float(i), value=100.0 + i)
            for i in range(n_forecasts)
        ]
        actuals = [
            ActualPoint(timestamp=float(i), value=100.0 + i + 1)
            for i in range(n_actuals)
        ]
        result = calibrate_forecasts(forecasts, actuals, method=method)
        assert result.method == method
        assert result.sample_size >= 0

    @given(
        n_forecasts=st.integers(min_value=1, max_value=50),
        n_actuals=st.integers(min_value=1, max_value=50),
        tolerance=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_match_forecast_actual_pairs(self, n_forecasts, n_actuals, tolerance):
        """match_forecast_actual_pairs should handle any valid inputs."""
        forecasts = [
            ForecastPoint(timestamp=float(i), value=100.0 + i)
            for i in range(n_forecasts)
        ]
        actuals = [
            ActualPoint(timestamp=float(i), value=100.0 + i)
            for i in range(n_actuals)
        ]
        pairs = match_forecast_actual_pairs(forecasts, actuals, tolerance=tolerance)
        assert isinstance(pairs, list)

    @given(
        n_pairs=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_compute_calibration_metrics(self, n_pairs):
        """compute_calibration_metrics should handle any valid pairs."""
        pairs = [
            ForecastPoint(timestamp=float(i), value=100.0 + i)
            for i in range(n_pairs)
        ]
        # Create matched pairs for testing
        from dcc.forecasting.calibration import MatchedPair
        matched = [
            MatchedPair(timestamp=float(i), forecast=100.0 + i, actual=100.0 + i + 1, error=1.0)
            for i in range(n_pairs)
        ]
        metrics = compute_calibration_metrics(matched)
        assert "bias" in metrics
        assert "mae" in metrics
        assert "rmse" in metrics
