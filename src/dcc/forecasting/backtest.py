"""Time-series backtesting: walk-forward validation, cross-validation, and error metrics.

Pure-Python implementation with no external dependencies.
All functions operate on sequences of (timestamp, value) pairs or plain numeric sequences.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastPoint:
    """A single forecast prediction with optional prediction interval."""

    timestamp: float
    value: float
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True)
class BacktestResult:
    """Result of a single backtest fold."""

    fold_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    predictions: list[float]
    actuals: list[float]
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.train_end <= self.train_start:
            raise ValueError("train_end must be > train_start")
        if self.test_end <= self.test_start:
            raise ValueError("test_end must be > test_start")


@dataclass(frozen=True)
class WalkForwardResult:
    """Aggregated result from walk-forward validation."""

    folds: list[BacktestResult]
    min_train_size: int
    step_size: int
    horizon: int
    aggregate_metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CrossValidationResult:
    """Aggregated result from time-series cross-validation."""

    folds: list[BacktestResult]
    n_splits: int
    gap: int
    aggregate_metrics: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Error metrics
# ---------------------------------------------------------------------------


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Error."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return 0.0
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Root Mean Squared Error."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return 0.0
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))


def mape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Percentage Error (in percent).

    Skips zero actuals to avoid division by zero.
    """
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    pairs = [(a, p) for a, p in zip(actual, predicted) if a != 0]
    if not pairs:
        return 0.0
    return sum(abs((a - p) / a) for a, p in pairs) / len(pairs) * 100.0


def smape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Symmetric Mean Absolute Percentage Error (in percent)."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return 0.0
    denom = sum(abs(a) + abs(p) for a, p in zip(actual, predicted))
    if denom == 0:
        return 0.0
    return 2.0 * sum(abs(a - p) for a, p in zip(actual, predicted)) / denom * 100.0


def mase(
    actual: Sequence[float],
    predicted: Sequence[float],
    training_actual: Sequence[float],
    seasonality: int = 1,
) -> float:
    """Mean Absolute Scaled Error.

    Scales the error by the in-sample mean absolute error of a naive forecast.
    """
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if len(training_actual) <= seasonality:
        raise ValueError("training_actual must have more than seasonality elements")
    if not actual:
        return 0.0
    naive_errors = sum(
        abs(training_actual[i] - training_actual[i - seasonality])
        for i in range(seasonality, len(training_actual))
    )
    naive_mae = naive_errors / (len(training_actual) - seasonality)
    if naive_mae == 0:
        return 0.0
    return mae(actual, predicted) / naive_mae


