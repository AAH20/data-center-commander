"""Example: Resample time-series data.

Downsamples high-frequency data to a lower frequency.
"""
from dcc.validation.intervals import TimeSeries, DataPoint, Aggregation, resample
from datetime import datetime, timedelta, timezone

base = datetime(2026, 1, 1, tzinfo=timezone.utc)
points = [DataPoint(timestamp=base + timedelta(minutes=i), value=100 + i) for i in range(60)]
series = TimeSeries(name="load", interval=60, points=points)
resampled = resample(series, target_interval=300, downsample_method=Aggregation.MEAN)
print(f"Original: {len(series.points)} points")
print(f"Resampled to 5min: {len(resampled.points)} points")
for p in resampled.points[:3]:
    print(f"  {p.timestamp}: {p.value:.1f}")
