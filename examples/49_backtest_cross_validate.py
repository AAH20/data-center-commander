"""Example: Time-series cross-validation.

K-fold CV with gap to prevent data leakage.
"""
from dcc.forecasting.backtest import cross_validate

data = list(range(80))
result = cross_validate(
    data=data,
    model_fn=lambda train, horizon: [train[-1]] * horizon,
    n_splits=5,
    gap=2,
    horizon=3,
)
print(f"Splits: {result.n_splits}")
print(f"Folds: {len(result.folds)}")
for fold in result.folds:
    print(f"  Fold {fold.fold_index}: train={fold.train_start}-{fold.train_end}, test={fold.test_start}-{fold.test_end}")