def bias(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean signed error (positive = over-forecasting)."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return 0.0
    return sum(p - a for a, p in zip(actual, predicted)) / len(actual)


def variance_ratio(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Ratio of prediction variance to actual variance (1.0 is ideal)."""
    if len(actual) != len(predicted) or len(actual) < 2:
        return 1.0
    mean_a = sum(actual) / len(actual)
    mean_p = sum(predicted) / len(predicted)
    var_a = sum((a - mean_a) ** 2 for a in actual) / (len(actual) - 1)
    var_p = sum((p - mean_p) ** 2 for p in predicted) / (len(predicted) - 1)
    if var_a == 0:
        return 1.0 if var_p == 0 else float("inf")
    return var_p / var_a


def evaluate_forecast(
    actual: Sequence[float],
    predicted: Sequence[float],
    training_actual: Sequence[float] | None = None,
    seasonality: int = 1,
) -> dict[str, float]:
    """Compute a full suite of error metrics.

    Returns a dict with: mae, rmse, mape, smape, bias, variance_ratio, and
    optionally mase (when training_actual is provided).
    """
    metrics: dict[str, float] = {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "mape": mape(actual, predicted),
        "smape": smape(actual, predicted),
        "bias": bias(actual, predicted),
        "variance_ratio": variance_ratio(actual, predicted),
    }
    if training_actual is not None:
        metrics["mase"] = mase(actual, predicted, training_actual, seasonality)
    return metrics


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------


def walk_forward(
    data: Sequence[float],
    model: Callable[[Sequence[float]], Sequence[float]],
    *,
    min_train_size: int,
    horizon: int = 1,
    step_size: int = 1,
) -> WalkForwardResult:
    """Walk-forward (rolling-origin) validation.

    For each fold:
      1. Train on data[0:train_end]
      2. Predict the next `horizon` values
      3. Compare predictions to actuals
      4. Advance by `step_size`

    Args:
        data: The full time series.
        model: A callable that takes a training sequence and returns predictions
               of length `horizon`.
        min_train_size: Minimum number of training points for the first fold.
        horizon: Number of steps ahead to forecast.
        step_size: How many steps to roll forward between folds.

    Returns:
        WalkForwardResult with per-fold and aggregate metrics.
    """
    n = len(data)
    if min_train_size < 1:
        raise ValueError("min_train_size must be >= 1")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if step_size < 1:
        raise ValueError("step_size must be >= 1")
    if min_train_size + horizon > n:
        raise ValueError(
            f"data length ({n}) must be >= min_train_size ({min_train_size}) + horizon ({horizon})"
        )

    folds: list[BacktestResult] = []
    fold_idx = 0
    train_end = min_train_size

    while train_end + horizon <= n:
        train_data = data[:train_end]
        test_data = data[train_end : train_end + horizon]

        predictions = list(model(train_data))
        if len(predictions) != horizon:
            raise ValueError(
                f"model returned {len(predictions)} predictions, expected {horizon}"
            )

        metrics = evaluate_forecast(test_data, predictions, train_data)
        folds.append(
            BacktestResult(
                fold_index=fold_idx,
                train_start=0,
                train_end=train_end,
                test_start=train_end,
                test_end=train_end + horizon,
                predictions=predictions,
                actuals=list(test_data),
                metrics=metrics,
            )
        )

        fold_idx += 1
        train_end += step_size

    aggregate = _aggregate_fold_metrics(folds)
    return WalkForwardResult(
        folds=folds,
        aggregate_metrics=aggregate,
        min_train_size=min_train_size,
        step_size=step_size,
        horizon=horizon,
    )


# ---------------------------------------------------------------------------
# Time-series cross-validation
# ---------------------------------------------------------------------------


def cross_validate(
    data: Sequence[float],
    model: Callable[[Sequence[float]], Sequence[float]],
    *,
    n_splits: int = 5,
    horizon: int = 1,
    gap: int = 0,
    expanding_window: bool = True,
) -> CrossValidationResult:
    """Time-series cross-validation with optional gap.

    Unlike standard k-fold, this respects temporal order. Each fold uses
    only past data for training and future data for testing.

    Args:
        data: The full time series.
        model: A callable that takes a training sequence and returns predictions
               of length `horizon`.
        n_splits: Number of train/test splits.
        horizon: Number of steps ahead to forecast in each test set.
        gap: Number of observations to skip between train and test (purge).
        expanding_window: If True, training window grows; if False, it slides
                          with fixed size.

    Returns:
        CrossValidationResult with per-fold and aggregate metrics.
    """
    n = len(data)
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if gap < 0:
        raise ValueError("gap must be >= 0")

    # Minimum data needed: at least 1 train point + gap + horizon per split
    min_needed = 1 + gap + horizon
    if n < min_needed * n_splits:
        raise ValueError(
            f"data length ({n}) too short for {n_splits} splits with "
            f"gap={gap} and horizon={horizon}"
        )

    folds: list[BacktestResult] = []

    # Calculate split boundaries
    # We divide the data into n_splits+1 contiguous blocks; the first block is
    # always training, and each subsequent block (minus gap) is a test set.
    usable = n - gap  # total usable length after accounting for gaps
    block_size = usable // (n_splits + 1)

    for i in range(n_splits):
        train_start: int = 0
        if expanding_window:
            train_end = block_size * (i + 1)
        else:
            # Sliding window: fixed training size = block_size * n_splits
            train_start = block_size * i
            train_end = train_start + block_size * n_splits
            if train_end > n - gap - horizon:
                break

        test_start = train_end + gap
        test_end = test_start + horizon

        if test_end > n:
            break

        train_data = data[:train_end]
        test_data = data[test_start:test_end]

        predictions = list(model(train_data))
        if len(predictions) != horizon:
            raise ValueError(
                f"model returned {len(predictions)} predictions, expected {horizon}"
            )

        metrics = evaluate_forecast(test_data, predictions, train_data)
        folds.append(
            BacktestResult(
                fold_index=i,
                train_start=0 if expanding_window else train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                predictions=predictions,
                actuals=list(test_data),
                metrics=metrics,
            )
        )

    aggregate = _aggregate_fold_metrics(folds)
    return CrossValidationResult(
        folds=folds,
        aggregate_metrics=aggregate,
        n_splits=len(folds),
        gap=gap,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _aggregate_fold_metrics(folds: list[BacktestResult]) -> dict[str, float]:
    """Compute mean metrics across all folds."""
    if not folds:
        return {}

    all_metric_keys: set[str] = set()
    for f in folds:
        all_metric_keys.update(f.metrics.keys())

    aggregate: dict[str, float] = {}
    for key in sorted(all_metric_keys):
        values = [f.metrics[key] for f in folds if key in f.metrics]
        if values:
            aggregate[key] = sum(values) / len(values)
    return aggregate


# ---------------------------------------------------------------------------
# Baseline models for testing
# ---------------------------------------------------------------------------


def naive_forecast(training_data: Sequence[float], horizon: int = 1) -> list[float]:
    """Naive forecast: repeat the last observed value."""
    if not training_data:
        raise ValueError("training_data must not be empty")
    return [training_data[-1]] * horizon


def seasonal_naive_forecast(
    training_data: Sequence[float], seasonality: int, horizon: int = 1
) -> list[float]:
    """Seasonal naive forecast: repeat values from one season ago."""
    if not training_data:
        raise ValueError("training_data must not be empty")
    if seasonality < 1:
        raise ValueError("seasonality must be >= 1")
    if len(training_data) < seasonality:
        raise ValueError(
            f"training_data length ({len(training_data)}) must be >= seasonality ({seasonality})"
        )
    return [training_data[-seasonality + (i % seasonality)] for i in range(horizon)]


def moving_average_forecast(
    training_data: Sequence[float], window: int, horizon: int = 1
) -> list[float]:
    """Moving average forecast: average of the last `window` values."""
    if not training_data:
        raise ValueError("training_data must not be empty")
    if window < 1:
        raise ValueError("window must be >= 1")
    if window > len(training_data):
        raise ValueError(
            f"window ({window}) must be <= training_data length ({len(training_data)})"
        )
    avg = sum(training_data[-window:]) / window
    return [avg] * horizon


def drift_forecast(training_data: Sequence[float], horizon: int = 1) -> list[float]:
    """Drift method: linear extrapolation from first to last observed value."""
    if len(training_data) < 2:
        raise ValueError("training_data must have at least 2 points")
    n = len(training_data)
    drift = (training_data[-1] - training_data[0]) / (n - 1)
    return [training_data[-1] + drift * (i + 1) for i in range(horizon)]
