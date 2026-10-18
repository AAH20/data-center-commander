"""Example: Track model performance over time.

Uses PerformanceTracker to monitor forecast accuracy.
"""
from dcc.forecasting.drift import PerformanceTracker, ModelPerformanceSnapshot
from datetime import datetime, timedelta

tracker = PerformanceTracker(model_id="load-forecast-v1", tenant_id="tenant-1")
for day in range(30):
    snapshot = ModelPerformanceSnapshot(
        model_id="load-forecast-v1",
        tenant_id="tenant-1",
        window_start=datetime(2026, 1, 1) + timedelta(days=day),
        window_end=datetime(2026, 1, 1) + timedelta(days=day + 1),
        predictions=24,
        actuals=24,
        errors=[2.5 * (1 + day * 0.02)] * 24,
    )
    snapshot.compute_derived()
    tracker.record(snapshot)
print(f"Snapshots: {tracker.snapshot_count}")
