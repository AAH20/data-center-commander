"""Example: Walk-forward backtesting.

Validates forecast accuracy using expanding window validation.
"""
from dcc.forecasting.backtest import walk_forward

data = list(range(100))
result = walk_forward(
    data=data,
    model_fn=lambda train, horizon: [train[-1]] * horizon,
    min_train_size=20,
    step_size=5,
    horizon=5,
)
print(f"Folds: {len(result.folds)}")
print(f"Aggregate MAE: {result.aggregate_metrics.get('mae', 'N/A')}")
