"""Tests for time-series backtesting: walk-forward, cross-validation, error metrics."""
from __future__ import annotations

import math
import unittest

from dcc.forecasting.backtest import (
    BacktestResult,
    CrossValidationResult,
    WalkForwardResult,
    cross_validate,
    drift_forecast,
    evaluate_forecast,
    mae,
    mape,
    mase,
    moving_average_forecast,
    naive_forecast,
    rmse,
    seasonal_naive_forecast,
    smape,
    variance_ratio,
    bias,
    walk_forward,
)


class ErrorMetricsTests(unittest.TestCase):
    def test_mae_basic(self):
        self.assertAlmostEqual(mae([1, 2, 3], [1, 2, 3]), 0.0)
        self.assertAlmostEqual(mae([1, 2, 3], [2, 3, 4]), 1.0)
        self.assertAlmostEqual(mae([1, 2, 3], [0, 0, 0]), 2.0)

    def test_rmse_basic(self):
        self.assertAlmostEqual(rmse([1, 2, 3], [1, 2, 3]), 0.0)
        self.assertAlmostEqual(rmse([1, 2, 3], [2, 3, 4]), 1.0)
        self.assertAlmostEqual(rmse([0, 0], [3, 4]), math.sqrt(12.5))

    def test_mape_basic(self):
        self.assertAlmostEqual(mape([100, 200], [100, 200]), 0.0)
        self.assertAlmostEqual(mape([100, 200], [110, 180]), 10.0)
        # Zero actuals are skipped
        self.assertAlmostEqual(mape([0, 100], [5, 100]), 0.0)

    def test_smape_basic(self):
        self.assertAlmostEqual(smape([100, 200], [100, 200]), 0.0)
        self.assertAlmostEqual(smape([100], [110]), 2 * 10 / 210 * 100)

    def test_mase_basic(self):
        # Perfect forecast -> MASE = 0
        self.assertAlmostEqual(mase([1, 2, 3], [1, 2, 3], [1, 2, 3, 4, 5]), 0.0)
        # Naive forecast on training [1,2,3,4,5] has MAE=1.0
        # Test forecast [2,3,4] vs actual [3,4,5] has MAE=1.0 -> MASE=1.0
        self.assertAlmostEqual(mase([3, 4, 5], [2, 3, 4], [1, 2, 3, 4, 5]), 1.0)

    def test_bias(self):
        self.assertAlmostEqual(bias([1, 2, 3], [1, 2, 3]), 0.0)
        self.assertAlmostEqual(bias([1, 2, 3], [2, 3, 4]), 1.0)  # over-forecast
        self.assertAlmostEqual(bias([1, 2, 3], [0, 1, 2]), -1.0)  # under-forecast

    def test_variance_ratio(self):
        self.assertAlmostEqual(variance_ratio([1, 2, 3], [1, 2, 3]), 1.0)
        # Predictions have zero variance
        self.assertAlmostEqual(variance_ratio([1, 2, 3], [2, 2, 2]), 0.0)

    def test_evaluate_forecast_returns_all_metrics(self):
        metrics = evaluate_forecast([1, 2, 3], [1, 2, 3])
        self.assertIn("mae", metrics)
        self.assertIn("rmse", metrics)
        self.assertIn("mape", metrics)
        self.assertIn("smape", metrics)
        self.assertIn("bias", metrics)
        self.assertIn("variance_ratio", metrics)
        self.assertNotIn("mase", metrics)

    def test_evaluate_forecast_with_training_includes_mase(self):
        metrics = evaluate_forecast([1, 2, 3], [1, 2, 3], training_actual=[1, 2, 3, 4, 5])
        self.assertIn("mase", metrics)

    def test_empty_inputs_return_zero(self):
        self.assertEqual(mae([], []), 0.0)
        self.assertEqual(rmse([], []), 0.0)
        self.assertEqual(mape([], []), 0.0)
        self.assertEqual(smape([], []), 0.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            mae([1, 2], [1])


class BaselineModelTests(unittest.TestCase):
    def test_naive_forecast(self):
        self.assertEqual(naive_forecast([1, 2, 3], horizon=3), [3, 3, 3])

    def test_naive_forecast_empty_raises(self):
        with self.assertRaises(ValueError):
            naive_forecast([], horizon=1)

    def test_seasonal_naive_forecast(self):
        # With seasonality=3, repeats last 3 values
        result = seasonal_naive_forecast([1, 2, 3, 4, 5, 6], seasonality=3, horizon=4)
        self.assertEqual(result, [4, 5, 6, 4])

    def test_seasonal_naive_requires_seasonality_data(self):
        with self.assertRaises(ValueError):
            seasonal_naive_forecast([1, 2], seasonality=3, horizon=1)

    def test_moving_average_forecast(self):
        result = moving_average_forecast([1, 2, 3, 4, 5], window=3, horizon=2)
        self.assertEqual(result, [4.0, 4.0])

    def test_moving_average_window_too_large(self):
        with self.assertRaises(ValueError):
            moving_average_forecast([1, 2], window=3, horizon=1)

    def test_drift_forecast(self):
        # Linear data: drift = (5-1)/4 = 1.0
        result = drift_forecast([1, 2, 3, 4, 5], horizon=3)
        self.assertAlmostEqual(result[0], 6.0)
        self.assertAlmostEqual(result[1], 7.0)
        self.assertAlmostEqual(result[2], 8.0)

    def test_drift_forecast_requires_two_points(self):
        with self.assertRaises(ValueError):
            drift_forecast([1], horizon=1)


class WalkForwardTests(unittest.TestCase):
    def test_basic_walk_forward(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = walk_forward(data, naive_forecast, min_train_size=5, horizon=1, step_size=1)
        self.assertIsInstance(result, WalkForwardResult)
        self.assertEqual(len(result.folds), 5)
        self.assertEqual(result.min_train_size, 5)
        self.assertEqual(result.step_size, 1)
        self.assertEqual(result.horizon, 1)

    def test_walk_forward_fold_structure(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = walk_forward(data, naive_forecast, min_train_size=5, horizon=1, step_size=1)
        fold = result.folds[0]
        self.assertIsInstance(fold, BacktestResult)
        self.assertEqual(fold.train_start, 0)
        self.assertEqual(fold.train_end, 5)
        self.assertEqual(fold.test_start, 5)
        self.assertEqual(fold.test_end, 6)
        self.assertEqual(len(fold.predictions), 1)
        self.assertEqual(len(fold.actuals), 1)

    def test_walk_forward_multi_step_horizon(self):
        data = list(range(1, 21))
        result = walk_forward(
            data,
            lambda train: naive_forecast(train, horizon=3),
            min_train_size=10,
            horizon=3,
            step_size=2,
        )
        # Folds at train_end=10,12,14,16,18 -> 5 folds (10+3=13<=20, 12+3=15<=20, etc.)
        self.assertGreater(len(result.folds), 0)
        for fold in result.folds:
            self.assertEqual(len(fold.predictions), 3)
            self.assertEqual(len(fold.actuals), 3)

    def test_walk_forward_aggregate_metrics(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = walk_forward(data, naive_forecast, min_train_size=5, horizon=1, step_size=1)
        self.assertIn("mae", result.aggregate_metrics)
        self.assertIn("rmse", result.aggregate_metrics)
        # Naive forecast on linear data: each fold predicts the last train value
        # Fold 0: train=[1..5], pred=6, actual=6 -> error=0
        # Fold 1: train=[1..6], pred=7, actual=7 -> error=0
        # etc. All errors are 0 for this perfect linear case with naive.
        # Actually: naive predicts last value, so pred=5, actual=6 -> error=1
        self.assertAlmostEqual(result.aggregate_metrics["mae"], 1.0)

    def test_walk_forward_model_must_return_correct_length(self):
        def bad_model(train):
            return [1.0]  # returns 1 instead of 2

        with self.assertRaises(ValueError):
            walk_forward([1, 2, 3, 4, 5], bad_model, min_train_size=3, horizon=2)

    def test_walk_forward_validation(self):
        with self.assertRaises(ValueError):
            walk_forward([1, 2], naive_forecast, min_train_size=0)
        with self.assertRaises(ValueError):
            walk_forward([1, 2], naive_forecast, min_train_size=1, horizon=0)
        with self.assertRaises(ValueError):
            walk_forward([1, 2], naive_forecast, min_train_size=1, horizon=1, step_size=0)
        with self.assertRaises(ValueError):
            walk_forward([1, 2], naive_forecast, min_train_size=3, horizon=1)

    def test_walk_forward_with_seasonal_model(self):
        data = [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]
        result = walk_forward(
            data,
            lambda train: seasonal_naive_forecast(train, seasonality=3, horizon=1),
            min_train_size=6,
            horizon=1,
            step_size=1,
        )
        self.assertGreater(len(result.folds), 0)


class CrossValidationTests(unittest.TestCase):
    def test_basic_cross_validation(self):
        data = list(range(1, 21))
        result = cross_validate(data, naive_forecast, n_splits=5, horizon=1)
        self.assertIsInstance(result, CrossValidationResult)
        self.assertEqual(len(result.folds), 5)
        self.assertEqual(result.n_splits, 5)
        self.assertEqual(result.gap, 0)

    def test_cv_expanding_window(self):
        data = list(range(1, 21))
        result = cross_validate(
            data, naive_forecast, n_splits=3, horizon=1, expanding_window=True
        )
        # Expanding window: train sizes should increase
        train_sizes = [f.train_end - f.train_start for f in result.folds]
        self.assertEqual(train_sizes, sorted(train_sizes))

    def test_cv_sliding_window(self):
        data = list(range(1, 31))
        result = cross_validate(
            data, naive_forecast, n_splits=3, horizon=1, expanding_window=False
        )
        # Sliding window: train sizes should be equal
        train_sizes = [f.train_end - f.train_start for f in result.folds]
        if len(train_sizes) > 1:
            self.assertEqual(len(set(train_sizes)), 1)

    def test_cv_with_gap(self):
        data = list(range(1, 21))
        result = cross_validate(data, naive_forecast, n_splits=3, horizon=1, gap=2)
        self.assertEqual(result.gap, 2)
        # With gap, test sets should not overlap with training
        for fold in result.folds:
            self.assertGreaterEqual(fold.test_start, fold.train_end + 2)

    def test_cv_aggregate_metrics(self):
        data = list(range(1, 21))
        result = cross_validate(data, naive_forecast, n_splits=5, horizon=1)
        self.assertIn("mae", result.aggregate_metrics)
        self.assertIn("rmse", result.aggregate_metrics)

    def test_cv_validation(self):
        with self.assertRaises(ValueError):
            cross_validate([1, 2], naive_forecast, n_splits=1)
        with self.assertRaises(ValueError):
            cross_validate([1, 2], naive_forecast, n_splits=2, horizon=0)
        with self.assertRaises(ValueError):
            cross_validate([1, 2], naive_forecast, n_splits=2, gap=-1)
        with self.assertRaises(ValueError):
            cross_validate([1, 2, 3], naive_forecast, n_splits=5, horizon=2)

    def test_cv_fold_structure(self):
        data = list(range(1, 21))
        result = cross_validate(data, naive_forecast, n_splits=3, horizon=1)
        for fold in result.folds:
            self.assertIsInstance(fold, BacktestResult)
            self.assertGreater(fold.train_end, fold.train_start)
            self.assertGreater(fold.test_end, fold.test_start)
            self.assertEqual(len(fold.predictions), 1)
            self.assertEqual(len(fold.actuals), 1)


class BacktestResultTests(unittest.TestCase):
    def test_backtest_result_creation(self):
        result = BacktestResult(
            fold_index=0,
            train_start=0,
            train_end=10,
            test_start=10,
            test_end=12,
            predictions=[1.0, 2.0],
            actuals=[1.5, 2.5],
            metrics={"mae": 0.5},
        )
        self.assertEqual(result.fold_index, 0)
        self.assertEqual(result.metrics["mae"], 0.5)

    def test_backtest_result_validates_ranges(self):
        with self.assertRaises(ValueError):
            BacktestResult(
                fold_index=0,
                train_start=10,
                train_end=10,  # invalid: not > train_start
                test_start=10,
                test_end=12,
                predictions=[1.0],
                actuals=[1.0],
            )


class IntegrationTests(unittest.TestCase):
    def test_walk_forward_with_moving_average(self):
        data = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
        result = walk_forward(
            data,
            lambda train: moving_average_forecast(train, window=3, horizon=1),
            min_train_size=5,
            horizon=1,
            step_size=1,
        )
        self.assertGreater(len(result.folds), 0)
        self.assertIn("mae", result.aggregate_metrics)

    def test_cross_validate_with_drift(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = cross_validate(
            data,
            lambda train: drift_forecast(train, horizon=1),
            n_splits=3,
            horizon=1,
        )
        self.assertGreater(len(result.folds), 0)

    def test_perfect_forecast_zero_error(self):
        def perfect_model(train):
            # For test data [5,6,7,8,9,10], predict exactly those
            return [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = walk_forward(data, perfect_model, min_train_size=4, horizon=6, step_size=6)
        self.assertEqual(len(result.folds), 1)
        self.assertAlmostEqual(result.aggregate_metrics["mae"], 0.0)
        self.assertAlmostEqual(result.aggregate_metrics["rmse"], 0.0)

    def test_large_dataset_performance(self):
        import random

        random.seed(42)
        data = [random.gauss(100, 10) for _ in range(1000)]
        result = walk_forward(data, naive_forecast, min_train_size=500, horizon=1, step_size=50)
        self.assertGreater(len(result.folds), 0)
        self.assertIn("mae", result.aggregate_metrics)


if __name__ == "__main__":
    unittest.main()
