"""Unit tests for dcc.forecasting.backtest module."""
import unittest
import math

from dcc.forecasting.backtest import (
    ForecastPoint,
    BacktestResult,
    WalkForwardResult,
    CrossValidationResult,
    mae,
    rmse,
    mape,
    smape,
    mase,
    bias,
    variance_ratio,
    evaluate_forecast,
    walk_forward,
    cross_validate,
    naive_forecast,
    seasonal_naive_forecast,
    moving_average_forecast,
    drift_forecast,
)


class TestForecastPoint(unittest.TestCase):
    def test_creation(self):
        fp = ForecastPoint(timestamp=100.0, value=50.0)
        self.assertEqual(fp.timestamp, 100.0)
        self.assertEqual(fp.value, 50.0)
        self.assertIsNone(fp.lower)
        self.assertIsNone(fp.upper)

    def test_with_interval(self):
        fp = ForecastPoint(timestamp=100.0, value=50.0, lower=40.0, upper=60.0)
        self.assertEqual(fp.lower, 40.0)
        self.assertEqual(fp.upper, 60.0)


class TestBacktestResult(unittest.TestCase):
    def test_creation(self):
        br = BacktestResult(
            fold_index=0,
            train_start=0,
            train_end=10,
            test_start=10,
            test_end=15,
            predictions=[1.0, 2.0],
            actuals=[1.1, 2.1],
        )
        self.assertEqual(br.fold_index, 0)
        self.assertEqual(len(br.predictions), 2)

    def test_invalid_train_range(self):
        with self.assertRaises(ValueError):
            BacktestResult(
                fold_index=0,
                train_start=10,
                train_end=10,
                test_start=10,
                test_end=15,
                predictions=[],
                actuals=[],
            )

    def test_invalid_test_range(self):
        with self.assertRaises(ValueError):
            BacktestResult(
                fold_index=0,
                train_start=0,
                train_end=10,
                test_start=15,
                test_end=15,
                predictions=[],
                actuals=[],
            )


class TestWalkForwardResult(unittest.TestCase):
    def test_creation(self):
        br = BacktestResult(
            fold_index=0,
            train_start=0,
            train_end=10,
            test_start=10,
            test_end=15,
            predictions=[1.0],
            actuals=[1.0],
        )
        wfr = WalkForwardResult(
            folds=[br],
            min_train_size=10,
            step_size=5,
            horizon=5,
        )
        self.assertEqual(len(wfr.folds), 1)
        self.assertEqual(wfr.min_train_size, 10)


class TestCrossValidationResult(unittest.TestCase):
    def test_creation(self):
        br = BacktestResult(
            fold_index=0,
            train_start=0,
            train_end=10,
            test_start=10,
            test_end=15,
            predictions=[1.0],
            actuals=[1.0],
        )
        cvr = CrossValidationResult(
            folds=[br],
            n_splits=5,
            gap=0,
        )
        self.assertEqual(len(cvr.folds), 1)
        self.assertEqual(cvr.n_splits, 5)


class TestMae(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(mae([1.0, 2.0], [1.0, 2.0]), 0.0)

    def test_basic(self):
        self.assertEqual(mae([1.0, 2.0], [2.0, 3.0]), 1.0)

    def test_empty(self):
        self.assertEqual(mae([], []), 0.0)

    def test_mismatched_length(self):
        with self.assertRaises(ValueError):
            mae([1.0], [1.0, 2.0])


class TestRmse(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(rmse([1.0, 2.0], [1.0, 2.0]), 0.0)

    def test_basic(self):
        self.assertAlmostEqual(rmse([1.0, 2.0], [2.0, 3.0]), 1.0)

    def test_empty(self):
        self.assertEqual(rmse([], []), 0.0)


class TestMape(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(mape([100.0, 200.0], [100.0, 200.0]), 0.0)

    def test_basic(self):
        self.assertAlmostEqual(mape([100.0], [110.0]), 10.0)

    def test_skips_zero(self):
        self.assertEqual(mape([0.0], [100.0]), 0.0)

    def test_empty(self):
        self.assertEqual(mape([], []), 0.0)


class TestSmape(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(smape([100.0, 200.0], [100.0, 200.0]), 0.0)

    def test_basic(self):
        result = smape([100.0], [110.0])
        self.assertGreater(result, 0)

    def test_empty(self):
        self.assertEqual(smape([], []), 0.0)


class TestMase(unittest.TestCase):
    def test_basic(self):
        result = mase([1.0, 2.0], [1.1, 2.1], [1.0, 2.0, 3.0, 4.0])
        self.assertGreater(result, 0)

    def test_empty(self):
        self.assertEqual(mase([], [], [1.0, 2.0, 3.0]), 0.0)

    def test_insufficient_training(self):
        with self.assertRaises(ValueError):
            mase([1.0], [1.0], [1.0], seasonality=1)


class TestBias(unittest.TestCase):
    def test_no_bias(self):
        self.assertEqual(bias([1.0, 2.0], [1.0, 2.0]), 0.0)

    def test_positive_bias(self):
        self.assertAlmostEqual(bias([2.0, 3.0], [1.0, 2.0]), 1.0)


class TestVarianceRatio(unittest.TestCase):
    def test_basic(self):
        result = variance_ratio([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
        self.assertGreater(result, 0)


class TestEvaluateForecast(unittest.TestCase):
    def test_evaluate(self):
        result = evaluate_forecast([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
        self.assertIsInstance(result, dict)
        self.assertIn("mae", result)
        self.assertIn("rmse", result)


class TestWalkForward(unittest.TestCase):
    def test_walk_forward(self):
        values = [float(i) for i in range(20)]
        result = walk_forward(values, min_train_size=10, step_size=5, horizon=3)
        self.assertIsInstance(result, WalkForwardResult)
        self.assertGreater(len(result.folds), 0)


class TestCrossValidate(unittest.TestCase):
    def test_cross_validate(self):
        values = [float(i) for i in range(20)]
        result = cross_validate(values, n_splits=3)
        self.assertIsInstance(result, CrossValidationResult)
        self.assertEqual(len(result.folds), 3)


class TestNaiveForecast(unittest.TestCase):
    def test_naive(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = naive_forecast(values, horizon=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1], 5.0)


class TestSeasonalNaiveForecast(unittest.TestCase):
    def test_seasonal_naive(self):
        values = [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
        result = seasonal_naive_forecast(values, seasonality=3, horizon=3)
        self.assertEqual(len(result), 3)


class TestMovingAverageForecast(unittest.TestCase):
    def test_moving_average(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = moving_average_forecast(values, window=3, horizon=3)
        self.assertEqual(len(result), 3)


class TestDriftForecast(unittest.TestCase):
    def test_drift(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = drift_forecast(values, horizon=3)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
