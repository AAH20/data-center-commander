"""Unit tests for dcc.forecasting.load module."""
import unittest
from datetime import datetime, timezone

from dcc.forecasting.load import (
    LoadObservation,
    ForecastPoint,
    ForecastResult,
    MovingAverageForecaster,
    ExponentialSmoothingForecaster,
    HoltWintersForecaster,
    LinearTrendForecaster,
    aggregate_to_hourly,
    aggregate_to_daily,
    compute_metrics,
    detect_anomalies,
    select_best_model,
)


class TestLoadObservation(unittest.TestCase):
    def test_creation(self):
        obs = LoadObservation(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            value=100.0,
        )
        self.assertEqual(obs.value, 100.0)
        self.assertEqual(obs.unit, "kW")

    def test_with_quality(self):
        obs = LoadObservation(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            value=100.0,
            quality="estimated",
        )
        self.assertEqual(obs.quality, "estimated")


class TestForecastPoint(unittest.TestCase):
    def test_creation(self):
        fp = ForecastPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            predicted=100.0,
        )
        self.assertEqual(fp.predicted, 100.0)
        self.assertIsNone(fp.lower_bound)

    def test_with_bounds(self):
        fp = ForecastPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            predicted=100.0,
            lower_bound=90.0,
            upper_bound=110.0,
        )
        self.assertEqual(fp.lower_bound, 90.0)


class TestForecastResult(unittest.TestCase):
    def test_creation(self):
        fp = ForecastPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            predicted=100.0,
        )
        r = ForecastResult(
            model_name="test",
            points=[fp],
        )
        self.assertEqual(r.model_name, "test")
        self.assertEqual(len(r.points), 1)


class TestAggregateToHourly(unittest.TestCase):
    def test_aggregate(self):
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), value=100.0),
            LoadObservation(timestamp=datetime(2024, 1, 1, 0, 30, tzinfo=timezone.utc), value=200.0),
        ]
        result = aggregate_to_hourly(obs)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].value, 150.0)

    def test_empty(self):
        result = aggregate_to_hourly([])
        self.assertEqual(result, [])


class TestAggregateToDaily(unittest.TestCase):
    def test_aggregate(self):
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), value=100.0),
            LoadObservation(timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc), value=200.0),
        ]
        result = aggregate_to_daily(obs)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].value, 150.0)


class TestComputeMetrics(unittest.TestCase):
    def test_perfect(self):
        result = compute_metrics([100.0, 200.0], [100.0, 200.0])
        self.assertEqual(result["mae"], 0.0)
        self.assertEqual(result["rmse"], 0.0)

    def test_basic(self):
        result = compute_metrics([100.0], [110.0])
        self.assertAlmostEqual(result["mae"], 10.0)
        self.assertAlmostEqual(result["rmse"], 10.0)


class TestDetectAnomalies(unittest.TestCase):
    def test_detect(self):
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i))
            for i in range(10)
        ]
        obs.append(LoadObservation(timestamp=datetime(2024, 1, 1, 10, tzinfo=timezone.utc), value=100.0))
        result = detect_anomalies(obs)
        self.assertIsInstance(result, list)

    def test_insufficient_data(self):
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), value=100.0),
        ]
        result = detect_anomalies(obs)
        self.assertEqual(result, [])


class TestMovingAverageForecaster(unittest.TestCase):
    def test_forecast(self):
        f = MovingAverageForecaster(window=3)
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i))
            for i in range(1, 11)
        ]
        result = f.forecast(obs, horizon=3)
        self.assertIsInstance(result, ForecastResult)
        self.assertEqual(len(result.points), 3)


class TestExponentialSmoothingForecaster(unittest.TestCase):
    def test_forecast(self):
        f = ExponentialSmoothingForecaster(alpha=0.3)
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i))
            for i in range(1, 11)
        ]
        result = f.forecast(obs, horizon=3)
        self.assertIsInstance(result, ForecastResult)
        self.assertEqual(len(result.points), 3)


class TestHoltWintersForecaster(unittest.TestCase):
    def test_forecast(self):
        f = HoltWintersForecaster(season_length=3)
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i % 3 + 1))
            for i in range(1, 13)
        ]
        result = f.forecast(obs, horizon=3)
        self.assertIsInstance(result, ForecastResult)


class TestLinearTrendForecaster(unittest.TestCase):
    def test_forecast(self):
        f = LinearTrendForecaster()
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i))
            for i in range(1, 11)
        ]
        result = f.forecast(obs, horizon=3)
        self.assertIsInstance(result, ForecastResult)
        self.assertEqual(len(result.points), 3)


class TestSelectBestModel(unittest.TestCase):
    def test_select(self):
        obs = [
            LoadObservation(timestamp=datetime(2024, 1, 1, i, tzinfo=timezone.utc), value=float(i))
            for i in range(1, 11)
        ]
        result = select_best_model(obs, horizon=3)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
